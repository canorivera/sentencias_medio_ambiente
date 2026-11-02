"""Lectura de las partes del número de expediente de PROFEPA.

Ejemplo: PFPA/25.3/2C.27.3/0021-19
    25      oficina (25 = Nuevo León)
    .3      subunidad dentro de la oficina (sin fuente oficial: se registra sin interpretar)
    2C.27.3 serie del cuadro de clasificación archivística (2C = asuntos jurídicos,
            27 = procedimientos administrativos, .3 = vida silvestre)
    0021    número del caso
    19      año de apertura del expediente

Fuentes de la serie: Guía simple de archivos de PROFEPA (2018) para 2C.27.x y Guía de
archivo documental (2026) para 3S.x. La clave de cada oficina no tiene lista oficial
publicada: se dedujo cruzando el número con el área responsable en el catálogo
(octubre de 2026). Los estados siguen el orden alfabético antiguo ("ch" después de "c").

La mitad del catálogo escribe el expediente sin separadores (PFPA2532C273002119) y hay
errores de captura, así que la lectura es tolerante y marca qué tan completa fue.
"""

import re

SERIES = {
    "2C.27.1": "industria", "2C.27.2": "forestal", "2C.27.3": "vida silvestre",
    "2C.27.4": "zona federal marítimo terrestre", "2C.27.5": "impacto ambiental",
    "2C.27.6": "organismos genéticamente modificados",
    "3S.1": "industria", "3S.2": "forestal", "3S.3": "vida silvestre",
    "3S.4": "impacto ambiental", "3S.5": "zona federal marítimo terrestre", "3S.6": "denuncias populares",
}

OFICINAS = {
    3: "Oficinas centrales: puertos, aeropuertos y fronteras / sustancias peligrosas",
    4: "Oficinas centrales: inspección y vigilancia de vida silvestre, recursos marinos y ecosistemas costeros",
    8: "Aguascalientes", 9: "Baja California", 10: "Baja California Sur", 11: "Campeche",
    12: "Coahuila", 13: "Colima", 14: "Chiapas", 15: "Chihuahua", 16: "Durango",
    17: "Estado de México", 18: "Guanajuato", 19: "Guerrero", 20: "Hidalgo", 21: "Jalisco",
    22: "Michoacán", 23: "Morelos", 24: "Nayarit", 25: "Nuevo León", 26: "Oaxaca",
    27: "Puebla", 28: "Querétaro", 29: "Quintana Roo", 30: "San Luis Potosí", 31: "Sinaloa",
    32: "Sonora", 33: "Tabasco", 34: "Tamaulipas", 35: "Tlaxcala", 36: "Veracruz",
    37: "Yucatán", 38: "Zacatecas", 39: "Zona Metropolitana del Valle de México",
}

SEPARADO = re.compile(
    r"PFPA\W*(\d{1,2})\W?(\d)\W+(?:2C\W?27\W?(?P<s2c>\d)|3\W?S\W?(?P<s3s>\d))\W+(?P<num>\d+)\W+(?P<anio>\d{2,4})\b")
COMPACTO = re.compile(r"PFPA(\d{1,2})(\d)(?:2C27(?P<s2c>\d)|3S(?P<s3s>\d))(?P<resto>\d+)$")


def _anio(texto):
    """Año de 2 o 4 dígitos, si es plausible (2005 a 2029)."""
    n = int(texto)
    n = n + 2000 if n < 100 else n
    return n if 2005 <= n <= 2029 else None


def parse(expediente):
    """Diccionario con las partes del expediente. `expediente_legible`: completo (todas las
    partes), parcial (al menos la serie) o no."""
    vacio = {"oficina": "", "entidad": "", "subunidad": "", "esquema": "", "serie": "", "materia_serie": "",
             "numero_caso": "", "anio_apertura": "", "expediente_legible": "no"}
    texto = expediente.upper().replace(" ", "")
    oficina = subunidad = serie = numero = anio = None
    m = SEPARADO.search(texto)
    if m:
        oficina, subunidad = int(m.group(1)), m.group(2)
        serie = f"2C.27.{m['s2c']}" if m["s2c"] else f"3S.{m['s3s']}"
        numero, anio = m["num"].lstrip("0") or "0", _anio(m["anio"])
    else:
        m = COMPACTO.search(re.sub(r"[^0-9A-Z]", "", texto))
        if m:
            oficina, subunidad = int(m.group(1)), m.group(2)
            serie = f"2C.27.{m['s2c']}" if m["s2c"] else f"3S.{m['s3s']}"
            resto = m["resto"]
            # el año va al final, con 4 dígitos (2024) o con 2 (24)
            if len(resto) >= 7 and resto[-4:-2] == "20" and _anio(resto[-4:]):
                numero, anio = resto[:-4], _anio(resto[-4:])
            elif len(resto) >= 3:
                numero, anio = resto[:-2], _anio(resto[-2:])
            numero = (numero or "").lstrip("0") or None
    if serie is None:
        # al menos la serie, aunque el resto no se lea
        compacto = re.sub(r"[^0-9A-Z]", "", texto)
        m = re.search(r"2C27([1-6])", compacto) or re.search(r"3S([1-6])", compacto)
        if not m:
            return vacio
        serie = f"2C.27.{m.group(1)}" if m.re.pattern.startswith("2C") else f"3S.{m.group(1)}"
    if oficina is not None and oficina not in OFICINAS:
        oficina = None
    completo = all(x is not None for x in (oficina, subunidad, numero, anio))
    return {
        "oficina": oficina if oficina is not None else "",
        "entidad": OFICINAS.get(oficina, ""),
        "subunidad": subunidad or "",
        "esquema": serie.split(".")[0],
        "serie": serie,
        "materia_serie": SERIES.get(serie, ""),
        "numero_caso": numero or "",
        "anio_apertura": anio or "",
        "expediente_legible": "completo" if completo else "parcial",
    }
