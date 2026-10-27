"""Compara cada opción de OCR contra las transcripciones de referencia.

Lee DATA_DIR/benchmark/referencias/<id>.txt y DATA_DIR/benchmark/salidas/<config>/<id>.md y
escribe en DATA_DIR/benchmark/:
    resultados_por_pagina.csv   una fila por página y configuración
    resultados_resumen.csv      promedios por configuración (y por estrato)

Medidas:
    cer          errores de carácter / caracteres de la referencia (texto completo, con
                 mayúsculas y acentos; sin marcas de Markdown ni HTML)
    cer_busqueda igual, sobre el texto como lo ve la búsqueda de términos (minúsculas, sin
                 acentos ni puntuación)
    recall_palabras, precision_palabras
                 proporción de palabras de la referencia que aparecen en la salida, y al revés,
                 sin importar el orden (no castiga encabezados o columnas en otro orden)
    recall_terminos
                 de los términos del libro de códigos presentes en la referencia, cuántos
                 encuentra la búsqueda (con tolerancia a errores) en la salida
    recall_terminos_exacto
                 igual, pero sin tolerancia a errores
    terminos_falsos
                 términos encontrados en la salida que no están en la referencia
En la referencia se quitan las marcas [testado] e [ilegible] y el prefijo "@@ " de
encabezados y pies (cer_cuerpo los excluye).

Uso (desde la raíz del repositorio):
    code/.venv/Scripts/python code/102_text_extraction/202_benchmark_scores.py
"""

import csv
import html
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from rapidfuzz.distance import Levenshtein

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "code" / "103_classification"))
from keywords import load_codebook, match_terms, normalize  # noqa: E402

load_dotenv(REPO_ROOT / ".env")
DATA_DIR = Path(os.environ["DATA_DIR"])
BENCH_DIR = DATA_DIR / "benchmark"
TERMS = load_codebook()

QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "«": '"', "»": '"', "–": "-", "—": "-"})


def clean_markup(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)   # imágenes de Markdown
    text = re.sub(r"[#*_`|>]+", " ", text)
    text = re.sub(r"\$\s*([^$]*?)\s*\$", r"\1", text)   # fórmulas en línea
    return text


def light(text):
    text = unicodedata.normalize("NFC", clean_markup(text)).translate(QUOTES)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def search_form(text):
    text = normalize(clean_markup(text))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip()


def reference_versions(raw):
    lines = raw.splitlines()
    full = "\n".join(l[3:] if l.startswith("@@ ") else l for l in lines)
    body = "\n".join(l for l in lines if not l.startswith("@@"))
    strip = lambda t: re.sub(r"\[(?:testado|ilegible)\]", " ", t)
    return strip(full), strip(body)


def cer(ref, hyp):
    return Levenshtein.distance(ref, hyp) / max(len(ref), 1)


def bag_scores(ref, hyp):
    r, h = Counter(ref.split()), Counter(hyp.split())
    common = sum((r & h).values())
    return common / max(sum(r.values()), 1), common / max(sum(h.values()), 1)


def main():
    with open(BENCH_DIR / "paginas.csv", encoding="utf-8") as f:
        strata = {r["id"]: r["estrato"] for r in csv.DictReader(f)}
    refs = {}
    for page_id in strata:
        path = BENCH_DIR / "referencias" / f"{page_id}.txt"
        if path.exists():
            refs[page_id] = reference_versions(path.read_text(encoding="utf-8"))
    times = {}
    times_path = BENCH_DIR / "salidas" / "tiempos.csv"
    if times_path.exists():
        with open(times_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                times[(r["config"], r["id"])] = float(r["segundos"])

    rows = []
    for config_dir in sorted(p for p in (BENCH_DIR / "salidas").iterdir() if p.is_dir()):
        for page_id, (ref_full, ref_body) in refs.items():
            out = config_dir / f"{page_id}.md"
            if not out.exists():
                continue
            hyp = out.read_text(encoding="utf-8")
            ref_terms = set(match_terms(ref_full, TERMS, fuzzy=False))
            hyp_terms = set(match_terms(hyp, TERMS, fuzzy=True))
            hyp_terms_exact = set(match_terms(hyp, TERMS, fuzzy=False))
            recall_w, precision_w = bag_scores(search_form(ref_full), search_form(hyp))
            rows.append({
                "config": config_dir.name, "id": page_id, "estrato": strata[page_id],
                "cer": round(cer(light(ref_full), light(hyp)), 4),
                "cer_cuerpo": round(cer(light(ref_body), light(hyp)), 4),
                "cer_busqueda": round(cer(search_form(ref_full), search_form(hyp)), 4),
                "recall_palabras": round(recall_w, 4), "precision_palabras": round(precision_w, 4),
                "terminos_ref": len(ref_terms),
                "terminos_encontrados": len(ref_terms & hyp_terms),
                "terminos_encontrados_exacto": len(ref_terms & hyp_terms_exact),
                "terminos_falsos": " ".join(sorted(hyp_terms - ref_terms)),
                "terminos_perdidos": " ".join(sorted(ref_terms - hyp_terms)),
                "segundos": times.get((config_dir.name, page_id), ""),
            })

    fields = list(rows[0])
    with open(BENCH_DIR / "resultados_por_pagina.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    def summarize(group, label):
        n_ref = sum(r["terminos_ref"] for r in group)
        secs = [r["segundos"] for r in group if r["segundos"] != ""]
        return {
            "config": label[0], "estrato": label[1], "paginas": len(group),
            "cer": round(statistics.mean(r["cer"] for r in group), 4),
            "cer_mediana": round(statistics.median(r["cer"] for r in group), 4),
            "cer_busqueda": round(statistics.mean(r["cer_busqueda"] for r in group), 4),
            "recall_palabras": round(statistics.mean(r["recall_palabras"] for r in group), 4),
            "precision_palabras": round(statistics.mean(r["precision_palabras"] for r in group), 4),
            "recall_terminos": round(sum(r["terminos_encontrados"] for r in group) / n_ref, 4) if n_ref else "",
            "recall_terminos_exacto": round(sum(r["terminos_encontrados_exacto"] for r in group) / n_ref, 4) if n_ref else "",
            "terminos_falsos": sum(len(r["terminos_falsos"].split()) for r in group),
            "segundos_mediana": round(statistics.median(secs), 2) if secs else "",
        }

    summary = []
    configs = sorted({r["config"] for r in rows})
    for c in configs:
        group = [r for r in rows if r["config"] == c]
        summary.append(summarize(group, (c, "todas")))
        for s in sorted({r["estrato"] for r in group}):
            summary.append(summarize([r for r in group if r["estrato"] == s], (c, s)))
    with open(BENCH_DIR / "resultados_resumen.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    print(f"{'config':<22}{'págs':>5}{'CER':>8}{'CER búsq':>10}{'recall pal':>11}{'recall térm':>12}{'falsos':>8}{'s/pág':>8}")
    for s in summary:
        if s["estrato"] == "todas":
            print(f"{s['config']:<22}{s['paginas']:>5}{s['cer']:>8.3f}{s['cer_busqueda']:>10.3f}"
                  f"{s['recall_palabras']:>11.3f}{str(s['recall_terminos']):>12}{s['terminos_falsos']:>8}{str(s['segundos_mediana']):>8}")


if __name__ == "__main__":
    main()
