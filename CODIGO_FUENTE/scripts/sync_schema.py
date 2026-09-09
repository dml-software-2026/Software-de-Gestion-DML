"""
scripts/sync_schema.py
 
Regenera db/schema-postgres.sql a partir del estado REAL de la base
(Supabase), consultando information_schema. No usa pg_dump: solo
psycopg2 + SQL estándar, para no depender de binarios externos.
 
USO:
    python scripts/sync_schema.py
 
Requiere DATABASE_URL en el entorno (.env local, o la que ya está seteada
como env var en Render). Apuntar SIEMPRE a Dev/staging al probar, nunca a
producción directamente.
 
Qué hace:
    1. Conecta a la base indicada por DATABASE_URL.
    2. Para cada tabla de public, arma su CREATE TABLE IF NOT EXISTS
       (columnas, tipos, defaults, nullability, primary key).
    3. Agrega los FOREIGN KEY como ALTER TABLE ... ADD CONSTRAINT al final,
       una vez que todas las tablas ya existen (evita problemas de orden
       de dependencias entre tablas).
    4. Sobrescribe db/schema-postgres.sql con el resultado.
 
Qué NO hace (a propósito):
    - No aplica nada a la base. Es de solo lectura sobre Postgres.
    - No reemplaza migrate_db(): ese sigue siendo el que aplica cambios.
      Este script solo documenta, después del hecho, cómo quedó la base.
"""
import os
import sys
from pathlib import Path
 
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
 
# Ruta de salida: db/schema-postgres.sql relativo a la raíz del repo.
# Este script vive en scripts/, así que la raíz es un nivel arriba.
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "db" / "schema-postgres.sql"
 
# A diferencia de la app Flask (que carga el .env al arrancar), un script
# standalone como este no lo hace solo. Lo cargamos explícitamente acá.
# El .env vive en la raíz real del repo (un nivel arriba de CODIGO_FUENTE),
# no en REPO_ROOT (que acá coincide con CODIGO_FUENTE, donde está db/).
# Probamos las dos ubicaciones por las dudas.
for candidate in (REPO_ROOT / ".env", REPO_ROOT.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break
 
 
def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: no se encontró DATABASE_URL en el entorno.")
        print("   Seteala en tu .env local (apuntando a Dev/staging) antes de correr este script.")
        sys.exit(1)
    return psycopg2.connect(database_url)
 
 
def get_tables(cur):
    """Lista de tablas de usuario en el schema public, en orden alfabético."""
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    return [row["table_name"] for row in cur.fetchall()]
 
 
def get_columns(cur, table_name):
    cur.execute(
        """
        SELECT
            column_name,
            data_type,
            udt_name,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return cur.fetchall()
 
 
def get_primary_key(cur, table_name):
    cur.execute(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
            AND tc.table_name = %s
            AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        (table_name,),
    )
    return [row["column_name"] for row in cur.fetchall()]
 
 
def get_unique_constraints(cur, table_name):
    """Devuelve una lista de listas de columnas, una por cada UNIQUE constraint."""
    cur.execute(
        """
        SELECT tc.constraint_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
            AND tc.table_name = %s
            AND tc.constraint_type = 'UNIQUE'
        ORDER BY tc.constraint_name, kcu.ordinal_position
        """,
        (table_name,),
    )
    grouped = {}
    for row in cur.fetchall():
        grouped.setdefault(row["constraint_name"], []).append(row["column_name"])
    return list(grouped.values())
 
 
def get_foreign_keys(cur, table_name):
    """FKs de esta tabla: columna local, tabla/columna referenciada, y su
    delete_rule (CASCADE, SET NULL, NO ACTION, etc.) para no perder
    ON DELETE CASCADE al regenerar el archivo."""
    cur.execute(
        """
        SELECT
            kcu.column_name AS local_column,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column,
            rc.delete_rule AS delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name
            AND tc.table_schema = rc.constraint_schema
        WHERE tc.table_schema = 'public'
            AND tc.table_name = %s
            AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY kcu.ordinal_position
        """,
        (table_name,),
    )
    return cur.fetchall()
 
 
# Mapeo de udt_name (nombre interno de Postgres) a lo que se escribe en el
# CREATE TABLE. information_schema.data_type a veces devuelve cosas
# genéricas como "ARRAY" o "USER-DEFINED"; udt_name es más preciso para
# los tipos que este proyecto usa.
def get_enum_types(cur):
    """
    Tipos ENUM custom definidos en el schema public (ej. estado_equipo_enum),
    con sus valores en el orden real de Postgres (enumsortorder), no
    alfabético. pg_type + pg_enum son catálogos internos de Postgres, no
    parte de information_schema (los ENUM no tienen representación ahí).
    """
    cur.execute(
        """
        SELECT t.typname AS type_name, e.enumlabel AS value
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public'
        ORDER BY t.typname, e.enumsortorder
        """
    )
    grouped = {}
    for row in cur.fetchall():
        grouped.setdefault(row["type_name"], []).append(row["value"])
    return grouped
 
 
def build_enum_type_sql(type_name, values):
    quoted_values = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
    return f"CREATE TYPE {type_name} AS ENUM ({quoted_values});"
 
 
TYPE_MAP = {
    "int4": "INTEGER",
    "int8": "BIGINT",
    "int2": "SMALLINT",
    "serial": "SERIAL",
    "bigserial": "BIGSERIAL",
    "text": "TEXT",
    "varchar": "VARCHAR",
    "bpchar": "CHAR",
    "bool": "BOOLEAN",
    "timestamp": "TIMESTAMP",
    "timestamptz": "TIMESTAMPTZ",
    "date": "DATE",
    "numeric": "NUMERIC",
    "float4": "REAL",
    "float8": "DOUBLE PRECISION",
    "jsonb": "JSONB",
    "json": "JSON",
    "uuid": "UUID",
}
 
 
def format_column_type(col):
    udt = col["udt_name"]
    # Si no está en el mapeo, es probable que sea un tipo custom (ej. un
    # ENUM como estado_equipo_enum) — se deja tal cual está en Postgres,
    # sin forzar mayúsculas, para que sea el nombre real del tipo.
    base = TYPE_MAP.get(udt, udt)
 
    if base == "VARCHAR" and col["character_maximum_length"]:
        return f"VARCHAR({col['character_maximum_length']})"
    if base == "NUMERIC" and col["numeric_precision"] is not None:
        if col["numeric_scale"]:
            return f"NUMERIC({col['numeric_precision']}, {col['numeric_scale']})"
        return f"NUMERIC({col['numeric_precision']})"
    return base
 
 
def is_serial_column(col, table_name, cur):
    """
    Detecta columnas SERIAL: en Postgres, una vez creada, una columna SERIAL
    pasa a verse como INTEGER con default nextval(...). Si encontramos ese
    patrón, escribimos SERIAL en vez de "INTEGER DEFAULT nextval(...)" para
    que el .sql generado sea legible y coincida con cómo se declaran
    normalmente las PK autoincrementales en este proyecto.
    """
    default = col["column_default"] or ""
    return col["udt_name"] in ("int4", "int8") and default.startswith("nextval(")
 
 
def build_column_def(col, table_name, cur, primary_key_cols):
    name = col["column_name"]
    serial = is_serial_column(col, table_name, cur)
 
    if serial:
        col_type = "BIGSERIAL" if col["udt_name"] == "int8" else "SERIAL"
    else:
        col_type = format_column_type(col)
 
    parts = [name, col_type]
 
    # Si es la única PK y es serial, no hace falta repetir NOT NULL:
    # PRIMARY KEY ya lo implica. Para el resto, reflejamos is_nullable.
    is_single_pk = len(primary_key_cols) == 1 and name in primary_key_cols
    if col["is_nullable"] == "NO" and not (is_single_pk and serial):
        parts.append("NOT NULL")
 
    if not serial and col["column_default"] is not None:
        parts.append(f"DEFAULT {col['column_default']}")
 
    return " ".join(parts)
 
 
def build_create_table(cur, table_name):
    columns = get_columns(cur, table_name)
    pk_cols = get_primary_key(cur, table_name)
    unique_groups = get_unique_constraints(cur, table_name)
 
    lines = [build_column_def(col, table_name, cur, pk_cols) for col in columns]
 
    if pk_cols:
        lines.append(f"PRIMARY KEY ({', '.join(pk_cols)})")
 
    for group in unique_groups:
        # Evitar declarar UNIQUE de nuevo si ya es la propia PK.
        if sorted(group) != sorted(pk_cols):
            lines.append(f"UNIQUE ({', '.join(group)})")
 
    body = ",\n    ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n    {body}\n);"
 
 
def build_foreign_keys_sql(cur, tables):
    """
    Genera los ALTER TABLE ... ADD CONSTRAINT para todas las FKs, agrupados
    al final del archivo. Así el orden de los CREATE TABLE no importa
    (no hay que resolver el orden de dependencias entre tablas).
    """
    statements = []
    seen = set()
    for table_name in tables:
        fks = get_foreign_keys(cur, table_name)
        for fk in fks:
            # Puede haber más de un constraint de Postgres describiendo
            # exactamente la misma relación (ej. declarada dos veces al
            # crear la tabla) — se deduplica por tabla+columna+referencia,
            # no por nombre de constraint.
            dedup_key = (table_name, fk["local_column"], fk["foreign_table"], fk["foreign_column"])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
 
            constraint_name = f"fk_{table_name}_{fk['local_column']}"
            on_delete = ""
            if fk["delete_rule"] and fk["delete_rule"] != "NO ACTION":
                on_delete = f" ON DELETE {fk['delete_rule']}"
            statements.append(
                f"ALTER TABLE {table_name} "
                f"ADD CONSTRAINT IF NOT EXISTS {constraint_name} "
                f"FOREIGN KEY ({fk['local_column']}) "
                f"REFERENCES {fk['foreign_table']} ({fk['foreign_column']}){on_delete};"
            )
    return statements
 
 
def main():
    print("=" * 70)
    print("SYNC SCHEMA — regenerando db/schema-postgres.sql desde Supabase")
    print("=" * 70)
 
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
 
    try:
        tables = get_tables(cur)
        print(f"\n📋 Tablas encontradas: {len(tables)}")
        for t in tables:
            print(f"   - {t}")
 
        enum_types = get_enum_types(cur)
        if enum_types:
            print(f"\n🏷️  Tipos ENUM encontrados: {len(enum_types)}")
            for name in enum_types:
                print(f"   - {name}")
        enum_statements = [
            build_enum_type_sql(name, values) for name, values in enum_types.items()
        ]
 
        create_statements = []
        for table_name in tables:
            print(f"\n🔍 Procesando {table_name}...")
            create_statements.append(build_create_table(cur, table_name))
 
        fk_statements = build_foreign_keys_sql(cur, tables)
 
        header = (
            "-- =====================================================\n"
            "-- schema-postgres.sql\n"
            "-- GENERADO AUTOMÁTICAMENTE por scripts/sync_schema.py\n"
            "-- NO EDITAR A MANO — los cambios se pierden en el próximo sync.\n"
            "--\n"
            "-- Refleja el estado real de la base al momento de correr el\n"
            "-- script. Los cambios incrementales de schema se hacen vía\n"
            "-- migrate_db() en CODIGO_FUENTE/extensions.py; este archivo es\n"
            "-- solo documentación versionada en git, generada después del\n"
            "-- hecho — no se corre manualmente contra Supabase.\n"
            "-- =====================================================\n"
        )
 
        output = header
        if enum_statements:
            output += "\n-- Tipos ENUM\n" + "\n".join(enum_statements) + "\n"
        output += "\n\n" + "\n\n".join(create_statements)
        if fk_statements:
            output += "\n\n-- Foreign keys\n" + "\n".join(fk_statements)
        output += "\n"
 
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(output, encoding="utf-8")
 
        print("\n" + "=" * 70)
        print(f"✅ {OUTPUT_PATH.relative_to(REPO_ROOT)} actualizado ({len(tables)} tablas, {len(enum_types)} enums)")
        print("   Revisá el diff en git antes de commitear.")
        print("=" * 70)
 
    finally:
        cur.close()
        conn.close()
 
 
if __name__ == "__main__":
    sys.exit(main() or 0)