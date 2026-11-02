"""Une las clasificaciones de los dos perfiles de texto en una sola tabla.

Para las resoluciones que pasaron por la segunda pasada de OCR (perfil alta, 300 ppp) se usa
esa clasificación. Para las demás se usa la del perfil estandar (200 ppp). Lee de
DATA_DIR/classification/intermedios/ (salida de 103_classify.py con cada perfil).

Escribe en DATA_DIR/classification/:
    clasificacion_final.csv          una fila por resolución. Mismas columnas que
                                     clasificacion_<perfil>.csv, con las de uso más frecuente
                                     al principio, más perfil_texto, candidata_estandar y
                                     enlace_dropbox (de 103c_dropbox_links.py, si ya se corrió)
    clasificacion_final.xlsx         la misma tabla con formato (encabezado y columna pdf fijos,
                                     filtros, candidatas resaltadas, vínculo de Dropbox a cada PDF) y dos
                                     hojas más: diccionario de datos y términos de búsqueda
y en DATA_DIR/classification/intermedios/:
    apariciones_final.csv            apariciones de términos, del mismo perfil que cada fila
    candidatas_final.csv             PDF candidatos (universo de vida silvestre)
    candidatas_cautiverio_final.csv  PDF candidatos de cautiverio
    candidatas_cautiverio_bienestar_final.csv  PDF candidatos de cautiverio con 2 o más términos
                                     de bienestar
Además regenera code/103_classification/CODEBOOK.md. Las columnas se describen en
diccionario.csv.

Uso (desde la raíz del repositorio, después de correr 103_classify.py con estandar y alta):
    code/.venv/Scripts/python code/103_classification/103b_combine.py
"""

import csv
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).parent))
from keywords import CODEBOOK, codebook_markdown, load_codebook, load_dictionary  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
OUT_DIR = DATA_DIR / "classification"
TMP_DIR = OUT_DIR / "intermedios"
ENLACES = TMP_DIR / "enlaces_dropbox.csv"

PERFILES = ["alta", "estandar"]   # en orden de preferencia
PRIMERAS = ["pdf", "enlace_dropbox", "expediente", "anio", "candidata", "candidata_cautiverio", "candidata_cautiverio_bienestar"]

ENCABEZADO = PatternFill("solid", fgColor="1F4E78")
RESALTE = PatternFill("solid", fgColor="E2EFDA")


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def format_sheet(ws, widths, wrap=False):
    """Encabezado fijo con estilo, filtros y anchos de columna."""
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = ENCABEZADO
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[1].height = 30
    ws.auto_filter.ref = ws.dimensions
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    if wrap:
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")


def width(series, name, lo=8, hi=50):
    largo = max([len(name)] + [len(str(v)) for v in series.dropna().head(2000)])
    return max(lo, min(hi, largo + 2))


def write_excel(path, data, columns):
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        data.to_excel(xl, sheet_name="clasificacion", index=False)
        pd.DataFrame(columns).to_excel(xl, sheet_name="diccionario", index=False)
        pd.read_csv(CODEBOOK, dtype=str).to_excel(xl, sheet_name="terminos", index=False)

        ws = xl.sheets["clasificacion"]
        format_sheet(ws, [7 if c.startswith("n_") and c[2:3].isupper() else width(data[c], c) for c in data.columns])
        ws.freeze_panes = "B2"
        for col in ("candidata", "candidata_cautiverio", "candidata_cautiverio_bienestar"):
            letra = get_column_letter(data.columns.get_loc(col) + 1)
            ws.conditional_formatting.add(f"{letra}2:{letra}{len(data) + 1}",
                                          FormulaRule(formula=[f"{letra}2=1"], fill=RESALTE))
        # vínculo de Dropbox en la columna pdf. Sin él, vínculo relativo (el Excel está en
        # classification/ y los PDF en raw/)
        enlaces = data["enlace_dropbox"].fillna("").tolist()
        for cell, enlace in zip(ws["A"][1:], enlaces):
            cell.hyperlink = enlace or f"../raw/{cell.value}"
            cell.font = Font(color="0563C1", underline="single")
        ws.column_dimensions["B"].width = 14

        ws = xl.sheets["diccionario"]
        format_sheet(ws, [26, 12, 80, 40], wrap=True)
        ws.freeze_panes = "B2"

        ws = xl.sheets["terminos"]
        format_sheet(ws, [6, 18, 35, 40, 9, 8, 25, 25, 25, 60, 15], wrap=True)
        ws.freeze_panes = "D2"


def main():
    tablas = {p: read(TMP_DIR / f"clasificacion_{p}.csv") for p in PERFILES}
    estandar = {r["pdf"]: r["candidata"] for r in tablas["estandar"]}
    enlaces = {r["pdf"]: r["enlace_dropbox"] for r in read(ENLACES)} if ENLACES.exists() else {}

    rows, origen = [], {}
    for perfil in PERFILES:
        for r in tablas[perfil]:
            if r["pdf"] in origen:
                continue
            origen[r["pdf"]] = perfil
            rows.append({**r, "perfil_texto": perfil, "candidata_estandar": estandar.get(r["pdf"], ""),
                         "enlace_dropbox": enlaces.get(r["pdf"], "")})
    rows.sort(key=lambda r: r["pdf"])
    fields = PRIMERAS + [c for c in rows[0] if c not in PRIMERAS]

    hits = []
    for perfil in PERFILES:
        hits += [h for h in read(TMP_DIR / f"apariciones_{perfil}.csv") if origen.get(h["pdf"]) == perfil]
    hits.sort(key=lambda h: h["pdf"])

    write(OUT_DIR / "clasificacion_final.csv", rows, fields)
    write(TMP_DIR / "apariciones_final.csv", hits, list(hits[0]))
    write(TMP_DIR / "candidatas_final.csv", [{"pdf": f"raw/{r['pdf']}"} for r in rows if r["candidata"] == "1"], ["pdf"])
    for col in ("candidata_cautiverio", "candidata_cautiverio_bienestar"):
        write(TMP_DIR / f"{col.replace('candidata', 'candidatas')}_final.csv",
              [{"pdf": f"raw/{r['pdf']}"} for r in rows if r[col] == "1"], ["pdf"])

    columns = load_dictionary()
    faltan = [c for c in fields if c not in {d["columna"] for d in columns} and not c.startswith("n_")]
    if faltan:
        print(f"Columnas sin descripción en diccionario.csv: {' '.join(faltan)}")
    (Path(__file__).parent / "CODEBOOK.md").write_text(codebook_markdown(load_codebook(), columns), encoding="utf-8")
    data = pd.read_csv(OUT_DIR / "clasificacion_final.csv", dtype={"subunidad": "Int64", "oficina": "Int64",
                                                                    "numero_caso": "Int64", "anio_apertura": "Int64"})
    write_excel(OUT_DIR / "clasificacion_final.xlsx", data, columns)

    n = {p: sum(v == p for v in origen.values()) for p in PERFILES}
    print(f"{len(rows)} resoluciones: {n['alta']} con texto de 300 ppp, {n['estandar']} con texto de 200 ppp")
    print(f"Candidatas: {sum(r['candidata'] == '1' for r in rows)}")
    print(f"  dejaron de serlo con 300 ppp: "
          f"{sum(r['candidata'] == '0' and r['candidata_estandar'] == '1' for r in rows)}")
    print(f"Candidatas de cautiverio: {sum(r['candidata_cautiverio'] == '1' for r in rows)}")
    print(f"  con 2 o más términos de bienestar: {sum(r['candidata_cautiverio_bienestar'] == '1' for r in rows)}")
    print(f"Con vínculo de Dropbox: {sum(bool(r['enlace_dropbox']) for r in rows)}")
    print(f"Resultados en {OUT_DIR}")


if __name__ == "__main__":
    main()
