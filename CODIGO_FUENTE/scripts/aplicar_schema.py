"""
scripts/aplicar_schema.py
 
Lee db/schema-postgres.sql (la fuente de verdad DECLARADA del schema) y
modifica Supabase para que quede exactamente igual a lo que dice ese
archivo: agrega tablas/columnas/valores de ENUM/foreign keys que falten,
corrige tipos de columna que no coincidan, y BORRA tablas/columnas que
estén en Supabase pero ya no estén en el archivo.
 
Es el script "al revés" de sync_schema.py:
    sync_schema.py:     Supabase (estado real) -> lee  -> escribe -> .sql
    aplicar_schema.py:  .sql (estado deseado)  -> lee  -> compara -> aplica -> Supabase
 
NUNCA aplica nada sin mostrar antes la lista completa de cambios (incluidos
los DROP) y pedir confirmación explícita escrita por el usuario. No hay
modo "silencioso" ni flag para saltear la confirmación: es intencional.
 
USO:
    python scripts/aplicar_schema.py
 
Requiere DATABASE_URL en el entorno (.env local, misma convención que
sync_schema.py y cargar_historico.py). Apuntar siempre a Dev al probar,
nunca a producción directamente.
 
Qué SÍ hace:
    - CREATE TYPE ... AS ENUM para tipos ENUM nuevos.
    - ALTER TYPE ... ADD VALUE para valores nuevos dentro de un ENUM existente.
    - CREATE TABLE IF NOT EXISTS para tablas nuevas.
    - ALTER TABLE ... ADD COLUMN para columnas nuevas.
    - ALTER TABLE ... ALTER COLUMN ... TYPE para columnas cuyo tipo no coincide.
    - ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY para FKs nuevas.
    - ALTER TABLE ... DROP COLUMN / DROP TABLE para lo que sobre en Supabase
      respecto al archivo — SIEMPRE con confirmación explícita, nunca solo.
 
Qué NO hace (a propósito, por ahora):
    - No corre en el deploy automático. Es una herramienta de uso manual,
      corrida a mano por una persona que revisa los cambios antes de
      confirmarlos. No reemplaza al mecanismo additive-only que corre en
      cada deploy (hoy migrate_db(); eso se analiza aparte).
    - No intenta migrar datos al cambiar tipos de columna más allá del
      USING implícito de Postgres — si el cambio de tipo puede fallar por
      datos existentes (ej. TEXT largo -> VARCHAR(50)), Postgres va a
      tirar el error en el momento de aplicar, no antes.
"""
import os
import re
import sys
from pathlib import Path
 
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
 
REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "db" / "schema-postgres.sql"
 
for candidate in (REPO_ROOT / ".env", REPO_ROOT.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break
 
 
# =====================================================================
# 1. PARSEO del archivo .sql declarado
#
# El archivo es generado por sync_schema.py con un formato consistente,
# así que el parser es deliberadamente simple (regex), no un parser SQL
# genérico. Si el formato de sync_schema.py cambia, este parser hay que
# actualizarlo junto con él.
# =====================================================================
 
def parse_schema_file(path):
    if not path.exists():
        print(f"❌ ERROR: no se encontró {path}")
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
 
    enums = parse_enums(text)
    tables = parse_tables(text)
    foreign_keys = parse_foreign_keys(text)
    return enums, tables, foreign_keys
 
 
def parse_enums(text):
    """CREATE TYPE nombre AS ENUM ('a', 'b', ...);  ->  {nombre: [valores]}"""
    enums = {}
    pattern = re.compile(
        r"CREATE TYPE\s+(\w+)\s+AS ENUM\s*\((.*?)\)\s*;", re.IGNORECASE | re.DOTALL
    )
    for name, values_blob in pattern.findall(text):
        values = re.findall(r"'((?:[^']|'')*)'", values_blob)
        enums[name] = [v.replace("''", "'") for v in values]
    return enums
 
 
def parse_tables(text):
    """
    CREATE TABLE IF NOT EXISTS nombre (\n    col tipo ...,\n    ...\n);
    -> {nombre: {"columns": {col: {"type": ..., "nullable": bool, "default": ...}},
                 "primary_key": [...], "unique_groups": [[...], ...]}}
    """
    tables = {}
    pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\)\s*;", re.IGNORECASE | re.DOTALL
    )
    for table_name, body in pattern.findall(text):
        columns = {}
        primary_key = []
        unique_groups = []
 
        # Separar por comas de nivel superior (no las que están dentro de
        # paréntesis de VARCHAR(255) o NUMERIC(10,2))
        entries = split_top_level_commas(body)
 
        for entry in entries:
            entry = entry.strip().rstrip(",").strip()
            if not entry:
                continue
 
            m_pk = re.match(r"PRIMARY KEY\s*\((.*?)\)", entry, re.IGNORECASE)
            if m_pk:
                primary_key = [c.strip() for c in m_pk.group(1).split(",")]
                continue
 
            m_uq = re.match(r"UNIQUE\s*\((.*?)\)", entry, re.IGNORECASE)
            if m_uq:
                unique_groups.append([c.strip() for c in m_uq.group(1).split(",")])
                continue
 
            # Columna: primer token es el nombre, resto es la definición
            m_col = re.match(r"(\w+)\s+(.*)", entry)
            if not m_col:
                continue
            col_name, rest = m_col.group(1), m_col.group(2)
 
            nullable = "NOT NULL" not in rest.upper()
            default_match = re.search(r"DEFAULT\s+(.+?)(?:\s+NOT NULL|$)", rest, re.IGNORECASE)
            default = default_match.group(1).strip() if default_match else None
 
            # El tipo es todo lo que queda antes de NOT NULL / DEFAULT
            col_type = rest
            col_type = re.sub(r"\s+NOT NULL.*", "", col_type, flags=re.IGNORECASE)
            col_type = re.sub(r"\s+DEFAULT\s+.+", "", col_type, flags=re.IGNORECASE)
            col_type = normalize_type(col_type.strip())
 
            columns[col_name] = {
                "type": col_type,
                "nullable": nullable,
                "default": default,
            }
 
        tables[table_name] = {
            "columns": columns,
            "primary_key": primary_key,
            "unique_groups": unique_groups,
        }
    return tables
 
 
def split_top_level_commas(body):
    """Divide por comas que no están dentro de paréntesis."""
    parts, depth, current = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return parts
 
 
def normalize_type(t):
    """SERIAL columnas: en Postgres, una vez creada, se ve como INTEGER con
    nextval() de default. Para comparar contra la base real (que reporta
    'integer'), tratamos SERIAL/BIGSERIAL como equivalentes a INTEGER/BIGINT
    al momento de comparar tipos existentes (no afecta CREATE TABLE nuevo,
    donde SERIAL se usa tal cual)."""
    return t.strip()
 
 
def parse_foreign_keys(text):
    """
    ALTER TABLE tabla ADD CONSTRAINT IF NOT EXISTS nombre
        FOREIGN KEY (col) REFERENCES tabla_ref (col_ref) [ON DELETE regla];
    """
    fks = []
    pattern = re.compile(
        r"ALTER TABLE\s+(\w+)\s+ADD CONSTRAINT IF NOT EXISTS\s+(\w+)\s+"
        r"FOREIGN KEY\s*\((\w+)\)\s+REFERENCES\s+(\w+)\s*\((\w+)\)"
        r"(?:\s+ON DELETE\s+(\w+))?\s*;",
        re.IGNORECASE,
    )
    for table, constraint_name, local_col, foreign_table, foreign_col, on_delete in pattern.findall(text):
        fks.append({
            "table": table,
            "constraint_name": constraint_name,
            "local_column": local_col,
            "foreign_table": foreign_table,
            "foreign_column": foreign_col,
            "on_delete": (on_delete or "").upper() or None,
        })
    return fks
 
 
# =====================================================================
# 2. LECTURA del estado real en Supabase
# =====================================================================
 
def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: no se encontró DATABASE_URL en el entorno.")
        sys.exit(1)
    print(f"🔌 Conectando a: {database_url.split('@')[-1]}")
    return psycopg2.connect(database_url)
 
 
def get_real_tables(cur):
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
    )
    return {row["table_name"] for row in cur.fetchall()}
 
 
def get_real_columns(cur, table_name):
    cur.execute(
        """
        SELECT column_name, data_type, udt_name, character_maximum_length,
               numeric_precision, numeric_scale, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return {row["column_name"]: row for row in cur.fetchall()}
 
 
def get_real_enums(cur):
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
 
 
def get_real_foreign_keys(cur, table_name):
    cur.execute(
        """
        SELECT tc.constraint_name, kcu.column_name AS local_column,
               ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
        WHERE tc.table_schema = 'public' AND tc.table_name = %s
            AND tc.constraint_type = 'FOREIGN KEY'
        """,
        (table_name,),
    )
    return {row["local_column"]: row for row in cur.fetchall()}
 
 
TYPE_MAP = {
    "int4": "INTEGER", "int8": "BIGINT", "int2": "SMALLINT",
    "text": "TEXT", "varchar": "VARCHAR", "bpchar": "CHAR", "bool": "BOOLEAN",
    "timestamp": "TIMESTAMP", "timestamptz": "TIMESTAMPTZ", "date": "DATE",
    "numeric": "NUMERIC", "float4": "REAL", "float8": "DOUBLE PRECISION",
    "jsonb": "JSONB", "json": "JSON", "uuid": "UUID", "bytea": "BYTEA",
}
 
 
def real_column_type_as_declared(col):
    """Convierte lo que devuelve information_schema al mismo formato de
    texto que usa el archivo .sql declarado, para poder comparar strings."""
    udt = col["udt_name"]
    base = TYPE_MAP.get(udt, udt.upper())
    if base == "VARCHAR" and col["character_maximum_length"]:
        return f"VARCHAR({col['character_maximum_length']})"
    if base == "NUMERIC" and col["numeric_precision"] is not None:
        if col["numeric_scale"]:
            return f"NUMERIC({col['numeric_precision']}, {col['numeric_scale']})"
        return f"NUMERIC({col['numeric_precision']})"
    return base
 
 
# =====================================================================
# 3. DIFF: comparar deseado vs. real, generar lista de cambios
# =====================================================================
 
class Cambio:
    def __init__(self, categoria, descripcion, sql, destructivo=False):
        self.categoria = categoria
        self.descripcion = descripcion
        self.sql = sql
        self.destructivo = destructivo
 
 
def calcular_diff(enums_deseado, tablas_deseado, fks_deseado, cur):
    cambios = []
 
    # --- ENUMs: tipos nuevos y valores nuevos ---
    enums_real = get_real_enums(cur)
    for enum_name, valores_deseados in enums_deseado.items():
        if enum_name not in enums_real:
            quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in valores_deseados)
            cambios.append(Cambio(
                "ENUM nuevo", f"Crear tipo {enum_name} con {len(valores_deseados)} valores",
                f"CREATE TYPE {enum_name} AS ENUM ({quoted});",
            ))
        else:
            valores_reales = enums_real[enum_name]
            for valor in valores_deseados:
                if valor not in valores_reales:
                    cambios.append(Cambio(
                        "Valor de ENUM nuevo", f"Agregar '{valor}' a {enum_name}",
                        f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{valor}';",
                    ))
 
    # --- Tablas y columnas ---
    tablas_real = get_real_tables(cur)
    for table_name, tabla_info in tablas_deseado.items():
        if table_name not in tablas_real:
            cambios.append(Cambio(
                "Tabla nueva", f"Crear tabla {table_name}",
                build_create_table_sql(table_name, tabla_info),
            ))
            continue  # ya va a quedar con todas sus columnas al crearla
 
        columnas_real = get_real_columns(cur, table_name)
        for col_name, col_info in tabla_info["columns"].items():
            if col_name not in columnas_real:
                cambios.append(Cambio(
                    "Columna nueva", f"Agregar {table_name}.{col_name} ({col_info['type']})",
                    f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "
                    f"{col_name} {col_info['type']}"
                    + (f" DEFAULT {col_info['default']}" if col_info["default"] else "")
                    + ";",
                ))
            else:
                col_real = columnas_real[col_name]
                tipo_real = real_column_type_as_declared(col_real)
                tipo_deseado = col_info["type"].upper()
 
                # SERIAL/BIGSERIAL no existen como tipos reales en Postgres:
                # se guardan como INTEGER/BIGINT con default nextval(...).
                # Si el archivo declara SERIAL y la base tiene ese patrón,
                # son equivalentes — no es un cambio de tipo real.
                es_serial_equivalente = (
                    tipo_deseado in ("SERIAL", "BIGSERIAL")
                    and col_real["udt_name"] in ("int4", "int8")
                    and (col_real["column_default"] or "").startswith("nextval(")
                )
 
                if not es_serial_equivalente and tipo_real.upper() != tipo_deseado:
                    cambios.append(Cambio(
                        "Tipo de columna distinto",
                        f"{table_name}.{col_name}: {tipo_real} → {tipo_deseado}",
                        f"ALTER TABLE {table_name} ALTER COLUMN {col_name} "
                        f"TYPE {col_info['type']} USING {col_name}::{col_info['type']};",
                    ))
 
        # --- Columnas que sobran (están en Supabase, no en el archivo) ---
        for col_name in columnas_real:
            if col_name not in tabla_info["columns"]:
                cambios.append(Cambio(
                    "Columna a borrar", f"Borrar {table_name}.{col_name} (no está en el schema)",
                    f"ALTER TABLE {table_name} DROP COLUMN {col_name};",
                    destructivo=True,
                ))
 
    # --- Tablas que sobran ---
    for table_name in tablas_real:
        if table_name not in tablas_deseado:
            cambios.append(Cambio(
                "Tabla a borrar", f"Borrar tabla {table_name} completa (no está en el schema)",
                f"DROP TABLE {table_name} CASCADE;",
                destructivo=True,
            ))
 
    # --- Foreign keys nuevas ---
    for fk in fks_deseado:
        fks_real = get_real_foreign_keys(cur, fk["table"])
        existe = any(
            real_fk["local_column"] == fk["local_column"]
            and real_fk["foreign_table"] == fk["foreign_table"]
            and real_fk["foreign_column"] == fk["foreign_column"]
            for real_fk in fks_real.values()
        )
        if not existe:
            on_delete = f" ON DELETE {fk['on_delete']}" if fk["on_delete"] else ""
            cambios.append(Cambio(
                "Foreign key nueva",
                f"{fk['table']}.{fk['local_column']} → {fk['foreign_table']}.{fk['foreign_column']}",
                f"ALTER TABLE {fk['table']} ADD CONSTRAINT {fk['constraint_name']} "
                f"FOREIGN KEY ({fk['local_column']}) "
                f"REFERENCES {fk['foreign_table']} ({fk['foreign_column']}){on_delete};",
            ))
 
    return cambios
 
 
def build_create_table_sql(table_name, tabla_info):
    lines = []
    for col_name, col_info in tabla_info["columns"].items():
        parts = [col_name, col_info["type"]]
        if not col_info["nullable"]:
            parts.append("NOT NULL")
        if col_info["default"]:
            parts.append(f"DEFAULT {col_info['default']}")
        lines.append(" ".join(parts))
    if tabla_info["primary_key"]:
        lines.append(f"PRIMARY KEY ({', '.join(tabla_info['primary_key'])})")
    for group in tabla_info["unique_groups"]:
        lines.append(f"UNIQUE ({', '.join(group)})")
    body = ",\n    ".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n    {body}\n);"
 
 
# =====================================================================
# 4. MOSTRAR cambios, PEDIR confirmación, APLICAR
# =====================================================================
 
ORDEN_APLICACION = [
    "ENUM nuevo", "Valor de ENUM nuevo", "Tabla nueva", "Columna nueva",
    "Tipo de columna distinto", "Foreign key nueva",
    "Columna a borrar", "Tabla a borrar",
]
 
 
def mostrar_cambios(cambios):
    print("\n" + "=" * 70)
    print(f"CAMBIOS DETECTADOS: {len(cambios)}")
    print("=" * 70)
 
    if not cambios:
        print("✅ Supabase ya coincide exactamente con db/schema-postgres.sql. Nada que hacer.")
        return
 
    for categoria in ORDEN_APLICACION:
        de_esta_categoria = [c for c in cambios if c.categoria == categoria]
        if not de_esta_categoria:
            continue
        print(f"\n--- {categoria} ({len(de_esta_categoria)}) ---")
        for c in de_esta_categoria:
            marca = "⚠️  DESTRUCTIVO" if c.destructivo else "  "
            print(f"{marca} {c.descripcion}")
            print(f"      SQL: {c.sql}")
 
    destructivos = [c for c in cambios if c.destructivo]
    if destructivos:
        print(f"\n⚠️  ATENCIÓN: {len(destructivos)} cambio(s) van a BORRAR datos/estructura de forma irreversible.")
 
 
def pedir_confirmacion(cambios):
    if not cambios:
        return False
    print("\n" + "-" * 70)
    respuesta = input("¿Aplicar estos cambios contra la base conectada? Escribí 'si' para confirmar: ")
    return respuesta.strip().lower() == "si"
 
 
def aplicar_cambios(cambios, conn, cur):
    for categoria in ORDEN_APLICACION:
        de_esta_categoria = [c for c in cambios if c.categoria == categoria]
        for c in de_esta_categoria:
            try:
                print(f"  → {c.descripcion}")
                cur.execute(c.sql)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"    ❌ ERROR aplicando este cambio: {e}")
                print(f"    Se detiene la ejecución acá. Los cambios previos ya aplicados quedan.")
                sys.exit(1)
    print("\n✅ Todos los cambios se aplicaron correctamente.")
 
 
def main():
    print("=" * 70)
    print("APLICAR SCHEMA — sincroniza Supabase con db/schema-postgres.sql")
    print("=" * 70)
 
    enums_deseado, tablas_deseado, fks_deseado = parse_schema_file(SCHEMA_PATH)
    print(f"\n📄 Leído {SCHEMA_PATH.name}: {len(tablas_deseado)} tablas, "
          f"{len(enums_deseado)} enums, {len(fks_deseado)} foreign keys declaradas")
 
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
 
    try:
        cambios = calcular_diff(enums_deseado, tablas_deseado, fks_deseado, cur)
        mostrar_cambios(cambios)
 
        if cambios and pedir_confirmacion(cambios):
            aplicar_cambios(cambios, conn, cur)
        elif cambios:
            print("\n🚫 Cancelado. No se aplicó ningún cambio.")
    finally:
        cur.close()
        conn.close()
 
 
if __name__ == "__main__":
    main()