import sys

import psycopg2
from flask import current_app, g
from psycopg2.extras import RealDictCursor


class PgConnection:
    """
    Wrapper fino sobre la conexión de psycopg2 que imita la API de
    sqlite3.Connection (db.execute(...), db.commit(), etc.) para minimizar
    los cambios necesarios en blueprints/services que ya llaman
    db.execute(...) directamente en todo el proyecto.

    OJO: las queries en esos archivos todavía usan placeholders `?` (estilo
    sqlite3). Con psycopg2 hay que pasar `%s`. Eso queda pendiente de otra
    sesión (auth.py, seed.py, scripts/*.py, etc.) — este wrapper no lo
    soluciona mágicamente, solo evita tener que tocar la forma en que se
    LLAMA a db.execute().
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        return cur

    def executescript(self, script):
        # psycopg2 permite mandar varios statements separados por ';' en un
        # solo execute() siempre que no se usen parámetros (%s).
        cur = self._conn.cursor()
        cur.execute(script)
        cur.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def __getattr__(self, name):
        # Delega cualquier otro atributo/método a la conexión real de psycopg2
        return getattr(self._conn, name)


def get_db():
    if "db" not in g:
        raw_conn = psycopg2.connect(current_app.config["DATABASE_URL"])
        g.db = PgConnection(raw_conn)
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _columnas_de(db, tabla):
    """Reemplazo de PRAGMA table_info(tabla) usando information_schema."""
    cur = db.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
        """,
        (tabla,),
    )
    return [row["column_name"] for row in cur.fetchall()]


def migrate_db():
    """Ejecuta migraciones de esquema necesarias."""
    db = get_db()
    try:
        columns = _columnas_de(db, "dml_repuestos")

        if "cantidad_utilizada" not in columns:
            db.execute("ALTER TABLE dml_repuestos ADD COLUMN IF NOT EXISTS cantidad_utilizada INTEGER DEFAULT 1")
            db.commit()

        if "estado_repuesto" not in columns:
            db.execute("ALTER TABLE dml_repuestos ADD COLUMN IF NOT EXISTS estado_repuesto TEXT DEFAULT 'INSPECCIONADO'")
            db.commit()

        columns_stock = _columnas_de(db, "stock_ubicaciones")

        if "codigo_ubicacion_fisica" not in columns_stock:
            db.execute("ALTER TABLE stock_ubicaciones ADD COLUMN IF NOT EXISTS codigo_ubicacion_fisica TEXT DEFAULT 'SIN UBICACIÓN'")
            db.commit()
            print("[MIGRATION] Agregada columna codigo_ubicacion_fisica a stock_ubicaciones")

        # NOTA: las tablas tickets, ticket_historial, stock_alertas,
        # estadisticas_repuestos y freezing_log ya NO se crean acá.
        # Esos CREATE TABLE quedaron cubiertos por schema-postgre.sql,
        # que ya fue corrido en el SQL Editor de Supabase. Mantenerlos
        # acá duplicados era redundante y una segunda fuente de verdad
        # del schema que se podía desincronizar de Supabase con el tiempo.

        db.commit()
        print("[MIGRATIONS] Completadas exitosamente")
    except Exception as e:
        print(f"Error en migraciones: {e}")
        db.rollback()

    # Migración: Agregar campos contacto_cliente y email_cliente a raypac_entries
    try:
        print("[MIGRATION] Verificando campos contacto_cliente y email_cliente...")
        column_names = _columnas_de(db, "raypac_entries")

        if "contacto_cliente" not in column_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN IF NOT EXISTS contacto_cliente TEXT")
            print("[MIGRATION] ✅ Columna contacto_cliente agregada")

        if "email_cliente" not in column_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN IF NOT EXISTS email_cliente TEXT")
            print("[MIGRATION] ✅ Columna email_cliente agregada")

        db.commit()
        print("[MIGRATION] ✅ Campos de contacto cliente verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de contacto: {e}")
        db.rollback()

    # Migración: Agregar numero_correlativo a raypac_entries
    # (raypac_new() en blueprints/raypac.py lee/escribe esta columna para
    # numerar los ingresos de forma correlativa arrancando en 1, pero nunca
    # tuvo migración en Postgres — solo existía en el schema.sql viejo de
    # SQLite. Sin esto, guardar un ingreso nuevo tira excepción.)
    try:
        print("[MIGRATION] Verificando campo numero_correlativo...")
        column_names = _columnas_de(db, "raypac_entries")

        if "numero_correlativo" not in column_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN IF NOT EXISTS numero_correlativo INTEGER")
            print("[MIGRATION] ✅ Columna numero_correlativo agregada")

        db.commit()
        print("[MIGRATION] ✅ Campo numero_correlativo verificado")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando numero_correlativo: {e}")
        db.rollback()

    # Migración: Agregar campos de estado a envios_repuestos
    try:
        print("[MIGRATION] Verificando campos de estado en envios_repuestos...")
        column_names = _columnas_de(db, "envios_repuestos")

        if "estado_envio" not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN IF NOT EXISTS estado_envio TEXT DEFAULT 'ENVIADO'")
            print("[MIGRATION] ✅ Columna estado_envio agregada")

        if "is_frozen" not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN IF NOT EXISTS is_frozen BOOLEAN DEFAULT TRUE")
            print("[MIGRATION] ✅ Columna is_frozen agregada (TRUE=congelado por defecto)")

        if "fecha_recepcion_dml" not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN IF NOT EXISTS fecha_recepcion_dml TIMESTAMP")
            print("[MIGRATION] ✅ Columna fecha_recepcion_dml agregada")

        if "usuario_recepcion_id" not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN IF NOT EXISTS usuario_recepcion_id INTEGER REFERENCES users(id)")
            print("[MIGRATION] ✅ Columna usuario_recepcion_id agregada")

        db.commit()
        print("[MIGRATION] ✅ Campos de estado de envíos verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de estado: {e}")
        db.rollback()

    # Migración: Agregar campos de acuse de recibo a dml_fichas
    try:
        print("[MIGRATION] Verificando campos de acuse de recibo...")
        column_names = _columnas_de(db, "dml_fichas")

        if "fecha_entrega_cliente" not in column_names:
            db.execute("ALTER TABLE dml_fichas ADD COLUMN IF NOT EXISTS fecha_entrega_cliente TIMESTAMP")
            print("[MIGRATION] ✅ Columna fecha_entrega_cliente agregada")

        if "recibido_por" not in column_names:
            db.execute("ALTER TABLE dml_fichas ADD COLUMN IF NOT EXISTS recibido_por TEXT")
            print("[MIGRATION] ✅ Columna recibido_por agregada")

        db.commit()
        print("[MIGRATION] ✅ Campos de acuse de recibo verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de acuse: {e}")
        db.rollback()

    # Migración: Rediseñar flujo Ticket → Ficha
    #
    # NOTA: el original recreaba toda la tabla `tickets` (CREATE ... AS SELECT
    # + DROP + CREATE + INSERT) porque SQLite no permite modificar un
    # constraint NOT NULL con ALTER TABLE. Postgres sí lo permite
    # directamente con ALTER COLUMN ... DROP NOT NULL, así que ese hack
    # completo (backup/drop/recreate) se elimina.
    try:
        print("[MIGRATION] Rediseñando flujo Ticket → Ficha...")

        cols_tickets = _columnas_de(db, "tickets")
        if "raypac_id" not in cols_tickets:
            db.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS raypac_id INTEGER REFERENCES raypac_entries(id)")
            print("[MIGRATION] ✅ Columna raypac_id agregada a tickets")

        cols_fichas = _columnas_de(db, "dml_fichas")
        if "ticket_id" not in cols_fichas:
            db.execute("ALTER TABLE dml_fichas ADD COLUMN IF NOT EXISTS ticket_id INTEGER REFERENCES tickets(id)")
            print("[MIGRATION] ✅ Columna ticket_id agregada a dml_fichas")

        cols_tickets = _columnas_de(db, "tickets")

        campos_texto = ["fecha_ingreso", "tecnico_responsable", "observaciones"]
        for campo in campos_texto:
            if campo not in cols_tickets:
                db.execute(f"ALTER TABLE tickets ADD COLUMN IF NOT EXISTS {campo} TEXT")
                print(f"[MIGRATION] ✅ Columna {campo} agregada a tickets")

        # Componentes del estado del equipo
        componentes = [
            "estado_equipo", "carcaza", "cubre_feedwheel", "mango", "botones",
            "motor_arrastre", "motor_sellado", "cuchilla", "servo",
            "rueda_arrastre", "resorte_manija", "otros",
        ]

        for componente in componentes:
            if componente not in cols_tickets:
                db.execute(f"ALTER TABLE tickets ADD COLUMN IF NOT EXISTS {componente} TEXT DEFAULT 'BUENO'")
                print(f"[MIGRATION] ✅ Columna {componente} agregada a tickets")

        # Postgres permite modificar el constraint NOT NULL directamente,
        # sin recrear la tabla como había que hacer en SQLite.
        db.execute("ALTER TABLE tickets ALTER COLUMN ficha_id DROP NOT NULL")
        print("[MIGRATION] ✅ ficha_id en tickets ahora es NULLABLE")

        db.commit()
        print("[MIGRATION] ✅ Flujo Ticket → Ficha configurado")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error en migración de flujo: {e}")
        db.rollback()

    # Migración: Agregar tipo_entrega a envios_repuestos
    try:
        print("[MIGRATION] Verificando campo tipo_entrega en envios_repuestos...")
        column_names = _columnas_de(db, "envios_repuestos")

        if "tipo_entrega" not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN IF NOT EXISTS tipo_entrega TEXT DEFAULT 'REPUESTOS'")
            print("[MIGRATION] ✅ Columna tipo_entrega agregada a envios_repuestos")

        db.commit()
        print("[MIGRATION] ✅ Campo tipo_entrega verificado")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando tipo_entrega: {e}")
        db.rollback()

    # Migración: Agregar estado_envio_equipos a raypac_entries
    try:
        print("[MIGRATION] Verificando campo estado_envio_equipos en raypac_entries...")
        raypac_col_names = _columnas_de(db, "raypac_entries")

        if "estado_envio_equipos" not in raypac_col_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN IF NOT EXISTS estado_envio_equipos TEXT DEFAULT 'PENDIENTE'")
            print("[MIGRATION] ✅ Columna estado_envio_equipos agregada a raypac_entries")

        if "fecha_envio_equipos" not in raypac_col_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN IF NOT EXISTS fecha_envio_equipos TIMESTAMP")
            print("[MIGRATION] ✅ Columna fecha_envio_equipos agregada a raypac_entries")

        db.commit()
        print("[MIGRATION] ✅ Campos de estado de envío de equipos verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de envío de equipos: {e}")
        db.rollback()

    # TODO SEGURIDAD (Épica 2): acá el app.py original tiene un bloque
    # "Migración de hashes de contraseñas" que re-escribe el password_hash de
    # 4 usuarios con valores hardcodeados en el código (dict CORRECT_HASHES),
    # cada vez que arranca la app. Es el mismo bug que las tareas pendientes
    # "credenciales hardcodeadas" + "passwords que se revierten en cada
    # arranque" de la Épica 2 - son el mismo bloque de código.
    # Lo dejamos fuera de este refactor a propósito: cuando ataquemos esa
    # épica, hay que reemplazarlo por un mecanismo real (reset manual desde
    # admin, o seed solo si el usuario no existe todavía) en vez de
    # sobreescribir el hash en cada arranque del server.


def init_db():
    db = get_db()
    migrate_db()  # Aplicar migraciones

    # Cargar datos iniciales (asumimos BD nueva)
    try:
        print("[SEED] 🌱 Cargando datos iniciales...", file=sys.stderr, flush=True)
        from CODIGO_FUENTE.services.seed import (
            load_seed_data,  # se crea en el siguiente checkpoint
        )
        db = get_db()
        load_seed_data(db)
        db.commit()
        print("[SEED] ✅ Datos iniciales cargados exitosamente", file=sys.stderr, flush=True)
    except Exception as e:
        import traceback
        print(f"[SEED] ❌ Error cargando datos: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
