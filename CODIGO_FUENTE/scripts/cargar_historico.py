"""
cargar_historico.py

Carga histórica de fichas DML a Postgres desde la planilla interna del
cliente (#76, reescrito en el #383).

Uso (desde la raíz del repo):
    python -m CODIGO_FUENTE.scripts.cargar_historico PLANILLA.xlsx --dry-run
    python -m CODIGO_FUENTE.scripts.cargar_historico PLANILLA.xlsx

Acepta el .xlsx del cliente (hoja "Total", encabezados en la fila 2) o un
.csv con los mismos encabezados. Requiere DATABASE_URL (en .env o en el
entorno). Orden: local -> dev -> prod.

Criterio del cliente (2026-11-23): "si falta algún dato, cárguenla igual".
Nada se descarta por un dato faltante o raro; lo que no entra en su columna
queda anotado en las observaciones de la ficha:
- fecha de ingreso vacía o ilegible -> se usa la de salida (y al revés);
- modelo vacío -> 'HISTORICO'; serie vacía -> 'HIST-<ficha>';
- N° de ficha con texto ("754 EX 717") -> 754, el resto va a observaciones;
- código de repuesto que no está en matriz_repuestos -> no se carga como
  repuesto, queda anotado en observaciones;
- N° de ciclos no numérico ("MANUAL") -> vacío, el texto va a observaciones.
Solo se saltea una fila si no tiene N° de ficha o no tiene ninguna fecha.

Reejecutable: si el N° de ficha ya existe no se toca. Si la que existe la
creó la app (no es histórica) se informa como CHOQUE: en prod hay fichas
840-845 creadas desde la app que en la planilla son fichas reales; decidir
qué hacer con ellas antes de cargar en prod.

--dry-run hace todo dentro de una transacción y al final la deshace: sirve
para ver el resumen sin escribir nada.

Las columnas "N° factura" y "Pago Ricardo" no se cargan acá: van en una
segunda pasada cuando existan las columnas de pago (#372).
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

REPUESTO_RE = re.compile(r"([A-Za-z0-9]+)\s*\((\d+)\)")
# Forma de un código de repuesto: 1-2 letras + 4 o más dígitos + letra opcional
# (D006110, B600013L, SP00367). Palabras sueltas ("NINGUNO") no son códigos.
REPUESTO_SIMPLE_RE = re.compile(r"^[A-Z]{1,2}\d{4,}[A-Z]?$")
FICHA_RE = re.compile(r"^\s*(\d+)\s*(.*)$")

# Códigos mal escritos en la planilla, corregidos por el cliente (#314).
CORRECCIONES_CODIGO = {
    "B006440": "D006440", "D0006120": "D006120", "D0001260": "D001260",
    "B500810": "B800510", "D500336": "B500336", "D600189": "B600189",
    "D00140": "D001140", "B004620": "D004620", "D0004620": "D004620",
}

# Columnas reales de estado_general (schema-postgres.sql). Cada ENUM ya
# incluye 'HISTORICO' como valor valido -> se puede insertar tal cual.
ESTADO_GENERAL_CAMPOS = [
    "estado_equipo", "carcaza", "cubre_feedwheel", "mango", "botones",
    "motor_arrastre", "motor_sellado", "cuchilla", "servo",
    "rueda_arrastre", "resorte_manija", "otros",
]

# Encabezado de la planilla (sin tildes, minúsculas, sin "n°") -> clave interna
ENCABEZADOS = {
    "item": "item", "ficha": "ficha_n", "cliente": "cliente", "serie": "serie",
    "ingreso": "ingreso", "mes salida": "mes_salida", "salida": "salida",
    "modelo": "modelo", "observacion": "observacion", "reparacion": "reparacion",
    "repuestos": "repuestos", "ciclos": "n_ciclos", "facturar": "facturar",
    "entregadas": "entregadas", "factura": "n_factura", "pago ricardo": "pago_tecnico",
    "remito": "remito",
}


# ----------------------------------------------------------------- lectura

def _normalizar(texto):
    """'N° Ciclos' -> 'ciclos', 'Reparación' -> 'reparacion', 'Ficha N°' -> 'ficha n'."""
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s[2:] if s.startswith("n ") else s


def _clave_columna(encabezado):
    norm = _normalizar(encabezado)
    if norm in ENCABEZADOS:
        return ENCABEZADOS[norm]
    for prefijo, clave in ENCABEZADOS.items():
        if norm.startswith(prefijo):
            return clave
    return None


def _leer_filas_crudas(path):
    """Todas las filas de la planilla como listas de valores."""
    if str(path).lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        wb = load_workbook(path, data_only=True, read_only=True)
        ws = wb["Total"] if "Total" in wb.sheetnames else wb.worksheets[0]
        return [list(f) for f in ws.iter_rows(values_only=True)]
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, newline="", encoding=encoding) as f:
                return [list(f) for f in csv.reader(f)]
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer '{path}'")


def leer_planilla(path):
    """Devuelve una lista de dicts (una por ficha) con claves internas."""
    crudas = _leer_filas_crudas(path)
    # La fila de encabezados es la primera que tiene "Ficha" (en el .xlsx
    # del cliente es la 2da: la 1ra es el título).
    fila_enc = next(i for i, fila in enumerate(crudas)
                    if any(isinstance(v, str) and _clave_columna(v) == "ficha_n" for v in fila))

    columnas = {}
    for col, enc in enumerate(crudas[fila_enc]):
        if isinstance(enc, str):
            clave = _clave_columna(enc)
            if clave and clave not in columnas.values():
                columnas[col] = clave

    filas = []
    for n, fila in enumerate(crudas[fila_enc + 1:], start=fila_enc + 2):  # N° de fila de Excel
        registro = {clave: _vacio_a_none(fila[col] if col < len(fila) else None)
                    for col, clave in columnas.items()}
        if registro.get("ficha_n") is None:
            continue
        registro["_fila"] = n
        filas.append(registro)
    return filas


def _vacio_a_none(valor):
    if valor is None:
        return None
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


def _texto(valor):
    return None if valor is None else str(valor).strip() or None


# ----------------------------------------------------------------- parseo

def parse_fecha(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_ficha(valor):
    """'754 EX 717' -> (754, 'EX 717'); 561 -> (561, None)."""
    if isinstance(valor, (int, float)):
        return int(valor), None
    m = FICHA_RE.match(str(valor))
    if not m:
        return None, None
    return int(m.group(1)), (m.group(2).strip() or None)


def parse_ciclos(valor):
    """Número -> (int, None). Texto ('MANUAL') -> (None, texto)."""
    if valor is None:
        return None, None
    if isinstance(valor, (int, float)):
        return int(valor), None
    s = str(valor).strip()
    if s.isdigit():
        return int(s), None
    return None, s


def parse_repuestos(valor):
    """Devuelve ([(código, cantidad)], hay_texto).

    Soporta 'COD(cant) COD2(cant2)', códigos separados por saltos de línea,
    espacios o comas. hay_texto=True si la celda trae algo que no es un
    código ("NO SE COLOCARON"): ese texto se guarda en observaciones."""
    s = _texto(valor)
    if not s:
        return [], False
    con_cantidad = REPUESTO_RE.findall(s)
    if con_cantidad:
        resto = REPUESTO_RE.sub(" ", s)
        return ([(cod.upper().strip(), int(cant)) for cod, cant in con_cantidad],
                bool(re.sub(r"[\s,;/.-]+", "", resto)))
    codigos, hay_texto = [], False
    for token in re.split(r"[\s,;/]+", s):
        token = token.strip().upper().rstrip(".")
        if not token:
            continue
        if REPUESTO_SIMPLE_RE.match(token):
            codigos.append((token, 1))
        else:
            hay_texto = True
    return codigos, hay_texto


def armar_ficha(fila, matriz):
    """Devuelve (data, avisos) o (None, [motivo]) si la fila no se puede cargar."""
    avisos = []
    notas = []

    ficha_n, resto_ficha = parse_ficha(fila.get("ficha_n"))
    if ficha_n is None:
        return None, [f"N° de ficha inválido: {fila.get('ficha_n')!r}"]
    if resto_ficha:
        notas.append(f"N° de ficha en la planilla: {str(fila.get('ficha_n')).strip()}")

    fecha_ingreso = parse_fecha(fila.get("ingreso"))
    fecha_egreso = parse_fecha(fila.get("salida"))
    if fila.get("ingreso") is not None and fecha_ingreso is None:
        notas.append(f"Fecha de ingreso en la planilla: {_texto(fila.get('ingreso'))}")
    if fila.get("salida") is not None and fecha_egreso is None:
        notas.append(f"Fecha de salida en la planilla: {_texto(fila.get('salida'))}")
    if fecha_ingreso is None and fecha_egreso is None:
        return None, ["Sin fecha de ingreso ni de salida"]
    if fecha_ingreso is None:
        fecha_ingreso = fecha_egreso
        avisos.append("sin fecha de ingreso: se usó la de salida")
    if fecha_egreso is None:
        fecha_egreso = fecha_ingreso
        avisos.append("sin fecha de salida: se usó la de ingreso")

    modelo = _texto(fila.get("modelo"))
    if not modelo:
        modelo = "HISTORICO"
        avisos.append("sin modelo")

    n_ciclos, ciclos_texto = parse_ciclos(fila.get("n_ciclos"))
    if ciclos_texto:
        notas.append(f"N° de ciclos: {ciclos_texto}")

    repuestos, desconocidos = [], []
    codigos, hay_texto = parse_repuestos(fila.get("repuestos"))
    if hay_texto:
        notas.append("Repuestos en la planilla: " + " ".join(_texto(fila.get("repuestos")).split()))
    for codigo, cantidad in codigos:
        codigo = CORRECCIONES_CODIGO.get(codigo, codigo)
        if codigo in matriz:
            repuestos.append((codigo, matriz[codigo], cantidad))
        else:
            desconocidos.append(codigo)
    if desconocidos:
        notas.append("Repuestos no reconocidos: " + ", ".join(desconocidos))
        avisos.append("códigos no reconocidos: " + ", ".join(desconocidos))

    observacion = _texto(fila.get("observacion"))
    if notas:
        observacion = "\n".join(([observacion] if observacion else []) + ["[Planilla] " + n for n in notas])

    remito = _texto(fila.get("remito"))
    data = {
        "ficha_n": ficha_n,
        "cliente": _texto(fila.get("cliente")) or "SIN DATO",
        "modelo": modelo,
        "serie": _texto(fila.get("serie")) or f"HIST-{ficha_n}",
        "fecha_ingreso": fecha_ingreso,
        "fecha_egreso": fecha_egreso,
        "observacion": observacion,
        "reparacion": _texto(fila.get("reparacion")),
        "n_ciclos": n_ciclos,
        "repuestos": repuestos,
        "numero_remito": remito if remito and remito.upper() != "HISTORICO" else "HISTORICO",
    }
    return data, avisos


# ----------------------------------------------------------------- base

def get_connection():
    import psycopg2

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL no está seteada (.env o entorno).", file=sys.stderr)
        sys.exit(1)
    try:
        return psycopg2.connect(database_url)
    except psycopg2.OperationalError as e:
        print(f"ERROR: no se pudo conectar a la base de datos: {e}", file=sys.stderr)
        sys.exit(1)


def cargar_matriz(cur):
    cur.execute("SELECT codigo_repuesto, item FROM matriz_repuestos")
    return {str(r["codigo_repuesto"]).upper().strip(): r["item"] for r in cur.fetchall()}


def ficha_existente(cur, numero):
    """None si no existe; 'historica' o 'app' según quién la creó."""
    cur.execute("SELECT tecnico FROM dml_fichas WHERE numero_ficha = %s", (numero,))
    row = cur.fetchone()
    if row is None:
        return None
    return "historica" if row["tecnico"] == "HISTORICO" else "app"


def insertar_ficha(cur, data):
    cur.execute(
        """
        INSERT INTO raypac_entries
            (fecha_recepcion, tipo_solicitud, cliente, numero_serie,
             modelo_maquina, tipo_maquina, comercial, mail_comercial, numero_remito,
             is_frozen, frozen_at, estado_envio_equipos, fecha_envio_equipos)
        VALUES (%s, 'HISTORICO', %s, %s, %s, 'HISTORICO', 'HISTORICO', 'historico@dml.local', %s,
                TRUE, %s, 'RECIBIDO', %s)
        RETURNING id
        """,
        (data["fecha_ingreso"], data["cliente"], data["serie"], data["modelo"], data["numero_remito"],
         data["fecha_ingreso"], data["fecha_ingreso"]),
    )
    raypac_id = cur.fetchone()["id"]

    cur.execute(
        """
        INSERT INTO dml_fichas
            (numero_ficha, raypac_id, fecha_ingreso, tecnico, observaciones,
             diagnostico_reparacion, estado_reparacion, n_ciclos,
             tecnico_resp, fecha_egreso, is_closed, closed_at,
             fecha_entrega_cliente, recibido_por)
        VALUES (%s, %s, %s, 'HISTORICO', %s, %s, 'MÁQUINA ENTREGADA', %s, 'HISTORICO', %s,
                TRUE, %s, %s, 'HISTORICO')
        RETURNING id
        """,
        (data["ficha_n"], raypac_id, data["fecha_ingreso"], data["observacion"],
         data["reparacion"], data["n_ciclos"], data["fecha_egreso"],
         data["fecha_egreso"], data["fecha_egreso"]),
    )
    ficha_id = cur.fetchone()["id"]

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
    cur.execute(
        f"INSERT INTO estado_general (ficha_id, {columnas}) VALUES (%s, {placeholders}) "
        "ON CONFLICT (ficha_id) DO NOTHING",
        (ficha_id, *("HISTORICO" for _ in ESTADO_GENERAL_CAMPOS)),
    )


# ----------------------------------------------------------------- main

def parse_args():
    parser = argparse.ArgumentParser(description="Carga histórica de fichas DML desde la planilla del cliente.")
    parser.add_argument("planilla", help=".xlsx del cliente (hoja Total) o .csv con los mismos encabezados")
    parser.add_argument("--dry-run", action="store_true", help="mostrar qué haría sin escribir nada")
    return parser.parse_args()


def main():
    from psycopg2.extras import RealDictCursor

    args = parse_args()
    if not os.path.isfile(args.planilla):
        print(f"ERROR: no se encontró el archivo '{args.planilla}'", file=sys.stderr)
        sys.exit(1)

    filas = leer_planilla(args.planilla)
    print(f"[INFO] {len(filas)} fichas leídas de la planilla")

    conn = get_connection()
    cargadas, ya_estaban, choques, salteadas, con_avisos = [], [], [], [], []
    vistas = set()
    reporte = []

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT current_database() AS db, current_user AS usr")
        info = cur.fetchone()
        print(f"[INFO] Base: '{info['db']}' como '{info['usr']}'" + ("  (DRY-RUN: no se guarda nada)" if args.dry_run else ""))
        matriz = cargar_matriz(cur)
        print(f"[INFO] Matriz de repuestos: {len(matriz)} códigos")

        for fila in filas:
            data, avisos = armar_ficha(fila, matriz)
            if data is None:
                salteadas.append(fila["ficha_n"])
                reporte.append((fila["_fila"], fila["ficha_n"], "SALTEADA", "; ".join(avisos)))
                continue
            n = data["ficha_n"]
            if n in vistas:
                salteadas.append(n)
                reporte.append((fila["_fila"], n, "SALTEADA", "N° de ficha repetido en la planilla"))
                continue
            vistas.add(n)

            existe = ficha_existente(cur, n)
            if existe == "historica":
                ya_estaban.append(n)
                continue
            if existe == "app":
                choques.append(n)
                reporte.append((fila["_fila"], n, "CHOQUE", "ese N° ya lo usa una ficha creada desde la app"))
                continue

            cur.execute("SAVEPOINT fila")
            try:
                insertar_ficha(cur, data)
                cur.execute("RELEASE SAVEPOINT fila")
                cargadas.append(n)
                if avisos:
                    con_avisos.append(n)
                    reporte.append((fila["_fila"], n, "CARGADA CON AVISOS", "; ".join(avisos)))
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT fila")
                salteadas.append(n)
                reporte.append((fila["_fila"], n, "ERROR", str(e).strip()))

        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()

    print(f"\n[RESUMEN] {'(DRY-RUN) ' if args.dry_run else ''}"
          f"{len(cargadas)} cargadas ({len(con_avisos)} con avisos), "
          f"{len(ya_estaban)} ya estaban, {len(choques)} choques, {len(salteadas)} salteadas")
    if choques:
        print(f"[ATENCIÓN] Choques con fichas de la app (no se cargaron): {sorted(choques)}")
    if salteadas:
        print(f"[ATENCIÓN] Salteadas: {salteadas}")

    if reporte:
        # Junto a la planilla (fuera del repo), con datos del cliente.
        destino = Path(args.planilla).resolve().parent / f"reporte_carga_{datetime.now():%Y-%m-%d-%H%M}.csv"
        with open(destino, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["fila_planilla", "ficha", "resultado", "detalle"])
            w.writerows(reporte)
        print(f"[INFO] Detalle por ficha en: {destino}")


if __name__ == "__main__":
    main()
