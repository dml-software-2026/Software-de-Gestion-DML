"""Backup completo de la base (#52).

David pidió una segunda copia de los datos fuera de Supabase ("se te cae el
original y se te cae la copia"). Arma un .zip en memoria con:

- backup.sql: estructura + datos de todas las tablas, para restaurar en una
  base vacía con un solo archivo (procedimiento en docs/BACKUPS.md).
- csv/<tabla>.csv: una planilla por tabla, para mirar los datos en Excel sin
  depender del sistema.

La estructura se lee de la base real en el momento del backup (no de
schema-postgres.sql, que no siempre coincide con lo que hay en Supabase -
ver #125). Mismo orden que usa pg_dump: tipos y secuencias -> tablas sin
restricciones -> datos -> claves/índices -> contadores. Al agregar las
claves foráneas después de los datos, el orden de los INSERT no importa
(ni el ciclo dml_fichas <-> tickets).

Se hace desde Python y no con pg_dump porque pg_dump no está garantizado en
Render y además tiene que coincidir con la versión de Postgres de Supabase.
La base es chica (los PDF no se guardan, se generan al vuelo), así que todo
entra en memoria sin problema.
"""

import io
import zipfile
from datetime import datetime


def _q(nombre):
    """Identificador entre comillas dobles (tablas/columnas/tipos)."""
    return '"' + nombre.replace('"', '""') + '"'


def _tablas(cur):
    cur.execute("""
        SELECT c.oid, c.relname FROM pg_class c
        WHERE c.relkind = 'r' AND c.relnamespace = 'public'::regnamespace
        ORDER BY c.relname
    """)
    return cur.fetchall()


def _estructura(cur, tablas, sql):
    """Escribe en sql los DROP + CREATE de tipos, secuencias y tablas.
    Devuelve (columnas por tabla, sentencias a correr después de los datos)."""
    nombres = [nombre for _, nombre in tablas]

    cur.execute("""
        SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder)
        FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE t.typnamespace = 'public'::regnamespace
        GROUP BY t.typname ORDER BY t.typname
    """)
    enums = cur.fetchall()

    # Secuencias (columnas SERIAL): se crean antes que las tablas porque el
    # DEFAULT nextval('...') de la columna las necesita.
    cur.execute("""
        SELECT s.relname, d.refobjid::regclass::text, a.attname
        FROM pg_class s
        LEFT JOIN pg_depend d ON d.objid = s.oid AND d.deptype = 'a'
             AND d.classid = 'pg_class'::regclass AND d.refclassid = 'pg_class'::regclass
        LEFT JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
        WHERE s.relkind = 'S' AND s.relnamespace = 'public'::regnamespace
        ORDER BY s.relname
    """)
    secuencias = cur.fetchall()

    sql.write("-- 1) Borrar lo que haya (la restauración deja la base igual al backup)\n")
    if nombres:
        sql.write("DROP TABLE IF EXISTS " + ", ".join(_q(t) for t in nombres) + " CASCADE;\n")
    for nombre, _, _ in secuencias:
        sql.write(f"DROP SEQUENCE IF EXISTS {_q(nombre)} CASCADE;\n")
    for nombre, _ in enums:
        sql.write(f"DROP TYPE IF EXISTS {_q(nombre)} CASCADE;\n")

    sql.write("\n-- 2) Tipos, secuencias y tablas\n")
    for nombre, valores in enums:
        etiquetas = ", ".join(cur.mogrify("%s", [v]).decode("utf-8") for v in valores)
        sql.write(f"CREATE TYPE {_q(nombre)} AS ENUM ({etiquetas});\n")
    for nombre, _, _ in secuencias:
        sql.write(f"CREATE SEQUENCE {_q(nombre)};\n")

    columnas = {}
    for oid, tabla in tablas:
        cur.execute("""
            SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
                   pg_get_expr(d.adbin, d.adrelid), a.attidentity
            FROM pg_attribute a
            LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """, (oid,))
        defs = []
        columnas[tabla] = []
        for col, tipo, not_null, default, identity in cur.fetchall():
            columnas[tabla].append(col)
            linea = f"    {_q(col)} {tipo}"
            if identity:
                linea += " GENERATED " + ("ALWAYS" if identity == "a" else "BY DEFAULT") + " AS IDENTITY"
            elif default is not None:
                linea += f" DEFAULT {default}"
            if not_null:
                linea += " NOT NULL"
            defs.append(linea)
        sql.write(f"CREATE TABLE {_q(tabla)} (\n" + ",\n".join(defs) + "\n);\n")

    # Lo que va después de los datos: primero PK/UNIQUE/CHECK, después FKs
    # (que necesitan las PK de la tabla referenciada), después índices sueltos.
    despues = []
    cur.execute("""
        SELECT c.relname, co.conname, pg_get_constraintdef(co.oid), co.contype
        FROM pg_constraint co JOIN pg_class c ON c.oid = co.conrelid
        WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
          AND co.contype IN ('p', 'u', 'c', 'f', 'x')
        ORDER BY (co.contype = 'f'), c.relname, co.conname
    """)
    for tabla, nombre, definicion, _ in cur.fetchall():
        despues.append(f"ALTER TABLE {_q(tabla)} ADD CONSTRAINT {_q(nombre)} {definicion};")

    cur.execute("""
        SELECT pg_get_indexdef(i.indexrelid)
        FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid
        WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r'
          AND NOT EXISTS (SELECT 1 FROM pg_constraint co WHERE co.conindid = i.indexrelid)
        ORDER BY 1
    """)
    despues += [f"{r[0]};" for r in cur.fetchall()]

    for nombre, tabla, col in secuencias:
        if tabla and col:
            despues.append(f"ALTER SEQUENCE {_q(nombre)} OWNED BY {tabla}.{_q(col)};")
            despues.append(
                f"SELECT setval({cur.mogrify('%s', [_q(nombre)]).decode('utf-8')}, "
                f"COALESCE((SELECT MAX({_q(col)}) FROM {tabla}), 0) + 1, false);"
            )

    # Columnas identity: su contador interno también tiene que seguir al máximo
    cur.execute("""
        SELECT c.relname, a.attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r' AND a.attidentity <> ''
    """)
    for tabla, col in cur.fetchall():
        despues.append(
            f"SELECT setval(pg_get_serial_sequence({cur.mogrify('%s', [_q(tabla)]).decode('utf-8')}, "
            f"{cur.mogrify('%s', [col]).decode('utf-8')}), "
            f"COALESCE((SELECT MAX({_q(col)}) FROM {_q(tabla)}), 0) + 1, false);"
        )

    return columnas, despues


def generar_backup_zip(db):
    """Devuelve (nombre_archivo, bytes del .zip) con la base completa."""
    cur = db.cursor()
    tablas = _tablas(cur)
    ahora = datetime.now()

    sql = io.StringIO()
    sql.write(
        "-- Backup completo (estructura + datos) - Software de Gestión DML\n"
        f"-- Generado: {ahora:%d/%m/%Y %H:%M}\n"
        "-- Restaurar sobre una base Postgres vacía - procedimiento en docs/BACKUPS.md.\n"
        "-- ATENCIÓN: si se corre sobre una base con datos, BORRA todas las tablas\n"
        "-- del sistema y las reemplaza por las de este backup.\n\n"
        "BEGIN;\n\n"
    )
    columnas, despues = _estructura(cur, tablas, sql)

    sql.write("\n-- 3) Datos\n")
    filas_por_tabla = {}
    for _, tabla in tablas:
        cols = columnas[tabla]
        cur.execute(f"SELECT {', '.join(_q(c) for c in cols)} FROM {_q(tabla)} ORDER BY 1")
        filas = cur.fetchall()
        filas_por_tabla[tabla] = len(filas)
        if not filas:
            continue
        sql.write(f"-- {tabla} ({len(filas)} filas)\n")
        lista_cols = ", ".join(_q(c) for c in cols)
        marcadores = "(" + ", ".join(["%s"] * len(cols)) + ")"
        # OVERRIDING SYSTEM VALUE: respeta los IDs originales aunque la
        # columna sea GENERATED ALWAYS AS IDENTITY (sin efecto en SERIAL).
        for fila in filas:
            sql.write(f"INSERT INTO {_q(tabla)} ({lista_cols}) OVERRIDING SYSTEM VALUE VALUES ")
            sql.write(cur.mogrify(marcadores, fila).decode("utf-8") + ";\n")
        sql.write("\n")

    sql.write("-- 4) Claves, índices y contadores de IDs\n")
    sql.write("\n".join(despues) + "\n\nCOMMIT;\n")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("backup.sql", sql.getvalue())
        for _, tabla in tablas:
            csv_buf = io.StringIO()
            cur.copy_expert(f"COPY (SELECT * FROM {_q(tabla)}) TO STDOUT WITH CSV HEADER", csv_buf)
            # BOM para que Excel abra bien los acentos
            zf.writestr(f"csv/{tabla}.csv", "﻿" + csv_buf.getvalue())
        resumen = "\n".join(f"{t}: {n} filas" for t, n in filas_por_tabla.items())
        zf.writestr("LEEME.txt",
                    "Backup de la base de datos - Software de Gestión DML\n"
                    f"Generado: {ahora:%d/%m/%Y %H:%M}\n\n"
                    "- csv/: una planilla por tabla, se abre con Excel.\n"
                    "- backup.sql: para restaurar el sistema completo (ver docs/BACKUPS.md en el repo).\n\n"
                    "Contiene datos de clientes y contraseñas cifradas de los usuarios:\n"
                    "guardarlo en un lugar seguro.\n\n"
                    f"Filas por tabla:\n{resumen}\n")
    cur.close()
    return f"backup_dml_{ahora:%Y-%m-%d_%H%M}.zip", buffer.getvalue()
