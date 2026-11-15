"""Carga masiva del stock de DML desde la planilla del cliente (#310).

La planilla es el Excel "STOCK DE REPUESTOS GENERAL" de DML: el encabezado
está en la fila que dice CODIGO en la columna C, y de ahí para abajo hay un
repuesto por fila (C = código, D = ítem, E = total, J = código de ubicación).
"""
import os

import openpyxl

from CODIGO_FUENTE.config import BASE_DIR
from CODIGO_FUENTE.services.ubicacion_fisica import normalizar_ubicacion_fisica

PLANILLA_STOCK = os.path.join(BASE_DIR, "DOCUMENTOS DML", "NUEVO STOCK DE REPUESTOS COMPLETO al 31-08-2026.xlsx")

COL_CODIGO, COL_ITEM, COL_TOTAL, COL_UBICACION = 2, 3, 4, 9  # C, D, E, J (desde 0)


def _texto(valor):
    return " ".join(str(valor).split()) if valor is not None else ""


def _cantidad(valor):
    """Entero >= 0, o None si la celda no es una cantidad válida (vacía, texto, decimal, negativa)."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, str):
        valor = valor.strip()
        if not valor.isdigit():
            return None
        valor = int(valor)
    if not isinstance(valor, int) or valor < 0:
        return None
    return valor


def leer_planilla_stock(ruta):
    """Lee la planilla y devuelve (filas, errores).

    filas: [{"fila", "codigo", "item", "cantidad", "ubicacion_fisica"}], una por repuesto.
    errores: [(fila, codigo, motivo)] de las filas que no se pueden cargar.
    Un 0 en el total es una cantidad válida: el repuesto está agotado.
    """
    hoja = openpyxl.load_workbook(ruta, read_only=True, data_only=True).worksheets[0]
    filas, errores, vistos = [], [], {}
    encabezado = False

    for numero_fila, valores in enumerate(hoja.iter_rows(values_only=True), start=1):
        valores = list(valores) + [None] * (COL_UBICACION + 1 - len(valores))
        codigo = _texto(valores[COL_CODIGO]).replace(" ", "").upper()
        if not encabezado:
            encabezado = codigo == "CODIGO"
            continue
        if not codigo:
            continue

        item = _texto(valores[COL_ITEM])
        cantidad = _cantidad(valores[COL_TOTAL])
        if not item:
            errores.append((numero_fila, codigo, "falta el ítem"))
        elif cantidad is None:
            errores.append((numero_fila, codigo, f"cantidad inválida: {valores[COL_TOTAL]!r}"))
        elif codigo in vistos:
            errores.append((numero_fila, codigo, f"código repetido (ya está en la fila {vistos[codigo]})"))
        else:
            vistos[codigo] = numero_fila
            filas.append({
                "fila": numero_fila,
                "codigo": codigo,
                "item": item,
                "cantidad": cantidad,
                "ubicacion_fisica": normalizar_ubicacion_fisica(valores[COL_UBICACION]),
            })

    if not encabezado:
        raise ValueError("No se encontró el encabezado (CODIGO en la columna C).")
    return filas, errores


def cargar_stock_dml(db, filas):
    """Pisa el stock de DML con las filas de la planilla, en la transacción de `db` (sin commit).

    - Código existente: actualiza ítem y cantidad en la matriz, y cantidad y ubicación física en DML.
    - Código nuevo: lo da de alta en la matriz y en el stock de DML.
    - Los códigos que no están en la planilla no se tocan.
    No dispara alertas ni mails: es el estado real del depósito, no un movimiento.
    Devuelve [(codigo, item, record_id, "nuevo" | "actualizado")].
    """
    resultados = []
    for f in filas:
        existente = db.execute(
            "SELECT id FROM matriz_repuestos WHERE codigo_repuesto = %s", (f["codigo"],)
        ).fetchone()
        if existente:
            db.execute(
                "UPDATE matriz_repuestos SET item = %s, cantidad_actual = %s, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = %s",
                (f["item"], f["cantidad"], existente["id"])
            )
            record_id, resultado = existente["id"], "actualizado"
        else:
            numero = db.execute("SELECT MAX(numero) AS max FROM matriz_repuestos").fetchone()["max"] or 0
            record_id = db.execute("""
                INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                VALUES (%s, %s, %s, %s, %s, 'DML')
                RETURNING id
            """, (numero + 1, f["codigo"], f["item"], f["cantidad"], f["cantidad"])).fetchone()["id"]
            resultado = "nuevo"

        actualizado = db.execute("""
            UPDATE stock_ubicaciones
            SET cantidad = %s, codigo_ubicacion_fisica = %s, updated_at = CURRENT_TIMESTAMP
            WHERE codigo_repuesto = %s AND ubicacion = 'DML'
            RETURNING id
        """, (f["cantidad"], f["ubicacion_fisica"], f["codigo"])).fetchone()
        if not actualizado:
            db.execute("""
                INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                VALUES (%s, 'DML', %s, %s)
            """, (f["codigo"], f["cantidad"], f["ubicacion_fisica"]))

        resultados.append((f["codigo"], f["item"], record_id, resultado))
    return resultados
