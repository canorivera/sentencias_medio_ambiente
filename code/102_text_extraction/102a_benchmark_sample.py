"""Elige las páginas de prueba para comparar opciones de OCR.

1. Recorre todos los PDF de DATA_DIR/raw y describe cada página: rotación, orientación,
   resolución efectiva de la imagen escaneada, cuánto de la página cubre la imagen, texto
   embebido y si ese texto menciona vida silvestre. El inventario queda en
   DATA_DIR/benchmark/inventario_paginas.csv (si ya existe, se reutiliza).
2. Elige 30 páginas de documentos distintos, por estratos:
     digital         4  PDF exportado de Word con texto completo (referencia = texto embebido)
     escaneo_bueno   5  escaneo de 200 ppp o más
     escaneo_malo    6  escaneo de menos de 150 ppp
     girada          3  contenido de lado o de cabeza (clasificador de orientación de PaddleOCR)
     tabla           3  página con muchas cifras (coordenadas, montos)
     vida_silvestre  9  escaneo cuyo texto embebido menciona términos de vida silvestre
3. Por cada página escribe en DATA_DIR/benchmark/paginas/:
     <id>.pdf        la página sola, para los motores de OCR
     <id>.png        imagen a 300 ppp, para revisar
     <id>_f<k>.png   la imagen en franjas horizontales, para transcribirla a mano
   y la lista en DATA_DIR/benchmark/paginas.csv.

Uso (desde la raíz del repositorio):
    code/.venv/Scripts/python code/102_text_extraction/102a_benchmark_sample.py
"""

import csv
import os
import random
import re
import unicodedata
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])

RAW_DIR = DATA_DIR / "raw"
BENCH_DIR = DATA_DIR / "benchmark"
INVENTORY = BENCH_DIR / "inventario_paginas.csv"
PAGES_DIR = BENCH_DIR / "paginas"

SEED = 20261027
QUOTAS = {"digital": 4, "escaneo_bueno": 5, "escaneo_malo": 6, "girada": 3, "tabla": 3, "vida_silvestre": 9}
OFFICE = re.compile(r"word|libreoffice|openoffice|writer|wps", re.I)
WILDLIFE = re.compile(r"vida silvestre|fauna silvestre|ejemplares de|nom-059|cites|\bpimvs\b|zoologic|"
                      r"unidad(es)? de manejo|aseguramiento precautorio|especies? (en riesgo|amenazad|en peligro)")
FIELDS = ["pdf", "pagina", "paginas_doc", "productor", "rotacion", "apaisada", "ppp_imagen",
          "cobertura_imagen", "chars_texto", "proporcion_digitos", "vida_silvestre"]


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def describe_page(page):
    width, height = page.get_size()
    best_dpi, coverage = 0.0, 0.0
    for obj in page.get_objects(max_depth=2):
        if obj.type != pdfium_c.FPDF_PAGEOBJ_IMAGE:
            continue
        left, bottom, right, top = obj.get_bounds()
        area = max(right - left, 0) * max(top - bottom, 0) / (width * height)
        if area > coverage:
            px_w, px_h = obj.get_px_size()
            inches = max(right - left, top - bottom) / 72
            coverage, best_dpi = area, max(px_w, px_h) / inches if inches else 0
    text = page.get_textpage().get_text_range()
    chars = len(text.strip())
    digits = sum(c.isdigit() for c in text) / chars if chars else 0
    return {
        "rotacion": page.get_rotation(),
        "apaisada": int(width > height),
        "ppp_imagen": round(best_dpi),
        "cobertura_imagen": round(coverage, 2),
        "chars_texto": chars,
        "proporcion_digitos": round(digits, 3),
        "vida_silvestre": int(bool(WILDLIFE.search(normalize(text)))),
    }


def build_inventory():
    pdfs = sorted(p for p in RAW_DIR.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    with open(INVENTORY, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i, pdf in enumerate(pdfs, 1):
            try:
                doc = pdfium.PdfDocument(str(pdf))
            except pdfium.PdfiumError:
                continue
            meta = doc.get_metadata_dict()
            producer = f"{meta.get('Producer', '')} | {meta.get('Creator', '')}".strip(" |")
            for k in range(len(doc)):
                try:
                    row = describe_page(doc[k])
                except Exception:
                    continue
                row.update(pdf=pdf.relative_to(DATA_DIR).as_posix(), pagina=k + 1,
                           paginas_doc=len(doc), productor=producer)
                writer.writerow(row)
            doc.close()
            if i % 500 == 0:
                print(f"  {i}/{len(pdfs)} PDF")


def find_rotated(scanned, wanted, rng):
    """Páginas cuyo contenido está de lado o de cabeza. La marca /Rotate del PDF no sirve: el
    escáner LANIER la pone en casi todas y la página se ve derecha. Se usa el clasificador de
    orientación de PaddleOCR sobre una muestra (en una exploración marcó ~5% de los escaneos)."""
    import numpy as np
    from paddleocr import DocImgOrientationClassification
    model = DocImgOrientationClassification(model_name="PP-LCNet_x1_0_doc_ori")
    sample = rng.sample(scanned, min(3000, len(scanned)))
    found = []
    for r in sample:
        try:
            doc = pdfium.PdfDocument(str(DATA_DIR / r["pdf"]))
            image = doc[r["pagina"] - 1].render(scale=1).to_numpy()[:, :, :3]
            doc.close()
        except Exception:
            continue
        if (image.mean(axis=2) < 128).mean() < 0.03:   # casi en blanco
            continue
        result = model.predict(np.ascontiguousarray(image))[0]
        if result["label_names"][0] != "0" and float(result["scores"][0]) > 0.9:
            found.append({**r, "giro": result["label_names"][0]})
            if len(found) >= wanted * 3:
                break
    return found


def stratum_candidates(rows, rng):
    scanned = [r for r in rows if r["cobertura_imagen"] >= 0.8]
    return {
        "digital": [r for r in rows if OFFICE.search(r["productor"]) and r["chars_texto"] >= 1500
                    and r["cobertura_imagen"] < 0.5],
        "escaneo_bueno": [r for r in scanned if r["ppp_imagen"] >= 200 and not r["vida_silvestre"]],
        "escaneo_malo": [r for r in scanned if 0 < r["ppp_imagen"] < 150 and not r["vida_silvestre"]],
        "girada": find_rotated(scanned, QUOTAS["girada"], rng),
        "tabla": [r for r in scanned if r["chars_texto"] >= 300 and r["proporcion_digitos"] >= 0.2],
        "vida_silvestre": [r for r in scanned if r["vida_silvestre"] and r["chars_texto"] >= 800],
    }


def pick_pages(rows):
    rng = random.Random(SEED)
    used_docs, chosen = set(), []
    for stratum, candidates in stratum_candidates(rows, rng).items():
        rng.shuffle(candidates)
        taken = 0
        for r in candidates:
            # sin primeras páginas en la mayoría de estratos: suelen ser carátulas y sellos
            if r["pdf"] in used_docs or (r["pagina"] == 1 and stratum != "girada"):
                continue
            chosen.append({**r, "estrato": stratum})
            used_docs.add(r["pdf"])
            taken += 1
            if taken == QUOTAS[stratum]:
                break
        print(f"  {stratum}: {taken} de {QUOTAS[stratum]} ({len(candidates)} candidatas)")
    for k, r in enumerate(chosen, 1):
        r["id"] = f"p{k:02d}_{r['estrato']}"
    return chosen


def export_page(row):
    doc = pdfium.PdfDocument(str(DATA_DIR / row["pdf"]))
    single = pdfium.PdfDocument.new()
    single.import_pages(doc, [row["pagina"] - 1])
    single.save(str(PAGES_DIR / f"{row['id']}.pdf"))
    image = doc[row["pagina"] - 1].render(scale=300 / 72).to_pil().convert("L")
    image.save(PAGES_DIR / f"{row['id']}.png")
    if row.get("giro"):
        # copia derecha para transcribir (el clasificador da el giro del contenido)
        image = image.rotate(int(row["giro"]), expand=True)
        image.save(PAGES_DIR / f"{row['id']}_derecha.png")
    # franjas con un poco de traslape, legibles al transcribir
    n = 3
    height = image.height
    for k in range(n):
        top = max(0, int(k * height / n) - 60)
        bottom = min(height, int((k + 1) * height / n) + 60)
        image.crop((0, top, image.width, bottom)).save(PAGES_DIR / f"{row['id']}_f{k + 1}.png")
    if row["estrato"] == "digital":
        text = doc[row["pagina"] - 1].get_textpage().get_text_range()
        (PAGES_DIR / f"{row['id']}_texto_embebido.txt").write_text(text, encoding="utf-8")
    doc.close()


def main():
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    PAGES_DIR.mkdir(exist_ok=True)
    if not INVENTORY.exists():
        print("Inventario de páginas (tarda unos minutos)")
        build_inventory()
    with open(INVENTORY, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ["pagina", "paginas_doc", "rotacion", "apaisada", "ppp_imagen", "chars_texto", "vida_silvestre"]:
            r[k] = int(r[k])
        for k in ["cobertura_imagen", "proporcion_digitos"]:
            r[k] = float(r[k])
    print(f"{len(rows)} páginas en el inventario")

    chosen = pick_pages(rows)
    for r in chosen:
        export_page(r)
    with open(BENCH_DIR / "paginas.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "estrato"] + FIELDS + ["giro"], restval="")
        writer.writeheader()
        writer.writerows(chosen)
    print(f"{len(chosen)} páginas en {PAGES_DIR}")


if __name__ == "__main__":
    main()
