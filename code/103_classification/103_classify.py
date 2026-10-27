"""Clasifica las resoluciones según los términos del libro de códigos y la serie del expediente.

Lee el texto de DATA_DIR/text/<perfil>/ (salida de 102b_extract_text.py) y escribe en
DATA_DIR/classification/:
    clasificacion_<perfil>.csv   una fila por resolución: serie del expediente, puntaje,
                                 términos encontrados y si es candidata
    apariciones_<perfil>.csv     cada aparición de cada término con su contexto, para revisar
                                 por qué se marcó una resolución
    candidatas_<perfil>.csv      lista de PDF candidatos (entrada de la segunda pasada de OCR)
Además regenera code/103_classification/CODEBOOK.md desde codebook.csv.

Una resolución es candidata si cumple al menos una de estas reglas:
    1. su expediente es de la serie de vida silvestre: 2C.27.3 (cuadro de clasificación
       archivística de PROFEPA de 2018) o 3S.3 (guía de archivo 2026)
    2. su puntaje (suma de pesos de términos distintos) es de UMBRAL o más
UMBRAL = 6 (por ejemplo, dos términos fuertes, o uno fuerte y dos medios). Calibrado con las
primeras 125 resoluciones extraídas: los expedientes de la serie de vida silvestre sacaron 9
o más (salvo uno), y un solo término fuerte marcaba a un tercio de las demás series.

Uso (desde la raíz del repositorio):
    code/.venv/Scripts/python code/103_classification/103_classify.py --perfil estandar
"""

import argparse
import csv
import os
import re
import sys
from multiprocessing import Pool
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from keywords import codebook_markdown, load_codebook, match_terms, normalize, score  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
OUT_DIR = DATA_DIR / "classification"
DOWNLOAD_LOG = DATA_DIR / "logs" / "download_log.csv"

UMBRAL = 6
CONTEXTO = 80
# Series de expediente (cuadro de clasificación archivística de PROFEPA)
SERIES = {
    "2C.27.1": "industria", "2C.27.2": "forestal", "2C.27.3": "vida silvestre",
    "2C.27.4": "zona federal marítimo terrestre", "2C.27.5": "impacto ambiental",
    "2C.27.6": "organismos genéticamente modificados",
    "3S.1": "industria", "3S.2": "forestal", "3S.3": "vida silvestre",
    "3S.4": "impacto ambiental", "3S.5": "zona federal marítimo terrestre", "3S.6": "denuncias populares",
}
WILDLIFE_SERIES = {"2C.27.3", "3S.3"}

TERMS = load_codebook()


def series_of(expediente):
    """Serie del expediente, tolerante a puntos y diagonales faltantes (PFPA822C2710000520)."""
    compact = re.sub(r"[^0-9A-Z]", "", expediente.upper())
    m = re.search(r"2C27([1-6])", compact)
    if m:
        return f"2C.27.{m.group(1)}"
    m = re.search(r"3S([1-6])", compact)
    return f"3S.{m.group(1)}" if m else ""


def load_expedientes():
    """Número de expediente de cada PDF, según la bitácora de descargas."""
    with open(DOWNLOAD_LOG, encoding="utf-8") as f:
        return {Path(r["dest"]).stem: r["ruling_id"] for r in csv.DictReader(f)}


def classify(args):
    md_path, text_dir = args
    text = normalize(md_path.read_text(encoding="utf-8"))
    found = match_terms(text, TERMS, normalized=True)
    hits = []
    for term_id, occurrences in found.items():
        for start, end, matched, exact in occurrences:
            hits.append({
                "id_termino": term_id, "encontrado": matched, "exacta": int(exact),
                "contexto": text[max(0, start - CONTEXTO): end + CONTEXTO],
            })
    return md_path.relative_to(text_dir).with_suffix(".pdf").as_posix(), found, hits


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--perfil", default="estandar", help="carpeta de DATA_DIR/text a clasificar")
    parser.add_argument("--procesos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()

    (Path(__file__).parent / "CODEBOOK.md").write_text(codebook_markdown(TERMS), encoding="utf-8")

    text_dir = DATA_DIR / "text" / args.perfil
    md_files = sorted(text_dir.rglob("*.md"))
    print(f"{len(md_files)} documentos en {text_dir}")
    expedientes = load_expedientes()
    by_id = {t.id: t for t in TERMS}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, all_hits = [], []
    with Pool(args.procesos) as pool:
        for i, (pdf, found, hits) in enumerate(pool.imap(classify, [(p, text_dir) for p in md_files], chunksize=8), 1):
            expediente = expedientes.get(Path(pdf).stem, Path(pdf).parent.name)
            serie = series_of(expediente) or series_of(Path(pdf).parent.name)
            weights = [by_id[t].peso for t in found]
            row = {
                "pdf": pdf, "expediente": expediente, "anio": pdf.split("/")[0],
                "serie": serie, "materia_serie": SERIES.get(serie, ""),
                "serie_vida_silvestre": int(serie in WILDLIFE_SERIES),
                "puntaje": score(found, TERMS),
                "n_fuerte": weights.count("fuerte"), "n_medio": weights.count("medio"), "n_debil": weights.count("debil"),
                "terminos": " ".join(sorted(found)),
                "solo_con_errores_ocr": " ".join(sorted(t for t, h in found.items() if not any(x[3] for x in h))),
            }
            row["candidata"] = int(row["serie_vida_silvestre"] or row["puntaje"] >= UMBRAL)
            row.update({f"n_{t.id}": len(found.get(t.id, [])) for t in TERMS})
            rows.append(row)
            all_hits += [{"pdf": pdf, **h} for h in hits]
            if i % 500 == 0:
                print(f"  {i}/{len(md_files)}")

    def write(name, data, fields):
        with open(OUT_DIR / name, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)

    if rows:
        write(f"clasificacion_{args.perfil}.csv", rows, list(rows[0]))
    write(f"apariciones_{args.perfil}.csv", all_hits, ["pdf", "id_termino", "encontrado", "exacta", "contexto"])
    write(f"candidatas_{args.perfil}.csv", [{"pdf": f"raw/{r['pdf']}"} for r in rows if r["candidata"]], ["pdf"])

    n = sum(r["candidata"] for r in rows)
    print(f"Candidatas: {n} de {len(rows)}")
    print(f"  por serie de vida silvestre: {sum(r['serie_vida_silvestre'] for r in rows)}")
    print(f"  con puntaje >= {UMBRAL}: {sum(r['puntaje'] >= UMBRAL for r in rows)}")
    print(f"Resultados en {OUT_DIR}")


if __name__ == "__main__":
    main()
