"""Corre las opciones de OCR sobre las 30 páginas de prueba (salida de 102a_benchmark_sample.py).

Por cada configuración escribe DATA_DIR/benchmark/salidas/<config>/<id>.md y agrega a
DATA_DIR/benchmark/salidas/tiempos.csv los segundos por página. La comparación con las
transcripciones de referencia la hace 202_benchmark_scores.py.

Configuraciones (CONFIGS):
    paddle_144          PaddleOCR-VL-1.6 completo (vLLM), página a 144 ppp sin corregir giro.
                        Es lo que hace PaddleOCR por omisión con un PDF.
    paddle_200_ori      igual, a 200 ppp y con corrección de giro (perfil "estandar")
    paddle_300_ori      igual, a 300 ppp (perfil "alta")
    paddle_gguf_200_ori PaddleOCR-VL-1.6 en GGUF con llama.cpp (la ruta de la laptop)
    olmocr_200          olmOCR-2-7B (FP8, vLLM), otro modelo abierto de OCR de documentos
    tesseract_300       Tesseract en español, como línea base clásica
    (olmOCR y Tesseract reciben la página ya enderezada con el clasificador de PaddleOCR)
    texto_embebido      el texto que ya trae el PDF (sin OCR), para medir qué tan confiable es

Servidores: en Colab el script levanta y apaga el servidor de cada modelo con el entorno
de vLLM (VLLM_ENV). En la laptop, paddle_gguf_200_ori usa llama.cpp (LLAMA_SERVER_EXE).

Uso:
    python 102d_benchmark_run.py --configs paddle_144 paddle_200_ori olmocr_200 tesseract_300
    python 102d_benchmark_run.py --configs texto_embebido paddle_gguf_200_ori      (laptop)
"""

import argparse
import base64
import csv
import io
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
import ocr  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
BENCH_DIR = DATA_DIR / "benchmark"
OUT_DIR = BENCH_DIR / "salidas"
VLLM_ENV = Path(os.getenv("VLLM_ENV", "/content/vllm_env"))

SERVERS = {
    "paddle_vllm": {
        "port": 8118,
        "cmd": ["{env}/bin/paddleocr", "genai_server", "--model_name", "PaddleOCR-VL-1.6-0.9B",
                "--backend", "vllm", "--host", "127.0.0.1", "--port", "8118"],
    },
    "olmocr": {
        "port": 8119,
        "cmd": ["{env}/bin/vllm", "serve", "allenai/olmOCR-2-7B-1025-FP8", "--host", "127.0.0.1",
                "--port", "8119", "--max-model-len", "16384", "--gpu-memory-utilization", "0.85",
                "--served-model-name", "olmocr"],
    },
}

CONFIGS = {
    "paddle_144": {"engine": "paddle", "server": "paddle_vllm", "dpi": 144, "orientacion": False},
    "paddle_200_ori": {"engine": "paddle", "server": "paddle_vllm", "dpi": 200, "orientacion": True},
    "paddle_300_ori": {"engine": "paddle", "server": "paddle_vllm", "dpi": 300, "orientacion": True},
    "paddle_gguf_200_ori": {"engine": "paddle", "server": "llama", "dpi": 200, "orientacion": True},
    "olmocr_200": {"engine": "vlm", "server": "olmocr", "dpi": 200, "lado_mayor": 1288},
    "tesseract_300": {"engine": "tesseract", "dpi": 300},
    "texto_embebido": {"engine": "texto_embebido"},
}

# Prompt de olmOCR-2 (build_no_anchoring_v4_yaml_prompt del paquete olmocr)
OLMOCR_PROMPT = (
    "Attached is one page of a document that you must process. Just return the plain text "
    "representation of this document as if you were reading it naturally. Convert equations to "
    "LateX and tables to HTML.\n"
    "If there are any figures or charts, label them with the following markdown syntax "
    "![Alt text describing the contents of the figure](page_startx_starty_width_height.png)\n"
    "Return your output as markdown, with a front matter section on top specifying values for the "
    "primary_language, is_rotation_valid, rotation_correction, is_table, and is_diagram parameters."
)


def wait_until_up(url, process, seconds=1800):
    for _ in range(seconds // 5):
        try:
            if requests.get(url, timeout=5).status_code == 200:
                return
        except requests.RequestException:
            pass
        if process is not None and process.poll() is not None:
            raise RuntimeError("el servidor terminó al arrancar")
        time.sleep(5)
    raise RuntimeError("el servidor no respondió a tiempo")


def start_server(name):
    """Devuelve (proceso, url base) del servidor del modelo."""
    log = open(OUT_DIR / f"servidor_{name}.log", "w", encoding="utf-8")
    if name == "llama":
        import importlib.util
        spec = importlib.util.spec_from_file_location("extract", Path(__file__).with_name("102b_extract_text.py"))
        extract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(extract)
        process = None if extract.server_is_up() else extract.start_llama_server()
        return process, extract.SERVER_URL
    spec = SERVERS[name]
    url = f"http://127.0.0.1:{spec['port']}"
    try:   # ya hay un servidor de este modelo corriendo
        if requests.get(f"{url}/v1/models", timeout=5).status_code == 200:
            return None, url
    except requests.RequestException:
        pass
    cmd = [c.format(env=VLLM_ENV) for c in spec["cmd"]]
    process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    wait_until_up(f"{url}/v1/models", process)
    return process, url


def stop_server(process):
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
        time.sleep(10)   # que libere la GPU


def page_image(pdf, dpi):
    doc, _ = ocr.open_pdf(pdf)
    try:
        return ocr.render(doc[0], dpi)
    finally:
        doc.close()


def run_paddle(pages, config, url):
    backend = "llama-cpp-server" if config["server"] == "llama" else "vllm-server"
    engine = ocr.PaddleVL(backend, f"{url}/v1", orientation=config["orientacion"], concurrency=8)
    profile = {"dpi": config["dpi"], "orientacion": config["orientacion"], "texto_embebido": False}
    for page_id, pdf in pages:
        t0 = time.time()
        document, _, _, _ = ocr.process_document(pdf, engine, profile)
        yield page_id, document, time.time() - t0


_ORIENTATION = None


def upright(image):
    """Endereza la página con el mismo clasificador de orientación que usa PaddleOCR, para que
    todos los motores reciban la página derecha. Para PIL, girar +etiqueta grados la endereza."""
    global _ORIENTATION
    import numpy as np
    if _ORIENTATION is None:
        from paddleocr import DocImgOrientationClassification
        _ORIENTATION = DocImgOrientationClassification(model_name="PP-LCNet_x1_0_doc_ori")
    result = _ORIENTATION.predict(np.ascontiguousarray(np.array(image.convert("RGB"))[:, :, ::-1]))[0]
    label = int(result["label_names"][0])
    return image.rotate(label, expand=True) if label else image


def run_vlm(pages, config, url):
    from PIL import Image
    for page_id, pdf in pages:
        t0 = time.time()
        image = upright(Image.fromarray(page_image(pdf, config["dpi"])[:, :, ::-1]))
        image.thumbnail((config["lado_mayor"], config["lado_mayor"]))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        payload = {
            "model": "olmocr", "temperature": 0.1, "max_tokens": 8000,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": OLMOCR_PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}},
            ]}],
        }
        response = requests.post(f"{url}/v1/chat/completions", json=payload, timeout=600)
        text = response.json()["choices"][0]["message"]["content"]
        if text.startswith("---"):   # encabezado YAML de olmOCR
            text = text.split("---", 2)[-1]
        yield page_id, text.strip(), time.time() - t0


def run_tesseract(pages, config):
    import pytesseract
    from PIL import Image
    for page_id, pdf in pages:
        t0 = time.time()
        image = upright(Image.fromarray(page_image(pdf, config["dpi"])[:, :, ::-1]))
        yield page_id, pytesseract.image_to_string(image, lang="spa"), time.time() - t0


def run_text_layer(pages):
    for page_id, pdf in pages:
        t0 = time.time()
        doc, _ = ocr.open_pdf(pdf)
        text = doc[0].get_textpage().get_text_range()
        doc.close()
        yield page_id, text, time.time() - t0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", nargs="+", required=True, choices=list(CONFIGS))
    args = parser.parse_args()

    with open(BENCH_DIR / "paginas.csv", encoding="utf-8") as f:
        pages = [(r["id"], BENCH_DIR / "paginas" / f"{r['id']}.pdf") for r in csv.DictReader(f)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    times_path = OUT_DIR / "tiempos.csv"

    for name in args.configs:
        config = CONFIGS[name]
        print(f"== {name}", flush=True)
        (OUT_DIR / name).mkdir(exist_ok=True)
        process = None
        try:
            if config.get("server"):
                process, url = start_server(config["server"])
            runner = {
                "paddle": lambda: run_paddle(pages, config, url),
                "vlm": lambda: run_vlm(pages, config, url),
                "tesseract": lambda: run_tesseract(pages, config),
                "texto_embebido": lambda: run_text_layer(pages),
            }[config["engine"]]()
            for page_id, text, seconds in runner:
                (OUT_DIR / name / f"{page_id}.md").write_text(text, encoding="utf-8")
                new = not times_path.exists()
                with open(times_path, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    if new:
                        writer.writerow(["config", "id", "segundos", "gpu"])
                    writer.writerow([name, page_id, round(seconds, 2), os.getenv("OCR_GPU", "laptop")])
                print(f"  {page_id}: {seconds:.1f} s", flush=True)
        except Exception as e:
            print(f"  ERROR en {name}: {type(e).__name__}: {e}", flush=True)
        finally:
            stop_server(process)


if __name__ == "__main__":
    main()
