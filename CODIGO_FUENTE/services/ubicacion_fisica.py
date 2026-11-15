"""#309: lugar físico del repuesto en el depósito de DML (ej. "E05-F05-B02").

Es la columna stock_ubicaciones.codigo_ubicacion_fisica; no confundir con
stock_ubicaciones.ubicacion, que es la empresa ("DML"/"RAYPAC").

Sin dependencias a propósito: lo usan el listado de stock, la carga masiva
por CSV, el seed y la migración que acomoda los valores ya cargados.
"""
import re

SIN_UBICACION = "SIN UBICACIÓN"
UBICACION_FISICA_MAX = 100

# Formato que usa DML en su planilla de stock (al 31/08/2026, 269 de 271
# códigos): Estante-Fila[-Posición A/B][-Box], ej. E05-F05-B02,
# E01-F04-PB-B02, E05-F04. En la planilla aparece con espacios sueltos
# ("E05 -F04 "), así que se compara sin espacios y con los guiones opcionales.
_PATRON_UBICACION = re.compile(r"^E(\d{1,2})(?:-?F(\d{1,2}))?(?:-?P([A-Z]))?(?:-?B(\d{1,2}))?$")


def normalizar_ubicacion_fisica(texto):
    """Texto libre -> forma guardada.

    - Si tiene la forma del código de DML, se guarda armado igual que en la
      planilla y sin espacios: "e5 - f4 - pb - b2" -> "E05-F04-PB-B02".
    - Si no (ej. "USO TALLER"), se guarda tal cual, en mayúscula, sin
      espacios de más ni pegados a los guiones ("E03 -F06 -P -" ->
      "E03-F06-P-"): es texto libre a propósito para no trabar casos
      especiales.
    - Vacío queda como SIN_UBICACION (pendiente de cargar).
    """
    limpio = " ".join((texto or "").split()).upper()
    if not limpio:
        return SIN_UBICACION
    m = _PATRON_UBICACION.match(limpio.replace(" ", ""))
    if not m:
        return re.sub(r"\s*-\s*", "-", limpio)
    estante, fila, posicion, box = m.groups()
    partes = [f"E{int(estante):02d}"]
    if fila:
        partes.append(f"F{int(fila):02d}")
    if posicion:
        partes.append(f"P{posicion}")
    if box:
        partes.append(f"B{int(box):02d}")
    return "-".join(partes)
