"""Carga masiva del stock de DML desde la planilla del cliente (#310).

La planilla es el Excel "STOCK DE REPUESTOS GENERAL" de DML: el encabezado
está en la fila que dice CODIGO en la columna C, y de ahí para abajo hay un
repuesto por fila (C = código, D = ítem, E = total, J = código de ubicación).
"""
import os

import openpyxl
from psycopg2.extras import RealDictCursor, execute_values

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

    Todo va en bloque (unas pocas consultas en total, no varias por repuesto):
    en Render cada consulta a Supabase tarda ~0,2 s, y repuesto por repuesto la
    carga pasaba de los 30 s que permite gunicorn y se cortaba.
    """
    if not filas:
        return []
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, codigo_repuesto FROM matriz_repuestos WHERE codigo_repuesto = ANY(%s)",
                ([f["codigo"] for f in filas],))
    ids = {r["codigo_repuesto"]: r["id"] for r in cur.fetchall()}
    existentes = [f for f in filas if f["codigo"] in ids]
    nuevas = [f for f in filas if f["codigo"] not in ids]

    if existentes:
        execute_values(cur, """
            UPDATE matriz_repuestos AS m
            SET item = v.item, cantidad_actual = v.cantidad, updated_at = CURRENT_TIMESTAMP
            FROM (VALUES %s) AS v(codigo, item, cantidad)
            WHERE m.codigo_repuesto = v.codigo
        """, [(f["codigo"], f["item"], f["cantidad"]) for f in existentes], page_size=len(existentes))

    if nuevas:
        cur.execute("SELECT COALESCE(MAX(numero), 0) AS max FROM matriz_repuestos")
        numero = cur.fetchone()["max"]
        insertadas = execute_values(cur, """
            INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
            VALUES %s
            RETURNING id, codigo_repuesto
        """, [(numero + i, f["codigo"], f["item"], f["cantidad"], f["cantidad"], "DML")
              for i, f in enumerate(nuevas, start=1)], page_size=len(nuevas), fetch=True)
        ids.update({r["codigo_repuesto"]: r["id"] for r in insertadas})

    execute_values(cur, """
        INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
        VALUES %s
        ON CONFLICT (codigo_repuesto, ubicacion) DO UPDATE
        SET cantidad = EXCLUDED.cantidad, codigo_ubicacion_fisica = EXCLUDED.codigo_ubicacion_fisica,
            updated_at = CURRENT_TIMESTAMP
    """, [(f["codigo"], "DML", f["cantidad"], f["ubicacion_fisica"]) for f in filas], page_size=len(filas))
    cur.close()

    codigos_nuevos = {f["codigo"] for f in nuevas}
    return [(f["codigo"], f["item"], ids[f["codigo"]], "nuevo" if f["codigo"] in codigos_nuevos else "actualizado")
            for f in filas]
