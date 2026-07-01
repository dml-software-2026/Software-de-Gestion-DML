import os
import sys
import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate_db():
    """Ejecuta migraciones de esquema necesarias."""
    db = get_db()
    try:
        # Verificar si la columna cantidad_utilizada existe
        cursor = db.execute("PRAGMA table_info(dml_repuestos)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'cantidad_utilizada' not in columns:
            db.execute("ALTER TABLE dml_repuestos ADD COLUMN cantidad_utilizada INTEGER DEFAULT 1")
            db.commit()

        if 'estado_repuesto' not in columns:
            db.execute("ALTER TABLE dml_repuestos ADD COLUMN estado_repuesto TEXT DEFAULT 'INSPECCIONADO'")
            db.commit()

        # Verificar si codigo_ubicacion_fisica existe en stock_ubicaciones
        cursor = db.execute("PRAGMA table_info(stock_ubicaciones)")
        columns_stock = [row[1] for row in cursor.fetchall()]

        if 'codigo_ubicacion_fisica' not in columns_stock:
            db.execute("ALTER TABLE stock_ubicaciones ADD COLUMN codigo_ubicacion_fisica TEXT DEFAULT 'SIN UBICACIÓN'")
            db.commit()
            print("[MIGRATION] Agregada columna codigo_ubicacion_fisica a stock_ubicaciones")

        # Crear tabla tickets si no existe
        db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_ticket TEXT UNIQUE NOT NULL,
                ficha_id INTEGER NOT NULL,
                numero_serie TEXT NOT NULL,
                estado TEXT DEFAULT 'ACTIVO',
                fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
                fecha_cierre TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE,
                UNIQUE(numero_ticket)
            )
        """)

        # Crear tabla ticket_historial si no existe
        db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                estado_anterior TEXT,
                estado_nuevo TEXT NOT NULL,
                motivo TEXT,
                usuario_id INTEGER,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                FOREIGN KEY(usuario_id) REFERENCES users(id)
            )
        """)

        # Crear tabla stock_alertas si no existe
        db.execute("""
            CREATE TABLE IF NOT EXISTS stock_alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_repuesto TEXT NOT NULL,
                item TEXT,
                cantidad_actual INTEGER,
                nivel_alerta TEXT NOT NULL,
                email_enviado INTEGER DEFAULT 0,
                fecha_alerta TEXT DEFAULT CURRENT_TIMESTAMP,
                fecha_resuelto TEXT,
                FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
            )
        """)

        # Crear tabla estadisticas_repuestos si no existe
        db.execute("""
            CREATE TABLE IF NOT EXISTS estadisticas_repuestos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_repuesto TEXT NOT NULL,
                item TEXT,
                cantidad_utilizada INTEGER DEFAULT 0,
                fecha_ultimo_uso TEXT,
                total_usos INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
            )
        """)

        # Crear tabla freezing_log si no existe
        db.execute("""
            CREATE TABLE IF NOT EXISTS freezing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tabla_nombre TEXT NOT NULL,
                registro_id INTEGER NOT NULL,
                estado_freezing INTEGER NOT NULL,
                usuario_freeze INTEGER,
                fecha_freeze TEXT,
                usuario_unfreeze INTEGER,
                fecha_unfreeze TEXT,
                motivo_unfreeze TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(usuario_freeze) REFERENCES users(id),
                FOREIGN KEY(usuario_unfreeze) REFERENCES users(id)
            )
        """)

        db.commit()
        print("[MIGRATIONS] Completadas exitosamente")
    except Exception as e:
        print(f"Error en migraciones: {e}")
        db.commit()

    # Migración: Agregar campos contacto_cliente y email_cliente a raypac_entries
    try:
        print("[MIGRATION] Verificando campos contacto_cliente y email_cliente...")
        columns = db.execute("PRAGMA table_info(raypac_entries)").fetchall()
        column_names = [col['name'] for col in columns]

        if 'contacto_cliente' not in column_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN contacto_cliente TEXT")
            print("[MIGRATION] ✅ Columna contacto_cliente agregada")

        if 'email_cliente' not in column_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN email_cliente TEXT")
            print("[MIGRATION] ✅ Columna email_cliente agregada")

        db.commit()
        print("[MIGRATION] ✅ Campos de contacto cliente verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de contacto: {e}")
        db.commit()

    # Migración: Agregar campos de estado a envios_repuestos
    try:
        print("[MIGRATION] Verificando campos de estado en envios_repuestos...")
        columns = db.execute("PRAGMA table_info(envios_repuestos)").fetchall()
        column_names = [col['name'] for col in columns]

        if 'estado_envio' not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN estado_envio TEXT DEFAULT 'ENVIADO'")
            print("[MIGRATION] ✅ Columna estado_envio agregada")

        if 'is_frozen' not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN is_frozen INTEGER DEFAULT 1")
            print("[MIGRATION] ✅ Columna is_frozen agregada (1=congelado por defecto)")

        if 'fecha_recepcion_dml' not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN fecha_recepcion_dml TEXT")
            print("[MIGRATION] ✅ Columna fecha_recepcion_dml agregada")

        if 'usuario_recepcion_id' not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN usuario_recepcion_id INTEGER REFERENCES users(id)")
            print("[MIGRATION] ✅ Columna usuario_recepcion_id agregada")

        db.commit()
        print("[MIGRATION] ✅ Campos de estado de envíos verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de estado: {e}")
        db.commit()

    # Migración: Agregar campos de acuse de recibo a dml_fichas
    try:
        print("[MIGRATION] Verificando campos de acuse de recibo...")

        columns = db.execute("PRAGMA table_info(dml_fichas)").fetchall()
        column_names = [col['name'] for col in columns]

        if 'fecha_entrega_cliente' not in column_names:
            db.execute("ALTER TABLE dml_fichas ADD COLUMN fecha_entrega_cliente TEXT")
            print("[MIGRATION] ✅ Columna fecha_entrega_cliente agregada")

        if 'recibido_por' not in column_names:
            db.execute("ALTER TABLE dml_fichas ADD COLUMN recibido_por TEXT")
            print("[MIGRATION] ✅ Columna recibido_por agregada")

        db.commit()
        print("[MIGRATION] ✅ Campos de acuse de recibo verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de acuse: {e}")
        db.commit()

    # Migración: Rediseñar flujo Ticket → Ficha
    try:
        print("[MIGRATION] Rediseñando flujo Ticket → Ficha...")

        # Verificar si raypac_id existe en tickets
        columns = db.execute("PRAGMA table_info(tickets)").fetchall()
        column_names = [col['name'] for col in columns]

        if 'raypac_id' not in column_names:
            db.execute("ALTER TABLE tickets ADD COLUMN raypac_id INTEGER REFERENCES raypac_entries(id)")
            print("[MIGRATION] ✅ Columna raypac_id agregada a tickets")

        # Verificar si ticket_id existe en dml_fichas
        columns = db.execute("PRAGMA table_info(dml_fichas)").fetchall()
        column_names = [col['name'] for col in columns]

        if 'ticket_id' not in column_names:
            db.execute("ALTER TABLE dml_fichas ADD COLUMN ticket_id INTEGER REFERENCES tickets(id)")
            print("[MIGRATION] ✅ Columna ticket_id agregada a dml_fichas")

        # Agregar campos adicionales a tickets si no existen
        columns_tickets = db.execute("PRAGMA table_info(tickets)").fetchall()
        tickets_cols = [col['name'] for col in columns_tickets]

        if 'fecha_ingreso' not in tickets_cols:
            db.execute("ALTER TABLE tickets ADD COLUMN fecha_ingreso TEXT")
            print("[MIGRATION] ✅ Columna fecha_ingreso agregada a tickets")

        if 'tecnico_responsable' not in tickets_cols:
            db.execute("ALTER TABLE tickets ADD COLUMN tecnico_responsable TEXT")
            print("[MIGRATION] ✅ Columna tecnico_responsable agregada a tickets")

        if 'observaciones' not in tickets_cols:
            db.execute("ALTER TABLE tickets ADD COLUMN observaciones TEXT")
            print("[MIGRATION] ✅ Columna observaciones agregada a tickets")

        # Componentes del estado del equipo
        componentes = ['estado_equipo', 'carcaza', 'cubre_feedwheel', 'mango', 'botones',
                      'motor_arrastre', 'motor_sellado', 'cuchilla', 'servo',
                      'rueda_arrastre', 'resorte_manija', 'otros']

        for componente in componentes:
            if componente not in tickets_cols:
                db.execute(f"ALTER TABLE tickets ADD COLUMN {componente} TEXT DEFAULT 'BUENO'")
                print(f"[MIGRATION] ✅ Columna {componente} agregada a tickets")

        # FIX CRÍTICO: En SQLite no se puede modificar constraint NOT NULL directamente
        # Necesitamos recrear la tabla si ficha_id es NOT NULL o faltan columnas
        columnas_requeridas = ['fecha_ingreso', 'tecnico_responsable', 'observaciones',
                               'estado_equipo', 'carcaza', 'cubre_feedwheel', 'mango', 'botones',
                               'motor_arrastre', 'motor_sellado', 'cuchilla', 'servo',
                               'rueda_arrastre', 'resorte_manija', 'otros']

        faltan_columnas = any(col not in tickets_cols for col in columnas_requeridas)

        try:
            # Intentar insertar un ticket de prueba con ficha_id NULL
            db.execute("INSERT INTO tickets (numero_ticket, numero_serie, estado, ficha_id, raypac_id) VALUES ('TEST-MIGRATION', 'TEST', 'ACTIVO', NULL, NULL)")
            db.execute("DELETE FROM tickets WHERE numero_ticket = 'TEST-MIGRATION'")

            if faltan_columnas:
                raise Exception("Faltan columnas en la tabla tickets")

            print("[MIGRATION] ✅ Tabla tickets ya permite ficha_id NULL y tiene todas las columnas")
        except Exception as test_error:
            if "NOT NULL constraint failed" in str(test_error) or faltan_columnas or "no column named" in str(test_error):
                print("[MIGRATION] ⚠️  Detectado constraint NOT NULL en ficha_id. Recreando tabla tickets...")

                # Respaldar datos existentes
                db.execute("""
                    CREATE TABLE tickets_backup AS
                    SELECT id, numero_ticket, ficha_id, numero_serie, estado,
                           fecha_creacion, fecha_cierre, created_at, updated_at, raypac_id
                    FROM tickets
                """)

                # Eliminar tabla original
                db.execute("DROP TABLE tickets")

                # Recrear tabla con ficha_id NULLABLE y todas las columnas necesarias
                db.execute("""
                    CREATE TABLE tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        numero_ticket TEXT UNIQUE NOT NULL,
                        ficha_id INTEGER,
                        numero_serie TEXT NOT NULL,
                        estado TEXT DEFAULT 'ACTIVO',
                        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
                        fecha_cierre TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        raypac_id INTEGER REFERENCES raypac_entries(id),
                        fecha_ingreso TEXT,
                        tecnico_responsable TEXT,
                        observaciones TEXT,
                        estado_equipo TEXT DEFAULT 'BUENO',
                        carcaza TEXT DEFAULT 'BUENO',
                        cubre_feedwheel TEXT DEFAULT 'BUENO',
                        mango TEXT DEFAULT 'BUENO',
                        botones TEXT DEFAULT 'BUENO',
                        motor_arrastre TEXT DEFAULT 'BUENO',
                        motor_sellado TEXT DEFAULT 'BUENO',
                        cuchilla TEXT DEFAULT 'BUENO',
                        servo TEXT DEFAULT 'BUENO',
                        rueda_arrastre TEXT DEFAULT 'BUENO',
                        resorte_manija TEXT DEFAULT 'BUENO',
                        otros TEXT DEFAULT 'BUENO',
                        FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE,
                        UNIQUE(numero_ticket)
                    )
                """)

                # Restaurar datos
                db.execute("""
                    INSERT INTO tickets
                    (id, numero_ticket, ficha_id, numero_serie, estado, fecha_creacion, fecha_cierre, created_at, updated_at, raypac_id)
                    SELECT id, numero_ticket, ficha_id, numero_serie, estado, fecha_creacion, fecha_cierre, created_at, updated_at, raypac_id
                    FROM tickets_backup
                """)

                # Eliminar backup
                db.execute("DROP TABLE tickets_backup")

                print("[MIGRATION] ✅ Tabla tickets recreada con ficha_id NULLABLE")
            else:
                raise test_error

        db.commit()
        print("[MIGRATION] ✅ Flujo Ticket → Ficha configurado")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error en migración de flujo: {e}")
        db.rollback()
        db.commit()

    # Migración: Agregar tipo_entrega a envios_repuestos
    try:
        print("[MIGRATION] Verificando campo tipo_entrega en envios_repuestos...")

        columns = db.execute("PRAGMA table_info(envios_repuestos)").fetchall()
        column_names = [col['name'] for col in columns]

        if 'tipo_entrega' not in column_names:
            db.execute("ALTER TABLE envios_repuestos ADD COLUMN tipo_entrega TEXT DEFAULT 'REPUESTOS'")
            print("[MIGRATION] ✅ Columna tipo_entrega agregada a envios_repuestos")

        db.commit()
        print("[MIGRATION] ✅ Campo tipo_entrega verificado")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando tipo_entrega: {e}")
        db.commit()

    # Migración: Agregar estado_envio_equipos a raypac_entries
    try:
        print("[MIGRATION] Verificando campo estado_envio_equipos en raypac_entries...")

        raypac_cols = db.execute("PRAGMA table_info(raypac_entries)").fetchall()
        raypac_col_names = [col['name'] for col in raypac_cols]

        if 'estado_envio_equipos' not in raypac_col_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN estado_envio_equipos TEXT DEFAULT 'PENDIENTE'")
            print("[MIGRATION] ✅ Columna estado_envio_equipos agregada a raypac_entries")

        if 'fecha_envio_equipos' not in raypac_col_names:
            db.execute("ALTER TABLE raypac_entries ADD COLUMN fecha_envio_equipos TEXT")
            print("[MIGRATION] ✅ Columna fecha_envio_equipos agregada a raypac_entries")

        db.commit()
        print("[MIGRATION] ✅ Campos de estado de envío de equipos verificados")

    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de envío de equipos: {e}")
        db.commit()

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
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()
    migrate_db()  # Aplicar migraciones

    # Cargar datos iniciales (asumimos BD nueva)
    try:
        print("[SEED] 🌱 Cargando datos iniciales...", file=sys.stderr, flush=True)
        from services.seed import load_seed_data  # se crea en el siguiente checkpoint
        db = get_db()
        load_seed_data(db)
        db.commit()
        print("[SEED] ✅ Datos iniciales cargados exitosamente", file=sys.stderr, flush=True)
    except Exception as e:
        import traceback
        print(f"[SEED] ❌ Error cargando datos: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
