"""Búsqueda de los términos del libro de códigos (codebook.csv) en un texto.

El texto se normaliza antes de buscar: minúsculas, sin acentos, sin etiquetas HTML ni
marcas de Markdown, palabras cortadas al final de renglón unidas ("silves-\\ntre") y
espacios colapsados. Los patrones del libro de códigos se escriben sobre ese texto.

Cada término tiene:
    errores   letras equivocadas que se toleran (errores típicos de OCR). Solo frases largas.
    contexto  patrón que debe aparecer a menos de VENTANA caracteres para que cuente
    excluir   patrón que, si aparece a menos de VENTANA caracteres, anula esa aparición
"""

import csv
import html
import re as re_std
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import regex

CODEBOOK = Path(__file__).with_name("codebook.csv")
VENTANA = 150
PESOS = {"fuerte": 3, "medio": 2, "debil": 1}


@dataclass
class Term:
    id: str
    grupo: str
    termino: str
    patron: str
    peso: str
    errores: int
    contexto: str
    excluir: str
    fuente: str
    justificacion: str

    def __post_init__(self):
        exact = f"(?:{self.patron})"
        self.exact = regex.compile(exact)
        # fuzzy: primero se busca la forma exacta y solo si no aparece se aceptan errores
        self.fuzzy = regex.compile(f"(?:{self.patron}){{e<={self.errores}}}") if self.errores else None
        self.context_re = regex.compile(self.contexto) if self.contexto else None
        self.exclude_re = regex.compile(self.excluir) if self.excluir else None

    def _valid(self, text, start, end):
        window = text[max(0, start - VENTANA): end + VENTANA]
        if self.context_re and not self.context_re.search(window):
            return False
        if self.exclude_re and self.exclude_re.search(window):
            return False
        return True

    def find(self, text, fuzzy=True):
        """Apariciones válidas: lista de (inicio, fin, texto encontrado, exacta)."""
        hits = [(m.start(), m.end(), m.group(), True) for m in self.exact.finditer(text)
                if self._valid(text, m.start(), m.end())]
        if not hits and fuzzy and self.fuzzy is not None:
            hits = [(m.start(), m.end(), m.group(), False) for m in self.fuzzy.finditer(text)
                    if self._valid(text, m.start(), m.end())]
        return hits


def load_codebook(path=CODEBOOK):
    with open(path, encoding="utf-8") as f:
        return [Term(**{**row, "errores": int(row["errores"] or 0)}) for row in csv.DictReader(f)]


TAG = re_std.compile(r"<[^>]+>")
MARKDOWN = re_std.compile(r"[#*_`|>\[\]]+")


def normalize(text):
    text = html.unescape(TAG.sub(" ", text))
    text = MARKDOWN.sub(" ", text)
    text = re_std.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re_std.sub(r"\s+", " ", text).strip()


def match_terms(text, terms, fuzzy=True, normalized=False):
    """Diccionario id -> lista de apariciones válidas (solo términos encontrados)."""
    text = text if normalized else normalize(text)
    found = {}
    for term in terms:
        hits = term.find(text, fuzzy=fuzzy)
        if hits:
            found[term.id] = hits
    return found


def score(found, terms):
    """Puntaje: suma del peso de cada término distinto encontrado."""
    by_id = {t.id: t for t in terms}
    return sum(PESOS[by_id[i].peso] for i in found)


def codebook_markdown(terms):
    """Tabla legible del libro de códigos (CODEBOOK.md)."""
    lines = [
        "# Libro de códigos de términos de búsqueda",
        "",
        "Archivo generado desde `codebook.csv` por `103_classify.py`. Para cambiar un término se edita el CSV.",
        "",
        "Los patrones se aplican sobre el texto normalizado (minúsculas, sin acentos, espacios colapsados).",
        f"`contexto` y `excluir` se buscan a menos de {VENTANA} caracteres de cada aparición.",
        "`errores` es el número de letras equivocadas que se toleran por errores de OCR.",
        f"Pesos: {', '.join(f'{k} = {v}' for k, v in PESOS.items())}. El puntaje de una resolución es la suma del peso de cada término distinto encontrado.",
        "Entre paréntesis en `fuente`: número de resoluciones, de 1,594 con texto embebido, que contenían el término en la exploración inicial.",
        "",
    ]
    groups = {}
    for t in terms:
        groups.setdefault(t.grupo, []).append(t)
    for grupo, items in groups.items():
        lines += [f"## {grupo.replace('_', ' ').capitalize()}", "",
                  "| id | término | peso | errores | patrón | contexto | excluir | fuente | justificación |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for t in items:
            cells = [t.id, t.termino, t.peso, str(t.errores), f"`{t.patron}`",
                     f"`{t.contexto}`" if t.contexto else "", f"`{t.excluir}`" if t.excluir else "",
                     t.fuente, t.justificacion]
            lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        lines.append("")
    return "\n".join(lines)
