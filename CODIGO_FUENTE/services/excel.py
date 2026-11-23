"""Descargas en Excel (.xlsx) (#312).

Antes eran CSV con comas y UTF-8 sin BOM: en un Excel en español se abrían
todo en una sola columna y con los acentos rotos. Un .xlsx real se abre bien
siempre, y de paso sale con encabezados en negrita, filtro automático, la
primera fila fija y fechas en día/mes/año.
"""
import re
from datetime import date, datetime
from io import BytesIO

from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FORMATO_FECHA = "DD/MM/YYYY"
_FECHA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
_ANCHO_MAX = 60


def _valor_celda(valor):
    """Fechas guardadas como texto ISO ('2026-11-13' o con hora) pasan a fecha
    real, así Excel las muestra dd/mm/aaaa y se pueden ordenar y filtrar."""
    if isinstance(valor, str) and _FECHA_ISO.match(valor):
        try:
            return datetime.fromisoformat(valor[:10]).date()
        except ValueError:
            return valor
    if isinstance(valor, datetime):
        return valor.date()
    return valor


def armar_xlsx(titulo_hoja, encabezados, filas):
    """Devuelve los bytes de un .xlsx con una hoja: encabezados en negrita,
    fila 1 fija, filtro automático y ancho de columnas ajustado al contenido."""
    wb = Workbook()
    ws = wb.active
    ws.title = titulo_hoja[:31]  # límite de Excel para el nombre de la hoja

    ws.append(list(encabezados))
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="343A40")

    anchos = [len(str(e)) for e in encabezados]
    for fila in filas:
        valores = [_valor_celda(v) for v in fila]
        ws.append(valores)
        for i, v in enumerate(valores):
            texto = v.strftime("%d/%m/%Y") if isinstance(v, date) else ("" if v is None else str(v))
            anchos[i] = max(anchos[i], len(texto))

    for fila in ws.iter_rows(min_row=2):
        for celda in fila:
            if isinstance(celda.value, date):
                celda.number_format = FORMATO_FECHA

    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(ancho + 2, _ANCHO_MAX)
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def respuesta_xlsx(nombre_base, titulo_hoja, encabezados, filas):
    """Respuesta de descarga: <nombre_base>_AAAAMMDD.xlsx."""
    contenido = armar_xlsx(titulo_hoja, encabezados, filas)
    nombre = f"{nombre_base}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(BytesIO(contenido), mimetype=MIME_XLSX, as_attachment=True, download_name=nombre)
