"""Funciones comunes de extracción de texto (las usan 102b_extract_text.py y 102d_benchmark_run.py).

Por cada página de un PDF se decide de dónde sale el texto:
    texto_embebido  PDF exportado de Word u otro procesador de textos, con texto visible
                    (no la capa invisible que deja el OCR de un escáner), al menos 200
                    caracteres y sin rectángulos negros de testado encima del texto (si los
                    hay, el texto embebido podría traer datos testados)
    ocr             todo lo demás: la página se dibuja a los ppp del perfil y pasa por
                    PaddleOCR-VL (layout en Paddle y reconocimiento en un servidor vLLM o llama.cpp)
    ilegible        la página no se pudo dibujar

PDF dañados, en este orden: pypdfium2; reparación en memoria con PyMuPDF; páginas que aun
así no cargan se dibujan con PyMuPDF; si el PDF no tiene páginas legibles, se rescatan las
imágenes JPEG de sus bytes. Si nada funciona, el documento queda como pdf_ilegible y el
proceso sigue con el siguiente.
"""

import ctypes
import os
import re
from pathlib import Path

# Paddle reserva casi toda la VRAM por defecto. Aquí la comparte con el servidor del modelo.
os.environ.setdefault("FLAGS_allocator_strategy", "auto_growth")

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

OFFICE = re.compile(r"word|libreoffice|openoffice|writer|wps office", re.I)
MIN_CHARS_TEXT_LAYER = 200
MIN_CHARS_WITH_IMAGE = 1000
MAX_IMAGE_COVERAGE = 0.5
# Páginas por tanda de OCR. Cada página genera decenas de peticiones (una por bloque de texto) y
# la tanda espera a su bloque más lento: tandas más grandes dejan menos tiempo muerto al servidor.
CHUNK_PAGES = int(os.getenv("OCR_CHUNK_PAGES", "8"))

# Perfiles de extracción. "estandar" es la primera pasada sobre todo el corpus y "alta" la
# segunda pasada sobre las candidatas. Benchmark del 2026-10-27 (30 páginas, 202_benchmark_scores):
# a 200 ppp con giro corregido el OCR encontró 100% de los términos y 94-96% de las palabras;
# 144 ppp perdió calidad en escaneos malos y 300 ppp solo los mejoró un poco.
PROFILES = {
    "estandar": {"dpi": 200, "orientacion": True, "texto_embebido": True},
    "alta": {"dpi": 300, "orientacion": True, "texto_embebido": True},
}


class UnreadablePdf(Exception):
    pass


def open_pdf(path):
    """Abre un PDF. Si pypdfium2 no puede, lo repara con PyMuPDF en memoria."""
    try:
        return pdfium.PdfDocument(str(path)), "ok"
    except pdfium.PdfiumError:
        pass
    import pymupdf
    error = ""
    for options in ({}, {"garbage": 1}, {"garbage": 3, "clean": True}):
        try:
            with pymupdf.open(str(path)) as broken:
                data = broken.tobytes(**options)
            return pdfium.PdfDocument(data), "reparado"
        except Exception as e:
            error = str(e)
    raise UnreadablePdf(error)


def rescue_images(path, min_width=800):
    """Último recurso para PDF sin páginas legibles: los escaneos suelen guardar cada página
    como un JPEG. Se buscan esos JPEG en los bytes del archivo y se decodifican."""
    import io
    from PIL import Image
    data = Path(path).read_bytes()
    images, pos = [], 0
    while (start := data.find(b"\xff\xd8\xff", pos)) != -1:
        end = data.find(b"\xff\xd9", start)
        if end == -1:
            break
        pos = end + 2
        try:
            image = Image.open(io.BytesIO(data[start:pos]))
            image.load()
        except Exception:
            pos = start + 3
            continue
        if image.width >= min_width:
            images.append(np.ascontiguousarray(np.array(image.convert("RGB"))[:, :, ::-1]))
    return images


def producer(doc):
    meta = doc.get_metadata_dict()
    return f"{meta.get('Producer', '')} | {meta.get('Creator', '')}".strip(" |")


def _dark_fill_rects(page):
    """Rectángulos rellenos de color oscuro (posibles testados dibujados sobre el texto)."""
    rects = []
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    for obj in page.get_objects(max_depth=2):
        if obj.type != pdfium_c.FPDF_PAGEOBJ_PATH:
            continue
        if not pdfium_c.FPDFPageObj_GetFillColor(obj.raw, r, g, b, a):
            continue
        if a.value > 200 and max(r.value, g.value, b.value) < 70:
            left, bottom, right, top = obj.get_bounds()
            if (right - left) * (top - bottom) > 20:
                rects.append((left, bottom, right, top))
    return rects


def _image_coverage(page):
    width, height = page.get_size()
    coverage = 0.0
    for obj in page.get_objects(max_depth=2):
        if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:
            left, bottom, right, top = obj.get_bounds()
            coverage = max(coverage, (right - left) * (top - bottom) / (width * height))
    return coverage


def _text_under_rects(textpage, rects):
    if not rects:
        return False
    for i in range(textpage.count_chars()):
        left, bottom, right, top = textpage.get_charbox(i)
        cx, cy = (left + right) / 2, (bottom + top) / 2
        if any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in rects):
            return True
    return False


def _visible_text_share(page):
    """Proporción de objetos de texto visibles. Los escaneos con OCR del escáner traen el texto
    invisible (modo 3) encima de la imagen. Los PDF de Word, visible (aunque tengan una imagen
    de fondo con el membrete)."""
    modes = [pdfium_c.FPDFTextObj_GetTextRenderMode(obj.raw) for obj in page.get_objects(max_depth=2)
             if obj.type == pdfium_c.FPDF_PAGEOBJ_TEXT]
    return sum(m != pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE for m in modes) / len(modes) if modes else 0


def text_layer_status(page, is_office):
    """Texto embebido de la página y si se puede usar en lugar del OCR (y por qué no)."""
    textpage = page.get_textpage()
    text = textpage.get_text_range().strip()
    if not is_office:
        return text, False, "no_es_documento_digital"
    if len(text) < MIN_CHARS_TEXT_LAYER:
        return text, False, "poco_texto"
    if _visible_text_share(page) < 0.9:
        return text, False, "texto_invisible_de_escaneo"
    # poco texto sobre una imagen grande: probablemente un escaneo pegado en el documento
    if len(text) < MIN_CHARS_WITH_IMAGE and _image_coverage(page) > MAX_IMAGE_COVERAGE:
        return text, False, "imagen_con_poco_texto"
    if _text_under_rects(textpage, _dark_fill_rects(page)):
        return text, False, "texto_bajo_testado"
    return text, True, "usado"


def render(page, dpi):
    """Imagen BGR de la página a los ppp indicados (formato que espera PaddleOCR)."""
    image = page.render(scale=dpi / 72, grayscale=False).to_numpy()
    if image.ndim == 2:
        image = np.stack([image] * 3, axis=-1)
    return np.ascontiguousarray(image[:, :, :3])


def render_with_pymupdf(path, k, dpi):
    """Segundo intento para páginas que pypdfium2 no puede cargar."""
    import pymupdf
    with pymupdf.open(str(path)) as doc:
        pix = doc[k].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return np.ascontiguousarray(image[:, :, ::-1])   # RGB a BGR


CJK_RUN = re.compile(r"[　-鿿豈-﫿]{3,}")
CHAR_RUN = re.compile(r"(.)\1{59,}")
UNIT_LOOP = re.compile(r"(\S.{1,79}?)(?:\s*\1){14,}", re.S)


def clean_loops(text):
    """Quita los bucles de generación del modelo. En el benchmark aparecieron en bloques que
    no son texto (un emblema leído como un ideograma repetido cientos de veces, un sello leído
    como fórmula repetida 520 veces). Se quitan: ideogramas (no hay en estas resoluciones),
    un carácter repetido más de 60 veces (se dejan 60; las actas usan rayas largas) y una
    misma secuencia con letras o números repetida 15 veces o más seguidas (se deja una)."""
    text = CJK_RUN.sub("", text)
    text = CHAR_RUN.sub(lambda m: m.group(1) * 60, text)
    # la secuencia debe tener letras o números fuera de etiquetas HTML y al menos dos caracteres
    # distintos: así no se tocan las celdas vacías de tablas ni las filas de "XXXX" con que
    # algunas versiones públicas tachan datos
    def collapse(m):
        unit = m.group(1)
        visible = re.sub(r"<[^>]*>", "", unit)
        return unit if re.search(r"\w", visible) and len(set(visible.replace(" ", ""))) >= 2 else m.group(0)
    return UNIT_LOOP.sub(collapse, text)


class PaddleVL:
    """PaddleOCR-VL con el reconocimiento en un servidor (vllm-server o llama-cpp-server)."""

    def __init__(self, backend, server_url, orientation=True, concurrency=4):
        from paddleocr import PaddleOCRVL
        self.pipeline = PaddleOCRVL(
            vl_rec_backend=backend,
            vl_rec_server_url=server_url,
            vl_rec_max_concurrency=concurrency,
            use_doc_orientation_classify=orientation,
            use_doc_unwarping=False,
            # PaddleOCR deja fuera del Markdown encabezados, pies y notas al margen. Aquí se
            # conservan: los pies de PROFEPA traen el monto de la multa y las medidas
            # correctivas, y las notas al margen, lo testado. Solo se omiten números de página
            # e imágenes.
            markdown_ignore_labels=["number", "header_image", "footer_image"],
        )

    def ocr(self, images):
        """Resultados de PaddleOCR-VL para una lista de imágenes, en orden."""
        return list(self.pipeline.predict_iter(images))

    def restructure(self, results):
        """Une tablas partidas entre páginas y reordena niveles de títulos. Devuelve el
        Markdown de cada página."""
        pages = self.pipeline.restructure_pages(results, merge_tables=True, relevel_titles=True,
                                                concatenate_pages=False)
        return [clean_loops(p.markdown["markdown_texts"]) for p in pages]


def ocr_page_record(result):
    res = result.json["res"]
    angle = None
    if isinstance(res.get("doc_preprocessor_res"), dict):
        angle = res["doc_preprocessor_res"].get("angle")
    return {
        "bloques": [
            {"etiqueta": b["block_label"], "bbox": b["block_bbox"], "texto": clean_loops(b["block_content"])}
            for b in res["parsing_res_list"]
        ],
        "giro_detectado": angle,
    }


def _empty_record(k):
    return {"pagina": k + 1, "fuente": "", "markdown": "", "texto_embebido": "",
            "motivo_texto_embebido": "", "bloques": [], "giro_detectado": None}


def _process_rescued(path, engine):
    images = rescue_images(path)
    if not images:
        raise UnreadablePdf("sin páginas legibles ni imágenes recuperables")
    pages, results = [], []
    for start in range(0, len(images), CHUNK_PAGES):
        results += engine.ocr(images[start:start + CHUNK_PAGES])
    for k, (res, markdown) in enumerate(zip(results, engine.restructure(results))):
        record = _empty_record(k)
        record.update(fuente="ocr", motivo_texto_embebido="imagen_rescatada", markdown=markdown,
                      **ocr_page_record(res))
        pages.append(record)
    document = "\n\n".join(p["markdown"] for p in pages if p["markdown"])
    meta = {"productor_pdf": "", "apertura": "imagenes_rescatadas", "paginas_doc": len(pages)}
    return document, pages, meta, "ok_imagenes_rescatadas"


def process_document(path, engine, profile):
    """Extrae el texto de un PDF. Devuelve (markdown del documento, registro por página, estado)."""
    try:
        doc, open_status = open_pdf(path)
    except UnreadablePdf:
        return _process_rescued(path, engine)
    try:
        is_office = bool(OFFICE.search(producer(doc)))
        pages = []
        to_ocr = []   # páginas que van a OCR
        for k in range(len(doc)):
            record = _empty_record(k)
            try:
                text, usable, reason = text_layer_status(doc[k], is_office)
                record.update(texto_embebido=text, motivo_texto_embebido=reason)
                if usable and profile["texto_embebido"]:
                    record.update(fuente="texto_embebido", markdown=text)
                else:
                    record["fuente"] = "ocr"
                    to_ocr.append(k)
            except Exception as e:
                # la página no carga en pypdfium2: se intenta dibujar con PyMuPDF
                record.update(fuente="ocr", motivo_texto_embebido=f"{type(e).__name__}: {e}"[:200])
                to_ocr.append(k)
            pages.append(record)
        meta ={"productor_pdf": producer(doc), "apertura": open_status, "paginas_doc": len(doc)}

        # OCR por tandas: las páginas se dibujan justo antes, para no tener todo el documento
        # en memoria. Si una tanda falla, se reintenta página por página.
        results = {}
        for start in range(0, len(to_ocr), CHUNK_PAGES):
            images = {}
            for k in to_ocr[start:start + CHUNK_PAGES]:
                try:
                    images[k] = render(doc[k], profile["dpi"])
                except Exception:
                    try:
                        images[k] = render_with_pymupdf(path, k, profile["dpi"])
                    except Exception as e:
                        pages[k].update(fuente="ilegible", motivo_texto_embebido=f"{type(e).__name__}: {e}"[:200])
            try:
                for k, res in zip(images, engine.ocr(list(images.values()))):
                    results[k] = res
            except Exception:
                for k, img in images.items():
                    try:
                        results[k] = engine.ocr([img])[0]
                    except Exception as e:
                        pages[k].update(fuente="error_ocr", motivo_texto_embebido=f"{type(e).__name__}: {e}"[:200])
            for k in images:
                if k in results:
                    results[k].pop("input_img", None)   # la imagen ya no se necesita
            del images
    finally:
        doc.close()

    if results:
        order = sorted(results)
        for k in order:
            pages[k].update(ocr_page_record(results[k]))
        for k, markdown in zip(order, engine.restructure([results[k] for k in order])):
            pages[k]["markdown"] = markdown

    document = "\n\n".join(p["markdown"] for p in pages if p["markdown"])
    sources = {p["fuente"] for p in pages}
    status = "ok" if sources <= {"ocr", "texto_embebido"} else "ok_con_paginas_fallidas"
    if open_status == "reparado":
        status += "_pdf_reparado"
    return document, pages, meta, status
