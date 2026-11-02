"""Crea un vínculo de Dropbox (solo ver) para el PDF de cada resolución.

Lee los PDF de DATA_DIR/classification/clasificacion_final.csv y escribe
DATA_DIR/classification/intermedios/enlaces_dropbox.csv (pdf, enlace_dropbox). Reutiliza los
vínculos que ya existen y solo crea los que faltan, así que se puede volver a correr.
103b_combine.py usa ese archivo para la columna enlace_dropbox y el vínculo del Excel.

La ruta en Dropbox se obtiene de la ubicación de DATA_DIR dentro de la carpeta local de
Dropbox (la que indica %LOCALAPPDATA%/Dropbox/info.json).

Requiere DROPBOX_TOKEN en .env: token de una app de Dropbox con acceso a toda la cuenta y los
permisos files.metadata.read, sharing.read y sharing.write.

Uso (desde la raíz del repositorio, después de 103b_combine.py; luego se vuelve a correr
103b_combine.py):
    code/.venv/Scripts/python code/103_classification/103c_dropbox_links.py
"""

import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
TOKEN = os.environ["DROPBOX_TOKEN"].strip()
TABLA = DATA_DIR / "classification" / "clasificacion_final.csv"
SALIDA = DATA_DIR / "classification" / "intermedios" / "enlaces_dropbox.csv"
API = "https://api.dropboxapi.com/2"
HILOS = 8


def dropbox_base():
    """Ruta de DATA_DIR vista desde la raíz de Dropbox (por ejemplo /research/sentencias_profepa)."""
    info = json.loads((Path(os.environ["LOCALAPPDATA"]) / "Dropbox" / "info.json").read_text(encoding="utf-8"))
    for cuenta in info.values():
        raiz = Path(cuenta["path"])
        if DATA_DIR.resolve().is_relative_to(raiz.resolve()):
            return "/" + DATA_DIR.resolve().relative_to(raiz.resolve()).as_posix()
    raise SystemExit(f"{DATA_DIR} no está dentro de una carpeta de Dropbox")


def call(endpoint, body):
    """Llamada a la API con reintentos cuando Dropbox pide esperar."""
    for intento in range(8):
        r = requests.post(f"{API}/{endpoint}", headers={"Authorization": f"Bearer {TOKEN}"}, json=body, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("Retry-After", 2 ** intento)))
            continue
        return r
    r.raise_for_status()


def existing_links():
    """Vínculos que ya existen en la cuenta, por ruta en minúsculas."""
    links, body, endpoint = {}, {}, "sharing/list_shared_links"
    while True:
        r = call(endpoint, body)
        r.raise_for_status()
        data = r.json()
        for link in data["links"]:
            if link[".tag"] == "file" and "path_lower" in link:
                links[link["path_lower"]] = link["url"]
        if not data.get("has_more"):
            return links
        body = {"cursor": data["cursor"]}


def create(path):
    r = call("sharing/create_shared_link_with_settings", {"path": path})
    if r.ok:
        return r.json()["url"]
    error = r.json().get("error", {})
    if error.get(".tag") == "shared_link_already_exists":
        r = call("sharing/list_shared_links", {"path": path, "direct_only": True})
        if r.ok and r.json()["links"]:
            return r.json()["links"][0]["url"]
    print(f"  sin vínculo: {path} ({r.json().get('error_summary', r.status_code)})")
    return ""


def main():
    with open(TABLA, encoding="utf-8", newline="") as f:
        pdfs = [r["pdf"] for r in csv.DictReader(f)]
    hechos = {}
    if SALIDA.exists():
        with open(SALIDA, encoding="utf-8", newline="") as f:
            hechos = {r["pdf"]: r["enlace_dropbox"] for r in csv.DictReader(f) if r["enlace_dropbox"]}

    base = dropbox_base()
    ruta = {pdf: f"{base}/raw/{pdf}" for pdf in pdfs}
    existentes = existing_links()
    for pdf in pdfs:
        if pdf not in hechos and ruta[pdf].lower() in existentes:
            hechos[pdf] = existentes[ruta[pdf].lower()]
    faltan = [pdf for pdf in pdfs if pdf not in hechos]
    print(f"{len(pdfs)} PDF: {len(pdfs) - len(faltan)} ya tienen vínculo, se crean {len(faltan)}")

    def guardar():
        with open(SALIDA, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["pdf", "enlace_dropbox"])
            writer.writeheader()
            writer.writerows({"pdf": p, "enlace_dropbox": hechos.get(p, "")} for p in pdfs)

    with ThreadPoolExecutor(HILOS) as pool:
        for i, (pdf, url) in enumerate(zip(faltan, pool.map(lambda p: create(ruta[p]), faltan)), 1):
            if url:
                hechos[pdf] = url
            if i % 250 == 0:
                guardar()
                print(f"  {i}/{len(faltan)}")
    guardar()
    print(f"Vínculos: {sum(p in hechos for p in pdfs)} de {len(pdfs)}. Resultado en {SALIDA}")


if __name__ == "__main__":
    main()
