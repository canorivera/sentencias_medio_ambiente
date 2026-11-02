"""Clasifica las resoluciones según los términos del libro de códigos y el expediente.

Lee el texto de DATA_DIR/text/<perfil>/ (salida de 102b_extract_text.py) y escribe en
DATA_DIR/classification/:
    clasificacion_<perfil>.csv   una fila por resolución (columnas abajo)
    apariciones_<perfil>.csv     cada aparición de cada término con su contexto, para revisar
                                 por qué se marcó una resolución
    candidatas_<perfil>.csv      lista de PDF candidatos (entrada de la segunda pasada de OCR)
Además regenera code/103_classification/CODEBOOK.md desde codebook.csv.

Columnas de clasificacion_<perfil>.csv:
    expediente y sus partes (expediente.py): oficina, entidad, subunidad, esquema, serie,
        materia_serie, numero_caso, anio_apertura, expediente_legible
    anio (de la resolución) y anios_hasta_resolucion (anio menos anio_apertura)
    del catálogo de PROFEPA: tipo_resolucion_catalogo, sentido_catalogo, organo_catalogo
    asunto (lo que dice el renglón "ASUNTO:" de la primera página) y tipo_documento
        (resolución, acuerdo de cierre, otro acuerdo, no identificado)
    puntaje, n_fuerte, n_medio, n_debil, terminos, solo_con_errores_ocr
    candidata (universo de vida silvestre)
    establecimientos (términos de la capa establecimiento), n_bienestar (términos distintos
        de la capa bienestar) y candidata_cautiverio
    n_<id> por cada término del libro de códigos

Reglas:
    candidata               serie de vida silvestre (2C.27.3 o 3S.3) o puntaje de UMBRAL o más
    candidata_cautiverio    candidata y al menos un término de establecimiento (zoológico,
                            acuario, UMA, PIMVS, delfinario, circo, cautiverio...). No exige
                            términos de bienestar: el ejemplo de la propuesta (zoológico La
                            Pastora, PFPA/25.3/2C.27.3/0021-19) no tiene ninguno.
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
import expediente as exp  # noqa: E402
from keywords import codebook_markdown, load_codebook, match_terms, normalize, score  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
OUT_DIR = DATA_DIR / "classification"
DOWNLOAD_LOG = DATA_DIR / "logs" / "download_log.csv"
CATALOGUE_DIR = DATA_DIR / "catalogue"

UMBRAL = 6
CONTEXTO = 80
WILDLIFE_SERIES = {"2C.27.3", "3S.3"}
CAT_URL = "Hipervínculo a la resolución en versión pública"

TERMS = load_codebook()
ASUNTO = re.compile(r"asunto\s*:\s*(.{5,90})")
# Cierre del expediente o del procedimiento (no "cierre del acta de inspección")
CIERRE = re.compile(r"acuerdo de cierre|decreta el cierre|cierre (?:del?|de la) (?:presente )?(?:expediente|procedimiento)|cierre no\.?\s*\d|^cierre")
ASUNTO_FIN = re.compile(r"\s(?:al c|a la c|exp|oficio|presente|inspeccionad|c\.|domicilio|ciudad)")


def document_type(text):
    """Asunto de la primera página y tipo de documento."""
    head = text[:4000]
    m = ASUNTO.search(head)
    asunto = ASUNTO_FIN.split(m.group(1))[0].strip(" .,:") if m else ""
    asunto = re.sub(r"\s+(?:al|a la|a|de|del|en)$", "", asunto)
    base = asunto or head
    if CIERRE.search(base):
        tipo = "acuerdo de cierre"
    elif "resolucion" in base or "resuelve" in base:
        tipo = "resolución"
    elif asunto.startswith("acuerdo"):
        tipo = "otro acuerdo"
    else:
        tipo = "no identificado"
    return asunto, tipo


def load_metadata():
    """Expediente y datos del catálogo de cada PDF (por la URL de descarga)."""
    catalogue = {}
    for csv_path in CATALOGUE_DIR.glob("*.csv"):
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                url = row[CAT_URL].strip().rstrip("}").strip()
                catalogue.setdefault((csv_path.name, url), {
                    "tipo_resolucion_catalogo": row["Tipo de resolución"].strip(),
                    "sentido_catalogo": row["Sentido de la resolución"].strip(),
                    "organo_catalogo": row["Órgano que emite la resolución"].strip(),
                })
    metadata = {}
    with open(DOWNLOAD_LOG, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            # clave: carpeta y nombre sin extensión; "pdf" guarda la ruta real (hay .PDF en mayúsculas)
            pdf = Path(r["dest"]).relative_to("raw")
            metadata.setdefault(pdf.with_suffix("").as_posix(), {
                "pdf": pdf.as_posix(), "expediente": r["ruling_id"], **catalogue.get((r["catalogue"], r["url"]), {}),
            })
    return metadata


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
    asunto, tipo = document_type(text)
    return md_path.relative_to(text_dir).with_suffix(".pdf").as_posix(), found, hits, asunto, tipo


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--perfil", default="estandar", help="carpeta de DATA_DIR/text a clasificar")
    parser.add_argument("--procesos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()

    (Path(__file__).parent / "CODEBOOK.md").write_text(codebook_markdown(TERMS), encoding="utf-8")

    text_dir = DATA_DIR / "text" / args.perfil
    md_files = sorted(text_dir.rglob("*.md"))
    print(f"{len(md_files)} documentos en {text_dir}")
    metadata = load_metadata()
    by_id = {t.id: t for t in TERMS}
    establishment = {t.id for t in TERMS if t.capa == "establecimiento"}
    welfare = {t.id for t in TERMS if t.capa == "bienestar"}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, all_hits = [], []
    with Pool(args.procesos) as pool:
        work = [(p, text_dir) for p in md_files]
        for i, (pdf, found, hits, asunto, tipo) in enumerate(pool.imap(classify, work, chunksize=8), 1):
            meta = metadata.get(Path(pdf).with_suffix("").as_posix(), {"expediente": Path(pdf).parent.name})
            pdf = meta.get("pdf", pdf)
            parts = exp.parse(meta["expediente"])
            if parts["expediente_legible"] == "no":
                parts = exp.parse(Path(pdf).parent.name)   # el nombre de la carpeta a veces se lee mejor
            year = pdf.split("/")[0]
            weights = [by_id[t].peso for t in found]
            row = {
                "pdf": pdf, "expediente": meta["expediente"], **parts, "anio": year,
                "anios_hasta_resolucion": int(year) - parts["anio_apertura"]
                if year.isdigit() and parts["anio_apertura"] else "",
                "tipo_resolucion_catalogo": meta.get("tipo_resolucion_catalogo", ""),
                "sentido_catalogo": meta.get("sentido_catalogo", ""),
                "organo_catalogo": meta.get("organo_catalogo", ""),
                "asunto": asunto, "tipo_documento": tipo,
                "puntaje": score(found, TERMS),
                "n_fuerte": weights.count("fuerte"), "n_medio": weights.count("medio"), "n_debil": weights.count("debil"),
                "terminos": " ".join(sorted(found)),
                "solo_con_errores_ocr": " ".join(sorted(t for t, h in found.items() if not any(x[3] for x in h))),
            }
            row["candidata"] = int(parts["serie"] in WILDLIFE_SERIES or row["puntaje"] >= UMBRAL)
            row["establecimientos"] = " ".join(sorted(set(found) & establishment))
            row["n_bienestar"] = len(set(found) & welfare)
            row["candidata_cautiverio"] = int(row["candidata"] and bool(row["establecimientos"]))
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

    print(f"Candidatas: {sum(r['candidata'] for r in rows)} de {len(rows)}")
    print(f"  por serie de vida silvestre: {sum(r['serie'] in WILDLIFE_SERIES for r in rows)}")
    print(f"  con puntaje >= {UMBRAL}: {sum(r['puntaje'] >= UMBRAL for r in rows)}")
    print(f"Candidatas de cautiverio: {sum(r['candidata_cautiverio'] for r in rows)}")
    print(f"Expedientes legibles: completo {sum(r['expediente_legible'] == 'completo' for r in rows)}, "
          f"parcial {sum(r['expediente_legible'] == 'parcial' for r in rows)}, "
          f"no {sum(r['expediente_legible'] == 'no' for r in rows)}")
    print(f"Resultados en {OUT_DIR}")


if __name__ == "__main__":
    main()
