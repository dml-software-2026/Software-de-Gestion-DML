"""Formato de fechas para lo que se imprime (#332).

El cliente pidió que en los PDF e impresiones las fechas salgan día/mes/año.
En la base hay fechas guardadas como texto ISO ('2026-11-13', a veces con
hora), como date/datetime, o vacías: este helper las pasa todas a
dd/mm/aaaa. También está registrado como filtro de Jinja (`|fecha`).
Las descargas en Excel ya salen así por su cuenta (services/excel.py, #312).
"""
from datetime import date, datetime


def fecha_ddmmaaaa(valor):
    """'2026-11-13', date(2026, 11, 13) o datetime(...) -> '13/11/2026'.
    None/vacío -> ''. Un texto que no es una fecha ISO se devuelve tal cual."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor).strip()
    try:
        return datetime.fromisoformat(texto[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return texto
