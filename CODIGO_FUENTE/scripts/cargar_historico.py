"""
cargar_historico.py

Carga historica de fichas DML a Postgres/Supabase (spec en descripciones-issues.md).
Reemplaza al intento manual anterior (IA + INSERTs sueltos): esto es reejecutable
e idempotente, sin paso SQL manual intermedio.

Uso:
    python cargar_historico.py maquinas.csv matriz.csv

Requiere DATABASE_URL (misma convencion que extensions.py). Dev primero, prod al final.

Politica de conflictos: ON CONFLICT DO NOTHING (skip). Corregir un registro ya
cargado = borrar manual en la BD + re-correr. No hay UPDATE automatico.
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv


import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no encontrada — revisá que exista el archivo .env en la raíz del repo")

COLS = [
    "item", "ficha_n", "cliente", "serie", "ingreso", "mes_salida", "salida",
    "modelo", "observacion", "reparacion", "repuestos", "n_ciclos",
    "facturar", "entregadas",
]

REPUESTO_RE = re.compile(r"([A-Za-z0-9]+)\s*\((\d+)\)")
REPUESTO_SIMPLE_RE = re.compile(r"^[A-Za-z0-9]+$")

# Columnas reales de estado_general (schema-postgres.sql). Cada ENUM ya
# incluye 'HISTORICO' como valor valido -> se puede insertar tal cual.
ESTADO_GENERAL_CAMPOS = [
    "estado_equipo", "carcaza", "cubre_feedwheel", "mango", "botones",
    "motor_arrastre", "motor_sellado", "cuchilla", "servo",
    "rueda_arrastre", "resorte_manija", "otros",
]


def get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL no esta seteada.\n"
            "    export DATABASE_URL=postgresql://usuario:pass@host:puerto/dbname\n",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return psycopg2.connect(database_url)
    except psycopg2.OperationalError as e:
        print(f"ERROR: no se pudo conectar a la base de datos: {e}", file=sys.stderr)
        sys.exit(1)


def cargar_matriz(matriz_csv):
    df = pd.read_csv(matriz_csv, encoding="utf-8")
    df.columns = [c.strip().lower() for c in df.columns]
    if "codigo_repuesto" not in df.columns and "codigo" in df.columns:
        df = df.rename(columns={"codigo": "codigo_repuesto"})
    return dict(zip(df["codigo_repuesto"].astype(str).str.upper().str.strip(), df["item"]))


def parse_fecha(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, (pd.Timestamp, datetime)):
        return valor.date() if isinstance(valor, datetime) else valor
    s = str(valor).strip()
    if not s or s.upper() == "HISTORICO":
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_repuestos(valor):
    """Soporta 'COD(cant) COD2(cant2)', saltos de linea, o codigos sueltos."""
    if pd.isna(valor):
        return []
    s = str(valor).strip()
    if not s:
        return []
    con_cantidad = REPUESTO_RE.findall(s)
    if con_cantidad:
        return [(cod.upper().strip(), int(cant)) for cod, cant in con_cantidad]
    partes = re.split(r"[\n\r]+", s)
    codigos = []
    for parte in partes:
        for token in parte.split():
            token = token.strip().upper()
            if REPUESTO_SIMPLE_RE.match(token):
                codigos.append((token, 1))
    return codigos


def validar_fila(row, matriz, fichas_vistas_csv):
    """Devuelve (valid, errors, data). Repuesto no encontrado en matriz = error."""
    errors = []

    ficha_raw = row.get("ficha_n")
    try:
        ficha_n = int(ficha_raw)
    except (ValueError, TypeError):
        return False, ["Ficha N vacia o invalida"], None

    if ficha_n in fichas_vistas_csv:
        return False, [f"Ficha N {ficha_n} duplicada dentro del mismo CSV"], None

    cliente = str(row.get("cliente")).strip() if not pd.isna(row.get("cliente")) else ""
    modelo = str(row.get("modelo")).strip() if not pd.isna(row.get("modelo")) else ""
    if not cliente:
        errors.append("Cliente vacio (NOT NULL)")
    if not modelo:
        errors.append("Modelo vacio (NOT NULL)")

    fecha_ingreso = parse_fecha(row.get("ingreso"))
    if fecha_ingreso is None:
        errors.append("Fecha de Ingreso invalida o faltante")

    fecha_egreso = parse_fecha(row.get("salida"))

    serie_raw = str(row.get("serie")).strip() if not pd.isna(row.get("serie")) else ""
    serie = serie_raw if serie_raw else f"HIST-{ficha_n}"

    repuestos = parse_repuestos(row.get("repuestos"))
    repuestos_resueltos = []
    for codigo, cantidad in repuestos:
        item = matriz.get(codigo)
        if item is None:
            errors.append(f"Codigo de repuesto '{codigo}' no encontrado en la matriz")
        else:
            repuestos_resueltos.append((codigo, item, cantidad))

    if errors:
        return False, errors, None

    entregadas = str(row.get("entregadas")).strip().upper() if not pd.isna(row.get("entregadas")) else ""
    estado_reparacion = "MAQUINA ENTREGADA" if entregadas in ("SI", "OK") else "A LA ESPERA DE REVISION"

    try:
        n_ciclos = int(row.get("n_ciclos")) if not pd.isna(row.get("n_ciclos")) else None
    except (ValueError, TypeError):
        n_ciclos = None

    data = {
        "ficha_n": ficha_n, "cliente": cliente, "modelo": modelo, "serie": serie,
        "fecha_ingreso": fecha_ingreso, "fecha_egreso": fecha_egreso,
        "observacion": None if pd.isna(row.get("observacion")) else str(row.get("observacion")).strip(),
        "reparacion": None if pd.isna(row.get("reparacion")) else str(row.get("reparacion")).strip(),
        "estado_reparacion": estado_reparacion, "n_ciclos": n_ciclos,
        "repuestos": repuestos_resueltos,
    }
    return True, [], data


def insertar_ficha(cur, data):
    """
    Idempotencia real: dml_fichas.numero_ficha es el UNIQUE del schema
    (raypac_entries.numero_serie NO tiene constraint). Por eso chequeamos
    existencia por numero_ficha ANTES de insertar nada, para no dejar un
    raypac_entries huerfano cuando la ficha ya existe de una corrida previa.
    """
    cur.execute("SELECT id FROM dml_fichas WHERE numero_ficha = %s", (data["ficha_n"],))
    if cur.fetchone() is not None:
        return False

    cur.execute(
        """
        INSERT INTO raypac_entries
            (fecha_recepcion, tipo_solicitud, cliente, numero_serie,
             modelo_maquina, tipo_maquina, comercial, mail_comercial)
        VALUES (%s, 'HISTORICO', %s, %s, %s, 'HISTORICO', 'HISTORICO', 'historico@dml.local')
        RETURNING id
        """,
        (data["fecha_ingreso"], data["cliente"], data["serie"], data["modelo"]),
    )
    raypac_id = cur.fetchone()["id"]

    cur.execute(
        """
        INSERT INTO dml_fichas
            (numero_ficha, raypac_id, fecha_ingreso, tecnico, observaciones,
             diagnostico_reparacion, estado_reparacion, n_ciclos,
             tecnico_resp, fecha_egreso)
        VALUES (%s, %s, %s, 'HISTORICO', %s, %s, %s, %s, 'HISTORICO', %s)
        ON CONFLICT (numero_ficha) DO NOTHING
        RETURNING id
        """,
        (
            data["ficha_n"], raypac_id, data["fecha_ingreso"], data["observacion"],
            data["reparacion"], data["estado_reparacion"], data["n_ciclos"], data["fecha_egreso"],
        ),
    )
    ficha_row = cur.fetchone()
    if ficha_row is None:
        return False  # carrera improbable, no dejamos hijos huerfanos

    ficha_id = ficha_row["id"]

    for codigo, descripcion, cantidad in data["repuestos"]:
        cur.execute(
            """
            INSERT INTO dml_repuestos
                (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (ficha_id, codigo, descripcion, cantidad, cantidad),
        )

    columnas = ", ".join(ESTADO_GENERAL_CAMPOS)
    placeholders = ", ".join(["%s"] * len(ESTADO_GENERAL_CAMPOS))
    valores = tuple("HISTORICO" for _ in ESTADO_GENERAL_CAMPOS)
    cur.execute(
        f"""
        INSERT INTO estado_general (ficha_id, {columnas})
        VALUES (%s, {placeholders})
        ON CONFLICT (ficha_id) DO NOTHING
        """,
        (ficha_id, *valores),
    )
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Carga historica DML desde CSVs.")
    parser.add_argument("maquinas_csv", help="CSV con las maquinas/fichas a cargar")
    parser.add_argument("matriz_csv", help="CSV con la matriz de repuestos (codigo_repuesto, item)")
    return parser.parse_args()


def main():
    args = parse_args()
    for path in (args.maquinas_csv, args.matriz_csv):
        if not os.path.isfile(path):
            print(f"ERROR: no se encontro el archivo '{path}'", file=sys.stderr)
            sys.exit(1)

    matriz = cargar_matriz(args.matriz_csv)
    print(f"[INFO] Matriz cargada: {len(matriz)} codigos de repuesto")

    try:
        df = pd.read_csv(args.maquinas_csv, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(args.maquinas_csv, encoding="cp1252")
    df.columns = [c.strip().lower() for c in df.columns]
    rename_map = {}
    for c in df.columns:
        if c.startswith("ficha"):
            rename_map[c] = "ficha_n"
        elif c.startswith("reparaci"):
            rename_map[c] = "reparacion"
        elif c.startswith("n") and "ciclos" in c:
            rename_map[c] = "n_ciclos"
    df = df.rename(columns=rename_map)

    conn = get_connection()
    procesados = insertados = skipped = 0
    error_rows = []
    fichas_vistas_csv = set()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            info_cur = conn.cursor(cursor_factory=RealDictCursor)
            info_cur.execute("SELECT current_database(), current_user;")
            info = info_cur.fetchone()
            print(f"[INFO] Conectado a '{info['current_database']}' como '{info['current_user']}'")
            info_cur.close()

            for idx, row in df.iterrows():
                procesados += 1
                csv_row_num = idx + 2

                valid, errors, data = validar_fila(row, matriz, fichas_vistas_csv)
                if not valid:
                    for err in errors:
                        error_rows.append({
                            "fila_csv": csv_row_num, "ficha_n": row.get("ficha_n"),
                            "columna": "ver_descripcion", "tipo_error": err,
                        })
                    continue

                fichas_vistas_csv.add(data["ficha_n"])
                try:
                    if insertar_ficha(cur, data):
                        conn.commit()
                        insertados += 1
                    else:
                        conn.commit()
                        skipped += 1
                except Exception as e:
                    conn.rollback()
                    error_rows.append({
                        "fila_csv": csv_row_num, "ficha_n": data["ficha_n"],
                        "columna": "insercion_bd", "tipo_error": f"Error al insertar: {e}",
                    })
    finally:
        conn.close()

    print(
        f"\n[RESUMEN] {procesados} registros procesados, {insertados} insertados, "
        f"{skipped} skipped (ya existian), {len(error_rows)} errores."
    )

    if error_rows:
        # Se guarda siempre junto a los CSV de entrada (misma carpeta que
        # maquinas_csv), no en el cwd desde donde se corre el script. Así
        # cae naturalmente dentro de scripts/data/, ya cubierto por el
        # patron errores_*.csv del .gitignore, sin importar desde donde
        # se invoque el comando.
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        carpeta_destino = os.path.dirname(os.path.abspath(args.maquinas_csv))
        error_filename = os.path.join(carpeta_destino, f"errores_{timestamp}.csv")
        with open(error_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["fila_csv", "ficha_n", "columna", "tipo_error"])
            writer.writeheader()
            writer.writerows(error_rows)
        print(f"[INFO] Errores guardados en: {error_filename}")


if __name__ == "__main__":
    main()