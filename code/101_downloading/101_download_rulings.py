"""Descarga las resoluciones y laudos de PROFEPA listados en el catálogo.

Lee los CSV de DATA_DIR/catalogue y guarda cada PDF en
DATA_DIR/raw/<año de resolución>/<número de expediente>/<archivo>.pdf

Los archivos que ya existen se omiten, así que el script se puede volver a
correr para completar descargas fallidas. El resultado de cada descarga queda
en DATA_DIR/logs/download_log.csv.

Uso (desde la raíz del repositorio):
    code/.venv/Scripts/python code/101_downloading/101_download_rulings.py
    code/.venv/Scripts/python code/101_downloading/101_download_rulings.py --workers 4 --limit 20
"""

import argparse
import csv
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])

CATALOGUE_DIR = DATA_DIR / "catalogue"
RAW_DIR = DATA_DIR / "raw"
LOG_PATH = DATA_DIR / "logs" / "download_log.csv"

COL_ID = "Número de expediente y/o resolución"
COL_DATE = "Fecha de resolución"
COL_URL = "Hipervínculo a la resolución en versión pública"

INVALID_CHARS = re.compile(r'[\\/:*?"<>|\s]+')


def sanitize(name):
    """Convierte un texto en un nombre válido de carpeta o archivo en Windows."""
    return INVALID_CHARS.sub("_", name.strip()).strip("._")


def clean_url(url):
    # Algunos enlaces del catálogo traen caracteres sobrantes al final (p. ej. ".pdf}")
    return url.strip().rstrip("}").strip()


def build_tasks():
    """Una tarea por documento único (carpeta + archivo)."""
    tasks = {}
    for csv_path in sorted(CATALOGUE_DIR.glob("*.csv")):
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                url = clean_url(row[COL_URL])
                if not url.lower().startswith("http"):
                    continue

                date = row[COL_DATE].strip()
                year = date[:4] if date[:4].isdigit() else "sin_fecha"

                file_name = sanitize(unquote(Path(urlparse(url).path).name))
                if not file_name.lower().endswith(".pdf"):
                    file_name += ".pdf"
                ruling_id = sanitize(row[COL_ID]) or Path(file_name).stem

                dest = RAW_DIR / year / ruling_id / file_name
                tasks.setdefault(dest, {
                    "catalogue": csv_path.name,
                    "ruling_id": row[COL_ID].strip(),
                    "year": year,
                    "url": url,
                    "dest": dest,
                })
    return list(tasks.values())


def make_session():
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session = requests.Session()
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "Mozilla/5.0 (investigacion academica)"
    return session


def download(session, task):
    dest = task["dest"]
    if dest.exists() and dest.stat().st_size > 0:
        return "ya_existia", dest.stat().st_size

    try:
        response = session.get(task["url"], timeout=120)
    except requests.ConnectionError as e:
        # El servidor de PROFEPA no responde por https, algunos enlaces del catálogo lo usan
        if not task["url"].startswith("https://"):
            return f"error: {type(e).__name__}", 0
        try:
            response = session.get("http://" + task["url"][len("https://"):], timeout=120)
        except requests.RequestException as e2:
            return f"error: {type(e2).__name__}", 0
    except requests.RequestException as e:
        return f"error: {type(e).__name__}", 0
    if response.status_code != 200:
        return f"http_{response.status_code}", 0
    if not response.content.startswith(b"%PDF"):
        return "no_es_pdf", 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(response.content)
    tmp.replace(dest)
    return "descargado", len(response.content)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=4, help="descargas simultáneas (default: 4)")
    parser.add_argument("--limit", type=int, default=None, help="descargar solo los primeros N documentos (prueba)")
    args = parser.parse_args()

    tasks = build_tasks()[: args.limit]
    print(f"{len(tasks)} documentos únicos en el catálogo")

    session = make_session()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download, session, t): t for t in tasks}
        for i, future in enumerate(as_completed(futures), 1):
            task = futures[future]
            status, size = future.result()
            results.append({**task, "dest": task["dest"].relative_to(DATA_DIR).as_posix(),
                            "status": status, "bytes": size})
            if i % 100 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)}")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["catalogue", "ruling_id", "year", "url", "dest", "status", "bytes"])
        writer.writeheader()
        writer.writerows(sorted(results, key=lambda r: r["dest"]))

    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    for status, n in sorted(counts.items()):
        print(f"{status}: {n}")
    print(f"Bitácora: {LOG_PATH}")


if __name__ == "__main__":
    main()
