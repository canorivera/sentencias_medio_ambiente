"""Extrae el texto de cada resolución (texto embebido confiable u OCR con PaddleOCR-VL).

Por cada PDF escribe en DATA_DIR/text/<perfil>/<año>/<número de expediente>/:
    <archivo>.md    texto completo en Markdown
    <archivo>.json  por página: de dónde salió el texto (texto_embebido, ocr, ilegible,
                    error_ocr), Markdown, bloques de layout con su etiqueta, giro detectado
                    y el texto embebido original del PDF
Las reglas para usar el texto embebido y el manejo de PDF dañados están en ocr.py.

Perfiles (ocr.PROFILES): "estandar" para todo el corpus y "alta" (más ppp) para la segunda
pasada sobre las candidatas de 103_classify.py.

El reconocimiento corre en un servidor de modelo:
    laptop  llama.cpp con PaddleOCR-VL-1.6 en GGUF (OCR_BACKEND=llama-cpp-server). Si no está
            activo, el script lo inicia con LLAMA_SERVER_EXE y OCR_MODEL_DIR y lo apaga al final.
    Colab   vLLM con el modelo completo (OCR_BACKEND=vllm-server), lo levanta 102c_colab.py.

Los documentos ya procesados se omiten. Cada resultado se agrega a DATA_DIR/logs/ocr_<perfil>.csv.

Uso (desde la raíz del repositorio):
    code/.venv/Scripts/python code/102_text_extraction/102b_extract_text.py --perfil estandar
    code/.venv/Scripts/python code/102_text_extraction/102b_extract_text.py --perfil estandar --year 2023 --limit 5
    code/.venv/Scripts/python code/102_text_extraction/102b_extract_text.py --perfil alta --lista <DATA_DIR>/classification/candidatas_estandar.csv
En Colab (lo lanza 102c_colab.py): --pedazo <csv con pdf,url,bytes> --descargar --envio <carpeta>
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
import ocr  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
RAW_DIR = DATA_DIR / "raw"

BACKEND = os.getenv("OCR_BACKEND", "llama-cpp-server")
SERVER_URL = os.getenv("OCR_SERVER_URL", "http://127.0.0.1:8111")
SERVER_PARALLEL = int(os.getenv("OCR_SERVER_PARALLEL", "4"))
SESSION = os.getenv("OCR_SESSION", "laptop")
SHIP_EVERY = 25
LOG_FIELDS = ["fecha", "pdf", "paginas", "paginas_ocr", "paginas_texto_embebido", "segundos", "estado"]


def server_is_up():
    try:
        return requests.get(f"{SERVER_URL}/health", timeout=5).status_code == 200
    except requests.RequestException:
        return False


def start_llama_server():
    """Inicia llama-server con PaddleOCR-VL y espera a que responda."""
    model_dir = Path(os.environ["OCR_MODEL_DIR"])
    port = SERVER_URL.rsplit(":", 1)[-1]
    log = open(DATA_DIR / "logs" / "llama_server.log", "w", encoding="utf-8")
    process = subprocess.Popen(
        [
            os.environ["LLAMA_SERVER_EXE"],
            "-m", str(model_dir / "PaddleOCR-VL-1.6-GGUF.gguf"),
            "--mmproj", str(model_dir / "PaddleOCR-VL-1.6-GGUF-mmproj.gguf"),
            "--host", "127.0.0.1", "--port", port,
            "--temp", "0", "-ngl", "99",
            "--parallel", str(SERVER_PARALLEL), "-c", str(8192 * SERVER_PARALLEL),
        ],
        stdout=log, stderr=subprocess.STDOUT,
    )
    for _ in range(120):
        if server_is_up():
            return process
        if process.poll() is not None:
            break
        time.sleep(1)
    process.terminate()
    raise RuntimeError(f"llama-server no arrancó, revisar {log.name}")


def output_paths(pdf_rel, profile_name):
    """pdf_rel es relativo a DATA_DIR (raw/<año>/<expediente>/<archivo>.pdf)."""
    rel = Path(pdf_rel).relative_to("raw")
    base = DATA_DIR / "text" / profile_name / rel.parent / rel.stem
    return base.with_suffix(".md"), base.with_suffix(".json")


def list_pdfs(args):
    """Lista de PDF a procesar (rutas relativas a DATA_DIR) y, en Colab, su URL y tamaño."""
    if args.pedazo or args.lista:
        with open(args.pedazo or args.lista, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return [(r["pdf"], r.get("url"), int(r["bytes"]) if r.get("bytes") else None) for r in rows]
    base = RAW_DIR / args.year if args.year else RAW_DIR
    return [(p.relative_to(DATA_DIR).as_posix(), None, None)
            for p in sorted(base.rglob("*")) if p.is_file() and p.suffix.lower() == ".pdf"]


def download(pdf_rel, url, size):
    """En Colab: baja el PDF de PROFEPA y revisa que pese lo mismo que la copia en Dropbox."""
    dest = DATA_DIR / pdf_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            response = requests.get(url.replace("https://", "http://"), timeout=180)
            if response.status_code == 200 and (size is None or len(response.content) == size):
                dest.write_bytes(response.content)
                return dest
        except requests.RequestException:
            pass
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("descarga fallida o tamaño distinto")


def write_outputs(pdf_rel, profile_name, document, pages, meta):
    md_path, json_path = output_paths(pdf_rel, profile_name)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pdf": pdf_rel, "perfil": profile_name, **ocr.PROFILES[profile_name],
               "modelo": "PaddleOCR-VL-1.6", "backend": BACKEND, **meta, "paginas": pages}
    tmp = json_path.with_name(json_path.name + ".part")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(json_path)
    # el .md se escribe al final: su existencia marca el documento como terminado
    tmp = md_path.with_name(md_path.name + ".part")
    tmp.write_text(document, encoding="utf-8")
    tmp.replace(md_path)
    return md_path, json_path


def ship(files, log_path, ship_dir, k):
    """Empaca resultados en un zip (rutas relativas a DATA_DIR) para que la laptop los baje."""
    ship_dir.mkdir(parents=True, exist_ok=True)
    final = ship_dir / f"{SESSION}_{k:04d}.zip"
    tmp = final.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files + [log_path]:
            if f.exists():
                z.write(f, f.relative_to(DATA_DIR).as_posix())
    tmp.replace(final)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--perfil", default="estandar", choices=list(ocr.PROFILES))
    parser.add_argument("--year", help="solo esta carpeta de año de DATA_DIR/raw")
    parser.add_argument("--lista", help="CSV con columna pdf (relativa a DATA_DIR)")
    parser.add_argument("--pedazo", help="CSV con columnas pdf, url, bytes (Colab)")
    parser.add_argument("--descargar", action="store_true", help="bajar cada PDF de PROFEPA y borrarlo al terminar")
    parser.add_argument("--envio", help="carpeta donde dejar los zips de resultados (Colab)")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    profile = ocr.PROFILES[args.perfil]
    pending = [x for x in list_pdfs(args) if not output_paths(x[0], args.perfil)[0].exists()][: args.limit]
    print(f"{len(pending)} documentos pendientes (perfil {args.perfil}: {profile})", flush=True)
    if not pending:
        return

    log_path = DATA_DIR / "logs" / (f"ocr_{args.perfil}.csv" if SESSION == "laptop" else f"ocr_{args.perfil}_{SESSION}.csv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    server = None
    if not server_is_up():
        if BACKEND != "llama-cpp-server":
            raise RuntimeError(f"el servidor del modelo no responde en {SERVER_URL}")
        server = start_llama_server()
    engine = ocr.PaddleVL(BACKEND, f"{SERVER_URL}/v1", orientation=profile["orientacion"],
                          concurrency=SERVER_PARALLEL)

    start, total_pages, to_ship, shipped = time.time(), 0, [], 0
    try:
        for i, (pdf_rel, url, size) in enumerate(pending, 1):
            t0 = time.time()
            pages, status = [], ""
            try:
                if args.descargar:
                    download(pdf_rel, url, size)
                document, pages, meta, status = ocr.process_document(DATA_DIR / pdf_rel, engine, profile)
                to_ship += write_outputs(pdf_rel, args.perfil, document, pages, meta)
            except ocr.UnreadablePdf:
                status = "pdf_ilegible"
            except Exception as e:
                status = f"error: {type(e).__name__}: {e}"[:300]
            finally:
                if args.descargar:
                    (DATA_DIR / pdf_rel).unlink(missing_ok=True)
            seconds = round(time.time() - t0, 1)
            n_ocr = sum(p["fuente"] == "ocr" for p in pages)
            total_pages += n_ocr
            new = not log_path.exists()
            with open(log_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
                if new:
                    writer.writeheader()
                writer.writerow({
                    "fecha": datetime.now().isoformat(timespec="seconds"), "pdf": pdf_rel,
                    "paginas": len(pages), "paginas_ocr": n_ocr,
                    "paginas_texto_embebido": sum(p["fuente"] == "texto_embebido" for p in pages),
                    "segundos": seconds, "estado": status,
                })
            rate = total_pages / max(time.time() - start, 1)
            print(f"[{i}/{len(pending)}] {Path(pdf_rel).name}: {len(pages)} págs ({n_ocr} OCR), "
                  f"{seconds} s, {status} ({rate:.2f} págs OCR/s)", flush=True)
            if args.envio and (len(to_ship) >= 2 * SHIP_EVERY or i == len(pending)):
                ship(to_ship, log_path, Path(args.envio), shipped)
                to_ship, shipped = [], shipped + 1
    finally:
        if server is not None:
            server.terminate()
    print(f"Bitácora: {log_path}")


if __name__ == "__main__":
    main()
