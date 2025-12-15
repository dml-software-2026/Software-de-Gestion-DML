import os
import sys
import sqlite3
import csv
from datetime import datetime, timedelta
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import json

from flask import (
    Flask, g, render_template, request, redirect,
    url_for, session, flash, send_file, jsonify, make_response
)

load_dotenv()

# Detectar si es ejecutable compilado
IS_EXECUTABLE = getattr(sys, 'frozen', False)
if IS_EXECUTABLE:
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "INTERFAZ", "templates"),
    static_folder=os.path.join(BASE_DIR, "INTERFAZ", "static"),
    static_url_path="/static"
)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
    DATABASE=os.path.join(BASE_DIR, "dml.db"),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "localhost"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", True),
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", "noreply@dml.local")
)

# Hacer funciones disponibles en Jinja2
def get_current_user_jinja():
    """Obtiene usuario actual para uso en Jinja2"""
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

app.jinja_env.globals.update(get_current_user=get_current_user_jinja)

# ======================== DATABASE ========================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
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
        
        # Verificar si las columnas ya existen
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
        # Necesitamos recrear la tabla si ficha_id es NOT NULL
        # Verificar si necesitamos migrar la tabla
        try:
            # Intentar insertar un ticket de prueba con ficha_id NULL
            db.execute("INSERT INTO tickets (numero_ticket, numero_serie, estado, ficha_id, raypac_id) VALUES ('TEST-MIGRATION', 'TEST', 'ACTIVO', NULL, NULL)")
            db.execute("DELETE FROM tickets WHERE numero_ticket = 'TEST-MIGRATION'")
            print("[MIGRATION] ✅ Tabla tickets ya permite ficha_id NULL")
        except Exception as test_error:
            if "NOT NULL constraint failed" in str(test_error):
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
                
                # Recrear tabla con ficha_id NULLABLE
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
    
    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error agregando campos de acuse: {e}")
        db.commit()
    
    # Migración de hashes de contraseñas (actualización automática)
    try:
        print("[MIGRATION] Verificando hashes de contraseñas...")
        
        # Hashes correctos actualizados (pbkdf2:sha256:600000)
        CORRECT_HASHES = {
            'admin@dml.local': 'pbkdf2:sha256:600000$6A2RbBVTCNKXL7de$75969207ac15a7e7c63186bd53b919c17b722a89500a7fc6eb60cb3b20cdef7d',
            'raypac@dml.local': 'pbkdf2:sha256:600000$aSrOi7eCprUIyoPQ$86de1f158beaf6d954e51fc29a03f8e33749c4993ed3327256b821e5a4fab30d',
            'tecnico@dml.local': 'pbkdf2:sha256:600000$bQ5PGbB2osS0xFi3$9cc5715d44a91e16db07e75d67842d981132af4d2d385164d2c5c0a906c3b8a7',
            'repuestos@dml.local': 'pbkdf2:sha256:600000$SyoM7kdkrIC3rxrS$e5e182cfd55f3482cbc5665339081ec5a90b3234a2d591634bd1ce89ea17cf47'
        }
        
        users_updated = 0
        for email, correct_hash in CORRECT_HASHES.items():
            current_user = db.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
            
            if current_user and current_user['password_hash'] != correct_hash:
                db.execute("UPDATE users SET password_hash = ? WHERE email = ?", (correct_hash, email))
                users_updated += 1
                print(f"[MIGRATION] ✅ Hash actualizado para: {email}")
        
        if users_updated > 0:
            db.commit()
            print(f"[MIGRATION] ✅ {users_updated} contraseñas actualizadas")
        else:
            print("[MIGRATION] ✅ Todos los hashes están actualizados")
            
    except Exception as e:
        print(f"[MIGRATION] ⚠️  Error actualizando hashes: {e}")
        db.commit()

def init_db():
    import sys
    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()
    migrate_db()  # Aplicar migraciones
    
    # Cargar datos iniciales (asumimos BD nueva)
    try:
        print("[SEED] 🌱 Cargando datos iniciales...", file=sys.stderr, flush=True)
        # Obtener nueva conexión después de las migraciones
        db = get_db()
        load_seed_data(db)  # Pasar la conexión existente
        db.commit()  # Asegurar commit
        print("[SEED] ✅ Datos iniciales cargados exitosamente", file=sys.stderr, flush=True)
    except Exception as e:
        import traceback
        print(f"[SEED] ❌ Error cargando datos: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)

def cargar_stock_completo_desde_csv(db):
    """Carga los 247 repuestos desde el CSV completo"""
    csv_path = os.path.join(BASE_DIR, "DOCUMENTOS DML", "Copia de NUEVO STOCK DE REPUESTOS COMPLETO.csv")
    
    if not os.path.exists(csv_path):
        print(f"[STOCK CSV] ⚠️  No se encontró: {csv_path}")
        return 0
    
    print(f"[STOCK CSV] 📖 Cargando desde: {csv_path}")
    
    repuestos_cargados = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            
            # Saltar las primeras 4 filas (encabezados)
            for _ in range(4):
                next(reader, None)
            
            for idx, row in enumerate(reader, start=1):
                if len(row) < 11:
                    continue
                
                # Extraer datos (columnas C a J = índices 2 a 9)
                codigo = row[2].strip() if len(row) > 2 and row[2] else None
                item = row[3].strip() if len(row) > 3 and row[3] else None
                cantidad_str = row[4].strip() if len(row) > 4 and row[4] else "0"
                codigo_ubicacion = row[9].strip() if len(row) > 9 and row[9] else "SIN UBICACIÓN"
                
                # Validaciones
                if not codigo or not item:
                    continue
                
                # Convertir cantidad
                try:
                    cantidad = int(cantidad_str) if cantidad_str else 0
                except ValueError:
                    cantidad = 0
                
                # 1. Insertar en matriz_repuestos
                db.execute("""
                    INSERT OR IGNORE INTO matriz_repuestos 
                    (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                    VALUES (?, ?, ?, ?, ?, 'DML')
                """, (idx, codigo, item, cantidad, cantidad))
                
                # 2. Insertar en stock_ubicaciones (ubicación DML)
                db.execute("""
                    INSERT OR IGNORE INTO stock_ubicaciones 
                    (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                    VALUES (?, 'DML', ?, ?)
                """, (codigo, cantidad, codigo_ubicacion))
                
                repuestos_cargados += 1
                
                if idx % 50 == 0:
                    db.commit()
        
        db.commit()
        
        # 3. Inicializar stock RAYPAC con cantidades desde matriz_repuestos
        print("[STOCK CSV] 📦 Inicializando stock RAYPAC...")
        db.execute("""
            INSERT OR IGNORE INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
            SELECT codigo_repuesto, 'RAYPAC', cantidad_actual, 'SIN UBICACIÓN'
            FROM matriz_repuestos
            WHERE codigo_repuesto NOT IN (SELECT codigo_repuesto FROM stock_ubicaciones WHERE ubicacion = 'RAYPAC')
        """)
        db.commit()
        
        raypac_count = db.execute("SELECT COUNT(*) as total FROM stock_ubicaciones WHERE ubicacion = 'RAYPAC'").fetchone()['total']
        print(f"[STOCK CSV] ✅ {repuestos_cargados} repuestos cargados en DML, {raypac_count} en RAYPAC")
        return repuestos_cargados
        
    except Exception as e:
        print(f"[STOCK CSV] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def load_seed_data(db=None):
    """Carga datos iniciales en la base de datos - BASADO EN seed_data_minimal.py"""
    if db is None:
        db = get_db()
    
    # VERIFICAR SI YA HAY REPUESTOS CARGADOS
    check_repuestos = db.execute("SELECT COUNT(*) as total FROM matriz_repuestos").fetchone()
    if check_repuestos and check_repuestos['total'] > 0:
        print(f"[SEED] ⚠️  Ya hay {check_repuestos['total']} repuestos cargados. Saltando seed.")
        return
    
    print("[SEED] 🌱 Cargando datos iniciales completos...")
    
    # 1. CARGAR STOCK COMPLETO DESDE CSV (247 repuestos)
    print("[SEED] 📦 Cargando stock completo desde CSV...")
    repuestos_count = cargar_stock_completo_desde_csv(db)
    
    if repuestos_count == 0:
        # Si no se pudo cargar el CSV, usar datos de ejemplo
        print("[SEED] ⚠️  CSV no disponible, usando repuestos de ejemplo")
        repuestos = [
            ("A000001", "MOTOR DE ARRASTRE"),
            ("A000002", "MOTOR DE SELLADO"),
            ("A000003", "CUCHILLA SUPERIOR"),
            ("A000004", "RUEDA DE ARRASTRE"),
            ("A000005", "CARCAZA FRONTAL"),
            ("A000006", "SERVO MOTOR"),
            ("A000007", "RESORTE DE MANIJA"),
            ("A000008", "BATERIA 12V"),
            ("A000009", "CARGADOR 220V"),
            ("A000010", "BOTONERA COMPLETA"),
        ]
        
        for idx, (codigo, item) in enumerate(repuestos, start=1):
            db.execute("""
                INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                VALUES (?, ?, ?, 0, 0, 'DML')
            """, (idx, codigo, item))
        db.commit()
        
        # Stock RAYPAC de ejemplo
        stock_raypac = [
            ("A000001", 15), ("A000002", 8), ("A000003", 3), ("A000004", 2), ("A000005", 10),
            ("A000006", 1), ("A000007", 20), ("A000008", 5), ("A000009", 0), ("A000010", 12),
        ]
        
        for codigo, cant in stock_raypac:
            db.execute("""
                INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad)
                VALUES (?, 'RAYPAC', ?)
            """, (codigo, cant))
        db.commit()
        
        # Stock DML de ejemplo
        stock_dml = [
            ("A000001", 5), ("A000002", 3), ("A000003", 2), ("A000004", 1), ("A000005", 4),
            ("A000006", 0), ("A000007", 8), ("A000008", 2), ("A000009", 3), ("A000010", 6),
        ]
        
        for codigo, cant in stock_dml:
            db.execute("""
                INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad)
                VALUES (?, 'DML', ?)
            """, (codigo, cant))
            # Legacy stock_dml para compatibilidad
            db.execute("""
                INSERT INTO stock_dml (codigo_repuesto, item, cantidad, cantidad_minima, estado_alerta)
                SELECT ?, item, ?, 2, 'OK'
                FROM matriz_repuestos WHERE codigo_repuesto = ?
            """, (codigo, cant, codigo))
    
    # DATOS DE EJEMPLO REMOVIDOS - Solo CSV carga permanente
    print(f"[SEED] ✅ {repuestos_count} repuestos cargados desde CSV")
    print("[SEED] Sistema listo para usar")

# ======================== HELPERS ========================

def send_mail(to_email, subject, html_body):
    """Envía mail con manejo de errores y timeout."""
    try:
        # Verificar que email no esté vacío
        if not to_email or not to_email.strip():
            print(f"⚠️ Email destinatario vacío, saltando envío", file=sys.stderr, flush=True)
            return False
            
        # Verificar configuración SMTP
        if not app.config.get('MAIL_USERNAME'):
            print(f"⚠️ SMTP no configurado (MAIL_USERNAME vacío). Email NO enviado a {to_email}", file=sys.stderr, flush=True)
            print(f"   Asunto: {subject}", file=sys.stderr, flush=True)
            return False
        
        msg = MIMEMultipart('alternative')
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        print(f"📧 Intentando enviar email a {to_email}...", file=sys.stderr, flush=True)
        print(f"   Servidor: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}", file=sys.stderr, flush=True)
        
        # Timeout de 10 segundos para evitar bloqueos
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'], timeout=10) as server:
            if app.config['MAIL_USE_TLS']:
                server.starttls()
            if app.config['MAIL_USERNAME']:
                server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        
        print(f"✅ Mail enviado exitosamente a {to_email}", file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print(f"❌ Error enviando mail a {to_email}: {type(e).__name__}: {str(e)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        return False

def log_action(user_id, action, table_name, record_id=None, old_value=None, new_value=None):
    """Registra acción en auditoría."""
    db = get_db()
    db.execute(
        """INSERT INTO audit_log 
           (user_id, action, table_name, record_id, old_value, new_value)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, action, table_name, record_id, old_value, new_value)
    )
    db.commit()

def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        # Validar que el usuario exista en BD
        user = get_current_user()
        if not user:
            session.clear()
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def permission_required(read_roles=None, write_roles=None):
    """
    Decorator para control de permisos granular.
    - read_roles: roles que pueden VER (lectura)
    - write_roles: roles que pueden EDITAR (escritura)
    Si solo se pasa write_roles, automáticamente tienen read también.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            user = get_current_user()
            if not user:
                session.clear()
                return redirect(url_for("login"))
            
            user_role = user["role"]
            
            # ADMIN siempre tiene acceso completo
            if user_role == "ADMIN":
                return view(*args, **kwargs)
            
            # Verificar permisos de escritura (incluye lectura)
            if write_roles and user_role in write_roles:
                return view(*args, **kwargs)
            
            # Verificar permisos de solo lectura
            if read_roles and user_role in read_roles:
                # Pasar flag readonly a la vista
                kwargs['readonly'] = True
                return view(*args, **kwargs)
            
            flash("No tienes permiso para acceder a esta página.", "error")
            return redirect(url_for("index"))
        return wrapped
    return decorator

def role_required(*roles):
    """Compatibilidad con código antiguo - todos tienen escritura."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            user = get_current_user()
            if not user:
                session.clear()
                return redirect(url_for("login"))
            if user["role"] not in roles:
                flash("No tienes permiso para acceder a esta página.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

def check_stock_alert(codigo, ubicacion="DML"):
    """Verifica nivel de stock por ubicación y retorna estado de alerta."""
    db = get_db()
    stock = db.execute(
        "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = ? AND ubicacion = ?",
        (codigo, ubicacion)
    ).fetchone()

    # Fallback: si no existe en la ubicación, usar cualquier ubicación (último registro)
    if not stock:
        stock = db.execute(
            "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = ? ORDER BY updated_at DESC LIMIT 1",
            (codigo,)
        ).fetchone()

    if not stock:
        return "NO_EXISTE"

    qty = stock['cantidad']
    if qty == 0:
        return "ROJO"  # Falta completamente
    elif qty == 1:
        return "AMARILLO"  # Último repuesto
    elif qty == 2:
        return "NARANJA"  # Pocos repuestos
    else:
        return "OK"

def get_alert_badge(codigo, ubicacion="DML"):
    """Retorna HTML badge para mostrar nivel de alerta."""
    nivel = check_stock_alert(codigo, ubicacion)
    
    badge_config = {
        "ROJO": {"color": "#dc3545", "texto": "REPUESTO FALTANTE", "emoji": "🔴"},
        "AMARILLO": {"color": "#ffc107", "texto": "ÚLTIMO REPUESTO", "emoji": "⚠️"},
        "NARANJA": {"color": "#ff6600", "texto": "POCOS REPUESTOS", "emoji": "⚠️"},
        "OK": {"color": "#28a745", "texto": "DISPONIBLE", "emoji": "✅"},
        "NO_EXISTE": {"color": "#6c757d", "texto": "NO EXISTE", "emoji": "❓"}
    }
    
    config = badge_config.get(nivel, badge_config["OK"])
    return f'<span class="badge badge-alert" style="background-color: {config["color"]}; color: white; padding: 8px 12px; border-radius: 4px; font-weight: bold; display: inline-block; min-width: 140px; text-align: center;" title="{config["texto"]}">{config["emoji"]} {nivel}</span>'

def generate_ficha_number():
    """Genera el próximo número de ficha correlativo."""
    db = get_db()
    last = db.execute("SELECT MAX(numero_ficha) as max FROM dml_fichas").fetchone()
    return (last['max'] or 500) + 1

def generate_ticket_number(serial):
    """Genera número de ticket basado en número de serie: TK-{serie}."""
    # Nuevo formato simplificado: TK-{serie}
    return f"TK-{serial.upper()}"

def generate_remito_raypac():
    """Genera un número de remito RP-YYYY-00001 correlativo para envíos a ST."""
    db = get_db()
    year = datetime.now().year
    count = db.execute(
        "SELECT COUNT(*) as total FROM raypac_entries WHERE numero_remito LIKE ?",
        (f"RP-{year}-%",)
    ).fetchone()
    seq = (count['total'] or 0) + 1
    return f"RP-{year}-{seq:05d}"

def generate_remito_envio():
    """Genera remitos para envíos de repuestos (ER-YYYY-00001)."""
    db = get_db()
    year = datetime.now().year
    count = db.execute(
        "SELECT COUNT(*) as total FROM envios_repuestos WHERE numero_remito LIKE ?",
        (f"ER-{year}-%",)
    ).fetchone()
    seq = (count['total'] or 0) + 1
    return f"ER-{year}-{seq:05d}"

def ajustar_stock_ubicacion(codigo_repuesto, ubicacion, delta):
    """Suma/resta stock en una ubicación específica, evitando negativos."""
    db = get_db()
    row = db.execute(
        "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = ? AND ubicacion = ?",
        (codigo_repuesto, ubicacion)
    ).fetchone()
    if row:
        nueva_cantidad = row['cantidad'] + delta
        if nueva_cantidad < 0:
            raise ValueError(f"Stock insuficiente en {ubicacion} para {codigo_repuesto}")
        db.execute(
            "UPDATE stock_ubicaciones SET cantidad = ?, updated_at = CURRENT_TIMESTAMP WHERE codigo_repuesto = ? AND ubicacion = ?",
            (nueva_cantidad, codigo_repuesto, ubicacion)
        )
    else:
        if delta < 0:
            raise ValueError(f"No existe stock en {ubicacion} para {codigo_repuesto}")
        db.execute(
            "INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad) VALUES (?, ?, ?)",
            (codigo_repuesto, ubicacion, delta)
        )

def crear_ticket(ficha_id, numero_serie):
    """Crea un ticket de seguimiento para una ficha DML."""
    db = get_db()
    numero_ticket = generate_ticket_number(numero_serie)
    
    db.execute("""
        INSERT INTO tickets (numero_ticket, ficha_id, numero_serie)
        VALUES (?, ?, ?)
    """, (numero_ticket, ficha_id, numero_serie))
    
    # Actualizar ficha con número de ticket
    db.execute("UPDATE dml_fichas SET numero_ticket = ? WHERE id = ?", (numero_ticket, ficha_id))
    db.commit()
    
    return numero_ticket

def registrar_cambio_estado_ticket(ticket_id, estado_nuevo, usuario_id, motivo=None):
    """Registra cambio de estado en el historial del ticket."""
    db = get_db()
    ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    
    db.execute("""
        INSERT INTO ticket_historial (ticket_id, estado_anterior, estado_nuevo, usuario_id, motivo)
        VALUES (?, ?, ?, ?, ?)
    """, (ticket_id, ticket['estado'] if ticket else None, estado_nuevo, usuario_id, motivo))
    
    db.execute("UPDATE tickets SET estado = ? WHERE id = ?", (estado_nuevo, ticket_id))
    db.commit()

def verificar_alerta_stock(codigo_repuesto, ubicacion="DML"):
    """Verifica y registra alerta de stock por ubicación y dispara aviso si corresponde."""
    db = get_db()
    stock = db.execute(
        """
        SELECT su.cantidad, su.ubicacion, m.item
        FROM stock_ubicaciones su
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
        WHERE su.codigo_repuesto = ? AND su.ubicacion = ?
        """,
        (codigo_repuesto, ubicacion)
    ).fetchone()

    if not stock:
        stock = db.execute(
            """
            SELECT su.cantidad, su.ubicacion, m.item
            FROM stock_ubicaciones su
            LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
            WHERE su.codigo_repuesto = ?
            ORDER BY su.updated_at DESC
            LIMIT 1
            """,
            (codigo_repuesto,)
        ).fetchone()

    if not stock:
        return None

    nivel_alerta = check_stock_alert(codigo_repuesto, stock['ubicacion'])
    item_nombre = stock['item'] or codigo_repuesto

    if nivel_alerta in ["ROJO", "AMARILLO", "NARANJA"]:
        # Registrar alerta
        db.execute("""
            INSERT INTO stock_alertas (codigo_repuesto, item, cantidad_actual, nivel_alerta)
            VALUES (?, ?, ?, ?)
        """, (codigo_repuesto, item_nombre, stock['cantidad'], nivel_alerta))
        db.commit()

        # Enviar email de alerta
        enviar_alerta_stock(codigo_repuesto, item_nombre, stock['cantidad'], nivel_alerta, stock['ubicacion'])

        return nivel_alerta
    return None

def enviar_alerta_stock(codigo, item, cantidad, nivel, ubicacion="DML"):
    """Envía email de alerta de stock."""
    colores = {
        "ROJO": "Repuesto AGOTADO",
        "AMARILLO": "Último repuesto disponible",
        "NARANJA": "Pocos repuestos disponibles"
    }
    
    body = f"""
    <h2>⚠️ ALERTA DE STOCK</h2>
    <p><strong>Nivel: {colores.get(nivel, nivel)}</strong></p>
    <p>Código: <strong>{codigo}</strong></p>
    <p>Item: <strong>{item}</strong></p>
    <p>Cantidad actual: <strong>{cantidad}</strong></p>
    <p>Ubicación: <strong>{ubicacion}</strong></p>
    <p>Por favor, verifique el stock y considere reposición.</p>
    """
    
    # Enviar a repuestos@dml.local
    send_mail("repuestos@dml.local", f"🔔 Alerta de Stock: {item}", body)

def actualizar_estado_alerta_stock(codigo, ubicacion="DML"):
    """Recalcula estado_alerta en stock_dml tras movimientos para la ubicación dada."""
    db = get_db()
    existe = db.execute(
        "SELECT 1 FROM stock_dml WHERE codigo_repuesto = ?",
        (codigo,)
    ).fetchone()
    if not existe:
        return

    nivel = check_stock_alert(codigo, ubicacion)
    db.execute(
        "UPDATE stock_dml SET estado_alerta = ?, updated_at = CURRENT_TIMESTAMP WHERE codigo_repuesto = ?",
        (nivel, codigo)
    )
    db.commit()

def actualizar_estadistica_repuesto(codigo_repuesto, cantidad=1):
    """Actualiza estadísticas de uso de repuesto."""
    db = get_db()
    
    stats = db.execute(
        "SELECT * FROM estadisticas_repuestos WHERE codigo_repuesto = ?",
        (codigo_repuesto,)
    ).fetchone()
    
    if stats:
        db.execute("""
            UPDATE estadisticas_repuestos 
            SET cantidad_utilizada = cantidad_utilizada + ?,
                fecha_ultimo_uso = ?,
                total_usos = total_usos + 1
            WHERE codigo_repuesto = ?
        """, (cantidad, datetime.now().isoformat(), codigo_repuesto))
    else:
        # Obtener item de matriz
        item = db.execute(
            "SELECT item FROM matriz_repuestos WHERE codigo_repuesto = ?",
            (codigo_repuesto,)
        ).fetchone()
        
        db.execute("""
            INSERT INTO estadisticas_repuestos 
            (codigo_repuesto, item, cantidad_utilizada, fecha_ultimo_uso, total_usos)
            VALUES (?, ?, ?, ?, 1)
        """, (codigo_repuesto, item['item'] if item else None, cantidad, datetime.now().isoformat()))
    
    db.commit()

def generar_ficha_pdf(ficha_id):
    """Genera un PDF con la ficha de reparación completa - idéntico a la vista web."""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from datetime import datetime
    
    db = get_db()
    
    # Obtener datos de la ficha
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (ficha_id,)).fetchone()
    if not ficha:
        return None
    
    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (ficha['raypac_id'],)).fetchone()
    partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = ?", (ficha_id,)).fetchall()
    repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = ?", (ficha_id,)).fetchall()
    
    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.4*inch, bottomMargin=0.4*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    story = []
    
    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle('HeadingBox', parent=styles['Heading2'], fontSize=11, 
                                   textColor=colors.darkblue, spaceAfter=3, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=9)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)
    
    # ENCABEZADO: N° Ficha | número | INFORME DML SOBRE EL EQUIPO EN REVISION
    header_data = [[
        Paragraph("<b>N° Ficha</b>", small_style),
        Paragraph(f"<b>{ficha['numero_ficha']:07d}</b>", small_style),
        Paragraph("<b>INFORME DML SOBRE EL<br/>EQUIPO EN REVISIÓN</b>", ParagraphStyle('Centered', parent=small_style, alignment=1))
    ]]
    header_table = Table(header_data, colWidths=[1.2*inch, 1.2*inch, 3.6*inch])
    header_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.08*inch))
    story.append(Paragraph("<b>Servicio Técnico</b>", ParagraphStyle('Center', parent=normal_style, alignment=1)))
    story.append(Spacer(1, 0.15*inch))
    
    # INFORMACIÓN GENERAL (IZQUIERDA) + ESTADO DEL EQUIPO (DERECHA)
    # Columna izquierda: información general
    info_rows = [
        ["Ficha N°:", f"{ficha['numero_ficha']:07d}"],
        ["Ticket N°:", ficha['numero_ticket'] or ""],
        ["Fecha Ingreso DML:", ficha['fecha_ingreso']],
        ["Fecha Egreso DML:", ficha['fecha_egreso'] or ""],
        ["Técnico Responsable:", ficha['tecnico_resp'] or ""],
        ["Estado:", ficha['estado_reparacion']],
    ]
    
    if raypac:
        info_rows.extend([
            ["Fecha recepción Raypac:", raypac['fecha_recepcion']],
            ["Cliente:", raypac['cliente'] or ""],
            ["N° Serie:", raypac['numero_serie'] or ""],
            ["Modelo:", raypac['modelo_maquina'] or ""],
            ["Tipo Máquina:", raypac['tipo_maquina'] or ""],
            ["Comercial responsable:", raypac['comercial'] or ""],
            ["Batería N°:", raypac['numero_bateria'] or ""],
            ["Cargador N°:", raypac['numero_cargador'] or ""],
        ])
    
    left_table = Table(info_rows, colWidths=[2.6*inch, 2.7*inch])
    left_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))
    
    # Columna derecha: estado del equipo (partes)
    parts_rows = [["PARTE", "Estado"]]
    if partes:
        for p in partes:
            parts_rows.append([p['nombre_parte'] or "", p['estado'] or "POR INSPECCIONAR"])
    else:
        for i in range(12):
            parts_rows.append(["", ""])
    
    right_table = Table(parts_rows, colWidths=[1.5*inch, 1.8*inch])
    right_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    # Combinar columnas en una tabla de dos columnas
    combo_table = Table([[left_table, right_table]], colWidths=[5.3*inch, 3.3*inch])
    combo_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(combo_table)
    story.append(Spacer(1, 0.15*inch))
    
    # DIAGNÓSTICO INICIAL
    story.append(Paragraph("DIAGNÓSTICO DEL DEPARTAMENTO TÉCNICO", heading_style))
    diag_data = [[ficha['diagnostico_inicial'] or "Pendida de potencia, cuchilla gastada"]]
    diag_table = Table(diag_data, colWidths=[6*inch])
    diag_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 0.15*inch))
    
    # OBSERVACIONES
    story.append(Paragraph("OBSERVACIONES", heading_style))
    obs_data = [[ficha['observaciones'] or "Ingreso reciente, pendiente inspección inicial"]]
    obs_table = Table(obs_data, colWidths=[6*inch])
    obs_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(obs_table)
    story.append(Spacer(1, 0.15*inch))
    
    # DIAGNÓSTICO DE REPARACIÓN
    story.append(Paragraph("DIAGNÓSTICO DE REPARACIÓN", heading_style))
    rep_diag_data = [[ficha['diagnostico_reparacion'] or "Pendiente"]]
    rep_diag_table = Table(rep_diag_data, colWidths=[6*inch])
    rep_diag_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('MINHEIGHT', (0, 0), (-1, -1), 0.5*inch),
    ]))
    story.append(rep_diag_table)
    story.append(Spacer(1, 0.15*inch))
    
    # REPUESTOS COLOCADOS
    story.append(Paragraph("REPUESTOS COLOCADOS", heading_style))
    rep_rows = [["Cantidad", "Código", "DESCRIPCION", "ESTADO", "EN STOCK", "EN FALTA"]]
    if repuestos:
        for rep in repuestos:
            rep_rows.append([
                str(rep['cantidad_utilizada'] or 1),
                rep['codigo_repuesto'] or "",
                (rep['descripcion'] or '')[:25],
                rep['estado_repuesto'] or "",
                "✓" if rep['en_stock'] else "",
                "✗" if rep['en_falta'] else ""
            ])
    # Relleno hasta 10 filas
    while len(rep_rows) < 11:
        rep_rows.append(["", "", "", "", "", ""])
    
    rep_table = Table(rep_rows, colWidths=[0.7*inch, 1.0*inch, 2.0*inch, 0.9*inch, 0.8*inch, 0.7*inch])
    rep_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#808080')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(rep_table)
    story.append(Spacer(1, 0.15*inch))
    
    # FILA SEPARADA - Ciclos
    story.append(Spacer(1, 0.05*inch))
    ciclos_rows = [["N° DE CICLOS DE LA MÁQUINA CON LAS QUE SALE DE ST", str(ficha['n_ciclos'] or 0)]]
    ciclos_table = Table(ciclos_rows, colWidths=[5.3*inch, 1.2*inch])
    ciclos_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    story.append(ciclos_table)
    story.append(Spacer(1, 0.15*inch))
    
    # MARCAR CON UNA CRUZ LO QUE CORRESPONDA
    story.append(Paragraph("MARCAR CON UNA CRUZ LO QUE CORRESPONDA", heading_style))
    marca_rows = [
        ["TIPO DE MÁQUINA QUE INGRESO AL ST", raypac['tipo_maquina'] if raypac else "A BATERIA"],
        ["El módulo reparación Base es de tres (3hs)", "A DEFINIR"],
        ["HORAS ADICIONALES DE TRABAJO", ficha['horas_adic'] or "NO APLICA"],
        ["MECANIZADO ADICIONAL REALIZADO A LA MAQUINA", ficha['mecanizado_adic'] or "NO APLICA"],
        ["TIPO DE TRABAJO REALIZADO", "REPARACIÓN"],
        ["TÉCNICO RESPONSABLE DEL ST DE DML", ficha['tecnico_resp'] or ""],
    ]
    marca_table = Table(marca_rows, colWidths=[5.3*inch, 1.2*inch])
    marca_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(marca_table)
    
    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Disponibilizar helpers en templates (después de que sean definidos)
app.jinja_env.globals.update(get_alert_badge=get_alert_badge)

# ======================== AUTH ========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        print(f"[LOGIN] Intento - Email: {email}, Password: {'*' * len(password)}")
        
        if not email or not password:
            flash("Email y contraseña son requeridos.", "error")
            return render_template("login.html")
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        print(f"[LOGIN] Usuario encontrado: {user is not None}")
        
        if user:
            print(f"[LOGIN] Hash en BD: {user['password_hash'][:50]}...")
            pwd_match = check_password_hash(user["password_hash"], password)
            print(f"[LOGIN] Contraseña coincide: {pwd_match}")
            
            if pwd_match:
                if not user["is_active"]:
                    flash("Usuario desactivado.", "error")
                    return render_template("login.html")
                session["user_id"] = user["id"]
                session.modified = True
                flash(f"Bienvenido {email}", "success")
                print(f"[LOGIN] Sesion creada para user_id: {user['id']}")
                return redirect(url_for("index"))
        
        flash("Credenciales inválidas.", "error")
        print(f"[LOGIN] Credenciales rechazadas para {email}")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    user = get_current_user()
    
    # Validación de seguridad - si user es None, redirigir al login
    if not user:
        session.clear()
        return redirect(url_for("login"))
    
    db = get_db()

    def count(sql, params=()):
        return db.execute(sql, params).fetchone()['total']

    role = user['role']
    stats = {}

    if role == "RAYPAC":
        stats = {
            "equipos_registrados": count("SELECT COUNT(*) AS total FROM raypac_entries"),
            "equipos_sin_remito": count("SELECT COUNT(*) AS total FROM raypac_entries WHERE numero_remito IS NULL OR numero_remito = ''"),
            "envios_pendientes": count("SELECT COUNT(*) AS total FROM envios_repuestos WHERE estado_envio = 'ENVIADO'"),
            "tickets_activos": count("SELECT COUNT(*) AS total FROM tickets WHERE estado = 'ACTIVO'")
        }
    elif role == "DML_REPUESTOS":
        stats = {
            "stock_bajo": count("SELECT COUNT(*) AS total FROM stock_ubicaciones WHERE ubicacion = 'DML' AND cantidad <= 2"),
            "envios_pendientes": count("SELECT COUNT(*) AS total FROM envios_repuestos WHERE estado = 'PENDIENTE'"),
            "fichas_espera_repuestos": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion = 'A LA ESPERA DE REPUESTOS'"),
            "tickets_activos": count("SELECT COUNT(*) AS total FROM tickets WHERE estado != 'CERRADO'")
        }
    elif role == "DML_ST":
        # Equipos freezados en RAYPAC (con remito) sin ficha DML creada = pendientes de recepción
        equipos_pendientes = db.execute("""
            SELECT COUNT(*) AS total 
            FROM raypac_entries r 
            WHERE r.is_frozen = 1 
            AND r.numero_remito IS NOT NULL 
            AND NOT EXISTS (SELECT 1 FROM dml_fichas f WHERE f.raypac_id = r.id)
        """).fetchone()['total']
        
        # Repuestos que estaban EN FALTA y ahora tienen stock disponible
        repuestos_disponibles = db.execute("""
            SELECT COUNT(DISTINCT dr.codigo_repuesto) AS total
            FROM dml_repuestos dr
            JOIN dml_fichas f ON f.id = dr.ficha_id
            JOIN stock_ubicaciones su ON su.codigo_repuesto = dr.codigo_repuesto AND su.ubicacion = 'DML'
            WHERE dr.en_falta = 1 
            AND f.is_closed = 0
            AND su.cantidad >= dr.cantidad_utilizada
        """).fetchone()['total']
        
        stats = {
            "fichas_revision_inicial": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion LIKE 'A LA ESPERA DE REVISI_N' AND is_closed = 0"),
            "fichas_en_reparacion": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion LIKE 'EN REPARACI_N' AND is_closed = 0"),
            "fichas_espera_repuestos": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion = 'A LA ESPERA DE REPUESTOS' AND is_closed = 0"),
            "fichas_listas": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE estado_reparacion LIKE 'M_QUINA LISTA PARA RETIRAR' AND is_closed = 0"),
            "equipos_raypac_pendientes": equipos_pendientes,
            "tickets_activos": count("SELECT COUNT(*) AS total FROM tickets WHERE estado != 'CERRADO'"),
            "repuestos_disponibles": repuestos_disponibles
        }
    else:  # ADMIN
        stats = {
            "equipos_raypac": count("SELECT COUNT(*) AS total FROM raypac_entries"),
            "fichas_abiertas": count("SELECT COUNT(*) AS total FROM dml_fichas WHERE is_closed = 0"),
            "envios_pendientes": count("SELECT COUNT(*) AS total FROM envios_repuestos WHERE estado = 'PENDIENTE'"),
            "stock_bajo_total": count("SELECT COUNT(*) AS total FROM stock_ubicaciones WHERE cantidad <= 2")
        }

    return render_template("index.html", user=user, stats=stats)

# ======================== APLICAR MIGRACIONES AL INICIAR ========================

@app.before_request
def apply_migrations():
    """Aplica migraciones de BD al iniciar la app"""
    if not hasattr(app, '_migrations_applied'):
        try:
            # Si la BD no existe, crearla (init_db incluye seed automático)
            db_path = app.config["DATABASE"]
            if not os.path.exists(db_path):
                print("📁 Base de datos no encontrada. Inicializando...")
                init_db()
            else:
                # Si existe, aplicar migraciones
                migrate_db()
        except Exception as e:
            print(f"Error en migraciones: {e}")
            import traceback
            traceback.print_exc()
        app._migrations_applied = True

# ======================== RAYPAC ========================

@app.route("/raypac")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["RAYPAC"])
def raypac_list(readonly=False):
    user = get_current_user()
    db = get_db()
    entries = db.execute("""
        SELECT r.*, 
               (SELECT COUNT(*) FROM dml_fichas f WHERE f.raypac_id = r.id) AS fichas_count,
               (SELECT f.id FROM dml_fichas f WHERE f.raypac_id = r.id ORDER BY f.created_at DESC LIMIT 1) AS ficha_id,
               (SELECT f.estado_reparacion FROM dml_fichas f WHERE f.raypac_id = r.id ORDER BY f.created_at DESC LIMIT 1) AS estado_ficha,
               (SELECT t.id FROM tickets t WHERE t.raypac_id = r.id ORDER BY t.created_at DESC LIMIT 1) AS ticket_id,
               (SELECT t.numero_ticket FROM tickets t WHERE t.raypac_id = r.id ORDER BY t.created_at DESC LIMIT 1) AS ticket_numero
        FROM raypac_entries r
        ORDER BY r.created_at DESC
    """).fetchall()
    
    # Configuración de badges para estados de fichas DML
    estado_config = {
        "REVISION_INICIAL": {"color": "#17a2b8", "texto": "Revisión Inicial"},
        "EN_REPARACION": {"color": "#ffc107", "texto": "En Reparación"},
        "PAUSADA": {"color": "#fd7e14", "texto": "Pausada"},
        "FINALIZADA": {"color": "#28a745", "texto": "Finalizada"},
        "ENTREGADA": {"color": "#6c757d", "texto": "Entregada"}
    }
    
    return render_template("raypac_list.html", entries=entries, user_role=user['role'], readonly=readonly, estado_config=estado_config)

@app.route("/raypac/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_new():
    user = get_current_user()
    db = get_db()
    
    if request.method == "POST":
        try:
            fecha = request.form.get("fecha_recepcion") or datetime.now().strftime("%Y-%m-%d")
            tipo_solicitud = request.form.get("tipo_solicitud")
            cliente = request.form.get("cliente")
            numero_serie = request.form.get("numero_serie")
            modelo = request.form.get("modelo_maquina")
            tipo_maquina = request.form.get("tipo_maquina")
            numero_bateria = request.form.get("numero_bateria") or "NO APLICA"
            numero_cargador = request.form.get("numero_cargador") or "NO APLICA"
            diagnostico = request.form.get("diagnostico_ingreso")
            comercial = request.form.get("comercial")
            mail_comercial = request.form.get("mail_comercial")
            contacto_cliente = request.form.get("contacto_cliente")
            email_cliente = request.form.get("email_cliente")
            
            # Validación básica
            if not all([tipo_solicitud, cliente, numero_serie, modelo, tipo_maquina, comercial, mail_comercial]):
                flash("Por favor completa todos los campos obligatorios.", "error")
                return render_template("raypac_form.html")
            
            # Verificar que el número de serie es único
            existe = db.execute("SELECT id FROM raypac_entries WHERE numero_serie = ?", (numero_serie,)).fetchone()
            if existe:
                flash("Este número de serie ya existe en el sistema.", "error")
                return render_template("raypac_form.html")

            # Número correlativo interno
            correlativo = db.execute("SELECT COALESCE(MAX(numero_correlativo), 0) + 1 AS next FROM raypac_entries").fetchone()['next']
            
            db.execute("""
                INSERT INTO raypac_entries 
                (numero_correlativo, fecha_recepcion, tipo_solicitud, cliente, numero_serie, modelo_maquina, tipo_maquina,
                 numero_bateria, numero_cargador, diagnostico_ingreso, comercial, mail_comercial, contacto_cliente, email_cliente)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (correlativo, fecha, tipo_solicitud, cliente, numero_serie, modelo, tipo_maquina,
                  numero_bateria, numero_cargador, diagnostico, comercial, mail_comercial, contacto_cliente, email_cliente))
            db.commit()
            
            raypac_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
            log_action(user['id'], "CREATE", "raypac_entries", raypac_id, None, 
                      f"Ingreso RAYPAC: {cliente} - {numero_serie}")
            
            flash("Ingreso RAYPAC registrado correctamente.", "success")
            return redirect(url_for("raypac_view", id=raypac_id))
        except Exception as e:
            flash(f"Error al guardar: {str(e)}", "error")
            return render_template("raypac_form.html")
    
    return render_template("raypac_form.html")

@app.route("/raypac/<int:id>")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["RAYPAC"])
def raypac_view(id, readonly=False):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    return render_template("raypac_view.html", entry=entry, user_role=user['role'], readonly=readonly)

@app.route("/raypac/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_edit(id):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    if entry['is_frozen'] and not request.form.get("unfreeze_code"):
        flash("Este registro está freezado. Requiere código de desbloqueo.", "error")
        return render_template("raypac_view.html", entry=entry)
    
    if request.method == "POST":
        try:
            unfreeze_code = request.form.get("unfreeze_code")
            if entry['is_frozen'] and unfreeze_code != "ADMIN2024":
                flash("Código de desbloqueo incorrecto.", "error")
                return render_template("raypac_view.html", entry=entry)
            
            fecha = request.form.get("fecha_recepcion")
            tipo_solicitud = request.form.get("tipo_solicitud")
            cliente = request.form.get("cliente")
            numero_serie = request.form.get("numero_serie")
            diagnostico = request.form.get("diagnostico_ingreso")
            comercial = request.form.get("comercial")
            mail_comercial = request.form.get("mail_comercial")
            contacto_cliente = request.form.get("contacto_cliente")
            email_cliente = request.form.get("email_cliente")
            
            db.execute("""
                UPDATE raypac_entries 
                SET fecha_recepcion=?, tipo_solicitud=?, cliente=?, numero_serie=?,
                    diagnostico_ingreso=?, comercial=?, mail_comercial=?, contacto_cliente=?, email_cliente=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ?
            """, (fecha, tipo_solicitud, cliente, numero_serie, diagnostico, comercial, mail_comercial, contacto_cliente, email_cliente, id))
            db.commit()
            
            log_action(user['id'], "UPDATE", "raypac_entries", id, None, 
                      f"Actualización: {cliente}")
            
            flash("Ingreso RAYPAC actualizado.", "success")
            return redirect(url_for("raypac_view", id=id))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template("raypac_form.html", entry=entry, edit=True)

@app.route("/raypac/<int:id>/freeze", methods=["POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def raypac_freeze(id):
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    numero_remito = (request.form.get("numero_remito") or "").strip()
    
    # CAMBIO DAVID: Remito OBLIGATORIO con formato ####-#### (8 dígitos)
    if not numero_remito:
        flash("⚠️ El número de remito es OBLIGATORIO para freezar y enviar. Formato: últimos 4 dígitos o completo ####-####.", "error")
        return redirect(url_for("raypac_view", id=id))
    
    # Auto-completar formato si solo ingresa 4 dígitos (últimos)
    import re
    if re.match(r'^\d{1,4}$', numero_remito):
        # Usuario ingresó solo números (1-4 dígitos), auto-completar
        ultimo = numero_remito.zfill(4)  # Rellenar con ceros a la izquierda
        numero_remito = f"00001-{ultimo}"  # Formato: 00001-XXXX
        flash(f"📋 Remito auto-completado: {numero_remito}", "info")
    elif not re.match(r'^\d{4,5}-\d{4,7}$', numero_remito):
        flash("⚠️ Formato de remito inválido. Ingresa solo los últimos 4 dígitos (ej: 4222) o el formato completo ####-#### (ej: 00001-04222).", "error")
        return redirect(url_for("raypac_view", id=id))
    
    # Verificar que no exista ya
    existe = db.execute("SELECT id FROM raypac_entries WHERE numero_remito = ?", (numero_remito,)).fetchone()
    if existe and existe['id'] != id:
        flash("El número de remito ya existe.", "error")
        return redirect(url_for("raypac_view", id=id))
    
    db.execute("""
        UPDATE raypac_entries 
        SET is_frozen = 1, frozen_at = CURRENT_TIMESTAMP, numero_remito = ?
        WHERE id = ?
    """, (numero_remito, id))
    db.commit()
    
    log_action(user['id'], "FREEZE", "raypac_entries", id, None, 
              f"Freezado con remito {numero_remito}")
    
    flash("Máquina freezada y enviada a ST.", "success")
    return redirect(url_for("raypac_view", id=id))

@app.route("/raypac/<int:id>/unfreeze", methods=["POST"])
@login_required
@role_required("ADMIN")  # RESTRICCIÓN: Solo ADMIN puede desfreezar
def raypac_unfreeze(id):
    """Descongelar un ingreso RAYPAC con código (solo ADMIN)"""
    user = get_current_user()
    db = get_db()
    entry = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (id,)).fetchone()
    
    if not entry:
        flash("Registro no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    if not entry['is_frozen']:
        flash("El registro no está freezado.", "error")
        return redirect(url_for("raypac_view", id=id))
    
    unfreeze_code = request.form.get("unfreeze_code", "").strip()
    
    # CAMBIO DAVID: Verificar código usando últimos 4 dígitos del remito
    # Formato remito: 0000-0000, últimos 4 dígitos = "0000" después del guión
    if entry['numero_remito'] and '-' in entry['numero_remito']:
        codigo_correcto = entry['numero_remito'].split('-')[-1]  # Últimos 4 dígitos
    else:
        codigo_correcto = entry['numero_remito'][-4:] if entry['numero_remito'] else ""
    
    if unfreeze_code != codigo_correcto:
        flash(f"⚠️ Código incorrecto. Use los últimos 4 dígitos del remito ({entry['numero_remito']}).", "error")
        return redirect(url_for("raypac_view", id=id))
    
    db.execute("""
        UPDATE raypac_entries 
        SET is_frozen = 0, frozen_at = NULL
        WHERE id = ?
    """, (id,))
    db.commit()
    
    log_action(user['id'], "UNFREEZE", "raypac_entries", id, None, "Descongelado")
    
    flash("✅ Máquina descongelada correctamente.", "success")
    return redirect(url_for("raypac_view", id=id))

# ======================== DML - FICHAS ========================

@app.route("/dml")
@login_required
@permission_required(read_roles=["RAYPAC", "DML_REPUESTOS"], write_roles=["DML_ST"])
def dml_list(readonly=False):
    user = get_current_user()
    db = get_db()
    fichas = db.execute("""
        SELECT f.*, r.cliente, r.numero_serie 
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        WHERE f.is_closed = 0
        ORDER BY f.created_at DESC
    """).fetchall()
    
    return render_template("dml_list.html", fichas=fichas, user_role=user['role'], readonly=readonly)

@app.route("/dml/entregadas")
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
def dml_entregadas():
    user = get_current_user()
    db = get_db()
    fichas = db.execute("""
        SELECT f.*, r.cliente, r.numero_serie, r.contacto_cliente, r.email_cliente
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        WHERE f.estado_reparacion = 'ENTREGADA'
        ORDER BY f.fecha_entrega_cliente DESC, f.updated_at DESC
    """).fetchall()
    
    return render_template("dml_entregadas.html", fichas=fichas, user_role=user['role'])

@app.route("/tickets/nuevo/<int:raypac_id>", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
def ticket_nuevo(raypac_id):
    """Crear ticket inicial desde RAYPAC freezado (nuevo flujo)."""
    user = get_current_user()
    db = get_db()
    
    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (raypac_id,)).fetchone()
    if not raypac:
        flash("Ingreso RAYPAC no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    if not raypac['is_frozen']:
        flash("El ingreso RAYPAC debe estar freezado para crear un ticket.", "error")
        return redirect(url_for("raypac_view", id=raypac_id))
    
    # Verificar si ya existe ticket para este RAYPAC
    ticket_existente = db.execute(
        "SELECT * FROM tickets WHERE raypac_id = ?", (raypac_id,)
    ).fetchone()
    
    if ticket_existente:
        flash(f"Ya existe un ticket para este ingreso: {ticket_existente['numero_ticket']}", "info")
        return redirect(url_for("ticket_view", numero_ticket=ticket_existente['numero_ticket']))
    
    if request.method == "POST":
        try:
            # Obtener datos del formulario
            fecha_ingreso = request.form.get("fecha_ingreso") or raypac['fecha_recepcion']
            tecnico_responsable = request.form.get("tecnico_responsable", "").strip()
            observaciones = request.form.get("observaciones", "").strip()
            
            # Componentes del estado del equipo
            estado_equipo = request.form.get("estado_equipo", "BUENO")
            carcaza = request.form.get("carcaza", "BUENO")
            cubre_feedwheel = request.form.get("cubre_feedwheel", "BUENO")
            mango = request.form.get("mango", "BUENO")
            botones = request.form.get("botones", "BUENO")
            motor_arrastre = request.form.get("motor_arrastre", "BUENO")
            motor_sellado = request.form.get("motor_sellado", "BUENO")
            cuchilla = request.form.get("cuchilla", "BUENO")
            servo = request.form.get("servo", "BUENO")
            rueda_arrastre = request.form.get("rueda_arrastre", "BUENO")
            resorte_manija = request.form.get("resorte_manija", "BUENO")
            otros = request.form.get("otros", "BUENO")
            
            # Validación
            if not tecnico_responsable:
                flash("El técnico responsable es obligatorio.", "error")
                return render_template("ticket_nuevo.html", raypac=raypac)
            
            # Generar número de ticket: TK-{serie}
            numero_ticket = generate_ticket_number(raypac['numero_serie'])
            
            # Crear ticket sin ficha_id (será NULL hasta que se cree la ficha)
            db.execute("""
                INSERT INTO tickets 
                (numero_ticket, raypac_id, numero_serie, estado, ficha_id,
                 fecha_ingreso, tecnico_responsable, observaciones,
                 estado_equipo, carcaza, cubre_feedwheel, mango, botones,
                 motor_arrastre, motor_sellado, cuchilla, servo,
                 rueda_arrastre, resorte_manija, otros)
                VALUES (?, ?, ?, 'ACTIVO', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (numero_ticket, raypac_id, raypac['numero_serie'], 
                  fecha_ingreso, tecnico_responsable, observaciones,
                  estado_equipo, carcaza, cubre_feedwheel, mango, botones,
                  motor_arrastre, motor_sellado, cuchilla, servo,
                  rueda_arrastre, resorte_manija, otros))
            
            db.commit()
            
            ticket_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
            
            log_action(user['id'], "CREATE", "tickets", ticket_id, None, 
                      f"Ticket inicial creado: {numero_ticket}")
            
            # Enviar email al comercial con el ticket
            if raypac['mail_comercial']:
                html_body = f"""
                <html>
                <head><style>
                    body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                    .email-container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; }}
                    .header {{ background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 20px; border-radius: 5px; text-align: center; }}
                    .ticket-box {{ border: 3px solid #2c3e50; padding: 20px; margin: 20px 0; border-radius: 8px; background-color: #ecf0f1; }}
                    .ticket-num {{ font-size: 32px; font-weight: bold; color: #e74c3c; text-align: center; margin: 10px 0; }}
                    .info-row {{ margin: 8px 0; padding: 5px 0; border-bottom: 1px solid #bdc3c7; }}
                    .label {{ font-weight: bold; color: #2c3e50; }}
                </style></head>
                <body>
                <div class="email-container">
                    <div class="header">
                        <h1>🎫 TICKET DE SEGUIMIENTO CREADO</h1>
                    </div>
                    <p>Estimado {raypac['comercial']},</p>
                    <p>Se ha generado un ticket de seguimiento para el equipo recibido:</p>
                    <div class="ticket-box">
                        <div class="ticket-num">{numero_ticket}</div>
                        <div class="info-row"><span class="label">Cliente:</span> {raypac['cliente']}</div>
                        <div class="info-row"><span class="label">Número de Serie:</span> {raypac['numero_serie']}</div>
                        <div class="info-row"><span class="label">Modelo:</span> {raypac['modelo_maquina']}</div>
                        <div class="info-row"><span class="label">Estado:</span> Pendiente de Revisión</div>
                    </div>
                    <p>Utilice este número de ticket para hacer seguimiento del estado de su equipo.</p>
                    <p style="color: #7f8c8d; font-size: 12px; text-align: center; margin-top: 20px;">DML Electricidad Industrial SRL - Servicio Técnico</p>
                </div>
                </body>
                </html>
                """
                send_mail(raypac['mail_comercial'], 
                         f"🎫 Ticket de Seguimiento: {numero_ticket}",
                         html_body)
            
            flash(f"✅ Ticket {numero_ticket} creado exitosamente.", "success")
            return redirect(url_for("ticket_view", numero_ticket=numero_ticket))
            
        except Exception as e:
            flash(f"Error al crear ticket: {str(e)}", "error")
    
    return render_template("ticket_nuevo.html", raypac=raypac)

@app.route("/dml/new/<int:raypac_id>", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_new(raypac_id):
    user = get_current_user()
    db = get_db()
    
    raypac = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (raypac_id,)).fetchone()
    if not raypac:
        flash("Ingreso RAYPAC no encontrado.", "error")
        return redirect(url_for("raypac_list"))
    
    # Buscar si existe un ticket asociado a este RAYPAC (nuevo flujo)
    ticket = db.execute("SELECT * FROM tickets WHERE raypac_id = ? AND ficha_id IS NULL", (raypac_id,)).fetchone()
    
    if request.method == "POST":
        try:
            fecha_ingreso = request.form.get("fecha_ingreso") or datetime.now().strftime("%Y-%m-%d")
            tecnico = request.form.get("tecnico")
            # CAMBIO DAVID: No usar diagnostico_inicial, ya viene de RAYPAC (diagnostico_ingreso)
            observaciones = request.form.get("observaciones")
            n_ciclos = request.form.get("n_ciclos") or 0
            tecnico_resp = request.form.get("tecnico_resp")
            
            if not all([tecnico, tecnico_resp]):
                flash("Completa los campos obligatorios.", "error")
                return render_template("dml_form.html", raypac=raypac, ticket=ticket)
            
            numero_ficha = generate_ficha_number()
            
            # Si existe ticket, asociar la ficha con él
            if ticket:
                db.execute("""
                    INSERT INTO dml_fichas 
                    (numero_ficha, raypac_id, ticket_id, numero_ticket, fecha_ingreso, tecnico,
                     observaciones, n_ciclos, tecnico_resp,
                     estado_reparacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (numero_ficha, raypac_id, ticket['id'], ticket['numero_ticket'], fecha_ingreso, tecnico,
                      observaciones, n_ciclos, tecnico_resp, 'REVISION_INICIAL'))
                
                ficha_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
                
                # Actualizar ticket con el ficha_id
                db.execute("UPDATE tickets SET ficha_id = ? WHERE id = ?", (ficha_id, ticket['id']))
                
                numero_ticket = ticket['numero_ticket']
            else:
                # Flujo antiguo: crear ficha sin ticket previo
                db.execute("""
                    INSERT INTO dml_fichas 
                    (numero_ficha, raypac_id, fecha_ingreso, tecnico,
                     observaciones, n_ciclos, tecnico_resp,
                     estado_reparacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (numero_ficha, raypac_id, fecha_ingreso, tecnico,
                      observaciones, n_ciclos, tecnico_resp, 'REVISION_INICIAL'))
                
                ficha_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
                
                # Crear ticket después (flujo antiguo)
                numero_ticket = crear_ticket(ficha_id, raypac['numero_serie'])
            
            db.commit()
            
            # Crear partes estándar
            partes = [
                "ESTADO DEL EQUIPO", "CARCAZA", "CUBRE FEEDWHEEL", "MANGO",
                "BOTONES", "MOTOR DE ARRASTRE", "MOTOR DE SELLADO", "CUCHILLA",
                "SERVO", "RUEDA DE ARRASTRE", "RESORTE DE MANIJA", "OTROS"
            ]
            for parte in partes:
                db.execute(
                    "INSERT INTO dml_partes (ficha_id, nombre_parte, estado) VALUES (?, ?, ?)",
                    (ficha_id, parte, "POR INSPECCIONAR")
                )
            db.commit()
            
            log_action(user['id'], "CREATE", "dml_fichas", ficha_id, None,
                      f"Ficha DML #{numero_ficha} - Ticket: {numero_ticket}")
            
            # CAMBIO DAVID: Redirigir directamente a EDICIÓN en lugar de vista
            flash(f"Ficha #{numero_ficha} creada correctamente. Ticket: {numero_ticket}", "success")
            return redirect(url_for("dml_edit", id=ficha_id))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return render_template("dml_form.html", raypac=raypac, ticket=ticket)
    
    return render_template("dml_form.html", raypac=raypac, ticket=ticket)

@app.route("/dml/<int:id>")
@login_required
@permission_required(read_roles=["RAYPAC", "DML_REPUESTOS"], write_roles=["DML_ST"])
def dml_view(id, readonly=False):
    user = get_current_user()
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    # Obtener datos de RAYPAC
    raypac = None
    if ficha['raypac_id']:
        raypac = db.execute(
            "SELECT * FROM raypac_entries WHERE id = ?",
            (ficha['raypac_id'],)
        ).fetchone()
    
    partes = db.execute(
        "SELECT * FROM dml_partes WHERE ficha_id = ? ORDER BY id",
        (id,)
    ).fetchall()
    
    repuestos = db.execute(
        "SELECT * FROM dml_repuestos WHERE ficha_id = ? ORDER BY id",
        (id,)
    ).fetchall()
    
    return render_template("dml_view.html", ficha=ficha, raypac=raypac, partes=partes, repuestos=repuestos, 
                           user_role=user['role'], readonly=readonly)

@app.route("/dml/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_edit(id):
    user = get_current_user()
    db = get_db()
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    if ficha['is_closed'] and not request.form.get("unfreeze_code"):
        flash("Esta ficha está cerrada. Requiere código para editar.", "error")
        return redirect(url_for("dml_view", id=id))
    
    if request.method == "POST":
        try:
            unfreeze_code = request.form.get("unfreeze_code")
            if ficha['is_closed'] and unfreeze_code != "ADMIN2024":
                flash("Código incorrecto.", "error")
                return redirect(url_for("dml_view", id=id))
            
            # Capturar SOLO los campos editables (no los de RAYPAC)
            fecha_ingreso = request.form.get("fecha_ingreso")
            fecha_egreso = request.form.get("fecha_egreso")
            
            estado = request.form.get("estado_reparacion")
            # CAMBIO DAVID: No usar diagnostico_inicial, ya viene de RAYPAC
            diagnostico_rep = request.form.get("diagnostico_reparacion")
            observaciones = request.form.get("observaciones")
            n_ciclos = request.form.get("n_ciclos")
            mecanizado = request.form.get("mecanizado_adic") or "NO APLICA"
            horas = request.form.get("horas_adic") or 0
            numero_remito = request.form.get("numero_remito_salida")
            tecnico_resp = request.form.get("tecnico_resp") or ""
            
            # Validación de flujo lógico de estados según documento David
            # Orden lógico: A LA ESPERA DE REVISIÓN → EN REPARACIÓN → [A LA ESPERA DE REPUESTOS] → MÁQUINA LISTA PARA RETIRAR → MÁQUINA ENTREGADA
            estados_orden = {
                'A LA ESPERA DE REVISIÓN': 0,
                'EN REPARACION': 1,
                'A LA ESPERA DE REPUESTOS': 1,  # Mismo nivel que EN REPARACION (puede ir y volver)
                'REPARACIÓN COMPLETADA': 2,
                'MÁQUINA LISTA PARA RETIRAR': 3,
                'MÁQUINA ENTREGADA': 4,
                'FINALIZADO': 5
            }
            
            estado_actual_nivel = estados_orden.get(ficha['estado_reparacion'], 0)
            estado_nuevo_nivel = estados_orden.get(estado, 0)
            
            # Prevenir retrocesos ilógicos (salvo entre EN REPARACION y A LA ESPERA DE REPUESTOS)
            if estado_actual_nivel >= 3 and estado_nuevo_nivel < estado_actual_nivel:
                # No permitir retrocesos desde MÁQUINA LISTA o posterior
                flash(f"⚠️ No se puede retroceder de '{ficha['estado_reparacion']}' a '{estado}'. Para cambios contacte al administrador.", "error")
                return redirect(url_for("dml_edit", id=id))
            
            # Actualizar SOLO los campos que existen en dml_fichas
            db.execute("""
                UPDATE dml_fichas 
                SET fecha_ingreso=?, fecha_egreso=?,
                    estado_reparacion=?, diagnostico_reparacion=?, observaciones=?,
                    n_ciclos=?, mecanizado_adic=?, horas_adic=?, numero_remito_salida=?,
                    tecnico_resp=?, updated_at=CURRENT_TIMESTAMP
                WHERE id = ?
            """, (fecha_ingreso, fecha_egreso,
                  estado, diagnostico_rep, observaciones,
                  n_ciclos, mecanizado, horas, numero_remito,
                  tecnico_resp, id))
            db.commit()
            
            # Actualizar partes
            partes = db.execute("SELECT id FROM dml_partes WHERE ficha_id = ? ORDER BY id", (id,)).fetchall()
            for idx, parte in enumerate(partes):
                estado_parte = request.form.get(f"parte_{idx}")
                if estado_parte:
                    db.execute(
                        "UPDATE dml_partes SET estado = ? WHERE id = ?",
                        (estado_parte, parte['id'])
                    )
            db.commit()
            
            log_action(user['id'], "UPDATE", "dml_fichas", id, None, f"Actualización ficha")
            
            flash("Ficha actualizada correctamente.", "success")
            return redirect(url_for("dml_view", id=id))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = ?", (id,)).fetchall()
    repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = ?", (id,)).fetchall()
    
    # Convertir Row a dict para serialización JSON
    partes = [dict(p) for p in partes]
    repuestos = [dict(r) for r in repuestos]
    ficha = dict(ficha)
    
    return render_template("dml_edit.html", ficha=ficha, partes=partes, repuestos=repuestos)

# ======================== REPUESTOS ========================

@app.route("/dml/<int:id>/repuestos/agregar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def agregar_repuesto(id):
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_edit", id=id))
    
    # Validar cantidad máxima (15 repuestos)
    count = db.execute("SELECT COUNT(*) as cnt FROM dml_repuestos WHERE ficha_id = ?", (id,)).fetchone()
    if count['cnt'] >= 15:
        flash("Máximo 15 repuestos por ficha.", "error")
        return redirect(url_for("dml_edit", id=id))
    
    codigo = request.form.get("codigo_repuesto", "").strip().upper()
    cantidad_utilizada = int(request.form.get("cantidad_utilizada", 1))
    
    # Validar campos obligatorios
    if not codigo or not cantidad_utilizada:
        flash("Código y cantidad son obligatorios.", "error")
        return redirect(url_for("dml_edit", id=id))
    
    # Buscar repuesto en matriz
    repuesto = db.execute(
        "SELECT * FROM matriz_repuestos WHERE codigo_repuesto = ?",
        (codigo,)
    ).fetchone()
    
    if not repuesto:
        flash(f"Repuesto '{codigo}' no encontrado en la matriz de repuestos.", "error")
        return redirect(url_for("dml_edit", id=id))
    
    # Verificar stock AUTOMÁTICAMENTE en ubicación DML
    stock = db.execute(
        "SELECT cantidad FROM stock_ubicaciones WHERE codigo_repuesto = ? AND ubicacion = 'DML'",
        (codigo,)
    ).fetchone()
    
    # Determinar estado automáticamente según stock
    if stock and stock['cantidad'] >= cantidad_utilizada:
        en_stock = 1
        en_falta = 0
        estado_repuesto = "EN STOCK"
        # Descontar del stock en DML usando ajustar_stock_ubicacion
        ajustar_stock_ubicacion(codigo, "DML", -cantidad_utilizada)
    else:
        en_stock = 0
        en_falta = 1
        estado_repuesto = "EN FALTA"
    
    # Insertar repuesto
    db.execute("""
        INSERT INTO dml_repuestos 
        (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (id, codigo, repuesto['item'], cantidad_utilizada, cantidad_utilizada, estado_repuesto, en_stock, en_falta))
    db.commit()
    
    # Actualizar estadísticas de uso
    actualizar_estadistica_repuesto(codigo, cantidad_utilizada)
    
    # Verificar alerta de stock después de descontar
    if en_stock:
        verificar_alerta_stock(codigo)
    
    log_action(user['id'], "ADD_PART", "dml_repuestos", id, None, 
              f"{codigo} x{cantidad_utilizada} ({estado_repuesto})")
    
    if en_stock:
        flash(f"Repuesto '{codigo}' agregado (disponible en stock, descontado automáticamente).", "success")
    else:
        flash(f"Repuesto '{codigo}' agregado (⚠️ NO hay stock disponible - marcado EN FALTA).", "warning")
    
    return redirect(url_for("dml_edit", id=id))

@app.route("/dml/<int:id>/marcar-falta/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def marcar_repuesto_falta(id, repuesto_id):
    db = get_db()
    
    repuesto = db.execute(
        "SELECT * FROM dml_repuestos WHERE id = ? AND ficha_id = ?",
        (repuesto_id, id)
    ).fetchone()
    
    if not repuesto:
        return jsonify({"error": "Repuesto no encontrado"}), 404
    
    db.execute(
        "UPDATE dml_repuestos SET en_falta = 1, en_stock = 0 WHERE id = ?",
        (repuesto_id,)
    )
    db.commit()
    
    return jsonify({"success": True}), 200

@app.route("/dml/<int:id>/marcar-llegada/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS")
def marcar_repuesto_llegada(id, repuesto_id):
    db = get_db()
    user = get_current_user()
    
    repuesto = db.execute(
        "SELECT * FROM dml_repuestos WHERE id = ? AND ficha_id = ?",
        (repuesto_id, id)
    ).fetchone()
    
    if not repuesto:
        return jsonify({"error": "Repuesto no encontrado"}), 404
    
    # Cambiar estado
    db.execute(
        "UPDATE dml_repuestos SET en_falta = 0, en_stock = 1, estado_repuesto = 'EN STOCK' WHERE id = ?",
        (repuesto_id,)
    )
    
    # Descontar del stock en ubicación DML
    ajustar_stock_ubicacion(repuesto['codigo_repuesto'], "DML", -repuesto['cantidad_utilizada'])
    
    # Actualizar estadísticas
    actualizar_estadistica_repuesto(repuesto['codigo_repuesto'], repuesto['cantidad_utilizada'])
    
    db.commit()
    
    # Verificar alerta de stock después de descontar
    verificar_alerta_stock(repuesto['codigo_repuesto'])
    
    log_action(user['id'], "PART_ARRIVED", "dml_repuestos", repuesto_id, None,
              f"{repuesto['codigo_repuesto']}")
    
    return jsonify({"success": True}), 200

@app.route("/dml/<int:ficha_id>/repuestos/mover-a-stock/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def mover_repuesto_a_stock(ficha_id, repuesto_id):
    """
    Mueve un repuesto de EN FALTA a EN STOCK cuando llega nueva disponibilidad.
    Descuenta del inventario y actualiza el estado.
    """
    user = get_current_user()
    db = get_db()
    
    # Obtener el repuesto
    repuesto = db.execute("""
        SELECT dr.*, m.item as descripcion
        FROM dml_repuestos dr
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = dr.codigo_repuesto
        WHERE dr.id = ? AND dr.ficha_id = ?
    """, (repuesto_id, ficha_id)).fetchone()
    
    if not repuesto:
        flash("Repuesto no encontrado.", "error")
        return redirect(url_for("dml_edit", id=ficha_id))
    
    # Verificar stock actual
    stock = db.execute("""
        SELECT cantidad FROM stock_ubicaciones 
        WHERE codigo_repuesto = ? AND ubicacion = 'DML'
    """, (repuesto['codigo_repuesto'],)).fetchone()
    
    if not stock or stock['cantidad'] < repuesto['cantidad_utilizada']:
        flash(f"⚠️ No hay stock suficiente de {repuesto['codigo_repuesto']}. Disponible: {stock['cantidad'] if stock else 0}, Necesario: {repuesto['cantidad_utilizada']}", "error")
        return redirect(url_for("dml_edit", id=ficha_id))
    
    # Actualizar estado a EN STOCK
    db.execute("""
        UPDATE dml_repuestos 
        SET en_stock = 1, en_falta = 0, estado_repuesto = 'COLOCADO'
        WHERE id = ?
    """, (repuesto_id,))
    
    # Descontar del stock
    db.execute("""
        UPDATE stock_ubicaciones 
        SET cantidad = cantidad - ?, updated_at = CURRENT_TIMESTAMP
        WHERE codigo_repuesto = ? AND ubicacion = 'DML'
    """, (repuesto['cantidad_utilizada'], repuesto['codigo_repuesto']))
    
    # Actualizar matriz_repuestos
    db.execute("""
        UPDATE matriz_repuestos 
        SET cantidad_actual = cantidad_actual - ?
        WHERE codigo_repuesto = ?
    """, (repuesto['cantidad_utilizada'], repuesto['codigo_repuesto']))
    
    db.commit()
    
    log_action(user['id'], "MOVER_REPUESTO_A_STOCK", "dml_repuestos", repuesto_id, 
              f"EN FALTA", f"EN STOCK - {repuesto['codigo_repuesto']}")
    
    flash(f"✅ Repuesto {repuesto['codigo_repuesto']} movido a EN STOCK y descontado del inventario.", "success")
    return redirect(url_for("dml_edit", id=ficha_id))

@app.route("/dml/<int:ficha_id>/repuestos/eliminar/<int:repuesto_id>", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def eliminar_repuesto(ficha_id, repuesto_id):
    user = get_current_user()
    db = get_db()
    
    repuesto = db.execute("SELECT * FROM dml_repuestos WHERE id = ? AND ficha_id = ?", (repuesto_id, ficha_id)).fetchone()
    if not repuesto:
        flash("Repuesto no encontrado.", "error")
        return redirect(url_for("dml_view", id=ficha_id))
    
    # Si el repuesto estaba en stock, devolverlo a ubicación DML
    if repuesto['en_stock']:
        ajustar_stock_ubicacion(repuesto['codigo_repuesto'], "DML", repuesto['cantidad_utilizada'])
        
        # Restar de estadísticas (reversar el uso)
        db.execute("""
            UPDATE estadisticas_repuestos 
            SET total_usos = total_usos - ?, ultima_actualizacion = CURRENT_TIMESTAMP
            WHERE codigo_repuesto = ?
        """, (repuesto['cantidad_utilizada'], repuesto['codigo_repuesto']))
    
    # Eliminar repuesto
    db.execute("DELETE FROM dml_repuestos WHERE id = ?", (repuesto_id,))
    db.commit()
    
    log_action(user['id'], "DELETE", "dml_repuestos", repuesto_id, None,
              f"Repuesto {repuesto['codigo_repuesto']} eliminado de ficha {ficha_id}")
    
    flash("Repuesto eliminado correctamente.", "success")
    return redirect(url_for("dml_view", id=ficha_id))

# ======================== TICKETS ========================

@app.route("/dml/<int:id>/crear-ticket", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def crear_ticket_endpoint(id):
    """Crea un ticket de seguimiento para una ficha DML."""
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    # Verificar si ya existe ticket
    if ficha['numero_ticket']:
        flash(f"Ya existe ticket creado: {ficha['numero_ticket']}", "info")
        return redirect(url_for("dml_view", id=id))
    
    try:
        # Obtener número de serie desde RAYPAC
        raypac = db.execute(
            "SELECT numero_serie, mail_comercial FROM raypac_entries WHERE id = ?",
            (ficha['raypac_id'],)
        ).fetchone()
        
        if not raypac:
            flash("No se encontró información de RAYPAC.", "error")
            return redirect(url_for("dml_view", id=id))
        
        # Crear ticket
        numero_ticket = crear_ticket(id, raypac['numero_serie'])
        
        # Enviar ticket por email
        if raypac['mail_comercial']:
            html_body = f"""
            <html>
            <head><style>
                body {{ font-family: Arial, sans-serif; }}
                .ticket-box {{ border: 2px solid #2c3e50; padding: 20px; border-radius: 5px; }}
                .ticket-num {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
                .info-row {{ margin: 10px 0; }}
                .label {{ font-weight: bold; color: #555; }}
            </style></head>
            <body>
            <h2>🎫 TICKET DE SEGUIMIENTO GENERADO</h2>
            <div class="ticket-box">
                <div class="ticket-num">{numero_ticket}</div>
                <div class="info-row"><span class="label">Número de Ficha:</span> {ficha['numero_ficha']}</div>
                <div class="info-row"><span class="label">Número de Serie:</span> {raypac['numero_serie']}</div>
                <div class="info-row"><span class="label">Estado:</span> {ficha['estado_reparacion']}</div>
                <div class="info-row"><span class="label">Fecha de Ingreso:</span> {ficha['fecha_ingreso']}</div>
            </div>
            <p>Puede usar este número de ticket para hacer seguimiento de su equipo.</p>
            <p style="color: #999; font-size: 12px;">DML Electricidad Industrial SRL</p>
            </body>
            </html>
            """
            send_mail(raypac['mail_comercial'], 
                     f"🎫 Ticket de Seguimiento: {numero_ticket}",
                     html_body)
        
        log_action(user['id'], "CREATE_TICKET", "tickets", id, None, numero_ticket)
        flash(f"✅ Ticket creado exitosamente: {numero_ticket}", "success")
        
    except Exception as e:
        flash(f"Error al crear ticket: {str(e)}", "error")
    
    return redirect(url_for("dml_view", id=id))

@app.route("/dml/<int:id>/close", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def dml_close(id):
    """Cierra/finaliza una ficha DML y notifica al comercial."""
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    if ficha['is_closed']:
        flash("Esta ficha ya está cerrada.", "info")
        return redirect(url_for("dml_view", id=id))
    
    # VALIDACIONES OBLIGATORIAS antes de cerrar
    errores = []
    
    # 1. Validar remito de salida
    if not ficha['numero_remito_salida']:
        errores.append("Número de remito de salida")
    
    # 2. Validar diagnóstico de reparación
    if not ficha['diagnostico_reparacion'] or len(ficha['diagnostico_reparacion'].strip()) < 10:
        errores.append("Diagnóstico de reparación (mínimo 10 caracteres)")
    
    # 3. Validar técnico responsable
    if not ficha['tecnico_resp']:
        errores.append("Técnico responsable")
    
    # 4. Validar que tenga al menos un repuesto registrado o partes inspeccionadas
    repuestos_count = db.execute("SELECT COUNT(*) as cnt FROM dml_repuestos WHERE ficha_id = ?", (id,)).fetchone()['cnt']
    partes_inspeccionadas = db.execute(
        "SELECT COUNT(*) as cnt FROM dml_partes WHERE ficha_id = ? AND estado != 'POR INSPECCIONAR'", 
        (id,)
    ).fetchone()['cnt']
    
    if repuestos_count == 0 and partes_inspeccionadas == 0:
        errores.append("Debe inspeccionar al menos una parte o agregar repuestos utilizados")
    
    if errores:
        flash(f"⚠️ No se puede cerrar la ficha. Campos requeridos faltantes:", "error")
        for error in errores:
            flash(f"• {error}", "error")
        return redirect(url_for("dml_edit", id=id))
    
    try:
        # Cerrar la ficha y marcar como ENTREGADA
        fecha_egreso = datetime.now().strftime("%Y-%m-%d")
        db.execute("""
            UPDATE dml_fichas 
            SET is_closed = 1, fecha_egreso = ?, estado_reparacion = 'ENTREGADA'
            WHERE id = ?
        """, (fecha_egreso, id))
        
        # Cerrar el ticket asociado (ya cumplió su función de seguimiento)
        if ficha['numero_ticket']:
            db.execute("""
                UPDATE tickets 
                SET estado = 'CERRADO', fecha_cierre = ?
                WHERE numero_ticket = ?
            """, (fecha_egreso, ficha['numero_ticket']))
        
        db.commit()
        
        # Obtener info para email
        raypac = db.execute(
            "SELECT numero_serie, cliente, comercial, mail_comercial FROM raypac_entries WHERE id = ?",
            (ficha['raypac_id'],)
        ).fetchone()
        
        # Enviar email "Máquina Lista" al comercial
        if raypac and raypac['mail_comercial']:
            html_body = f"""
            <html>
            <head><style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                .email-container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; padding: 20px; border-radius: 5px; text-align: center; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .content {{ color: #333; line-height: 1.6; }}
                .info-box {{ background-color: #ecf0f1; padding: 15px; border-left: 4px solid #27ae60; margin: 15px 0; }}
                .label {{ font-weight: bold; color: #2c3e50; }}
                .footer {{ color: #7f8c8d; font-size: 12px; text-align: center; margin-top: 20px; border-top: 1px solid #ecf0f1; padding-top: 10px; }}
                .success-badge {{ background-color: #27ae60; color: white; padding: 10px 15px; border-radius: 5px; display: inline-block; }}
            </style></head>
            <body>
            <div class="email-container">
                <div class="header">
                    <h1>✅ MÁQUINA LISTA PARA RETIRAR</h1>
                </div>
                <div class="content">
                    <p>Estimado {raypac['comercial']},</p>
                    <p>Le comunicamos que la reparación de su equipo ha sido <span class="success-badge">FINALIZADA</span> y está lista para retirar.</p>
                    <div class="info-box">
                        <p><span class="label">Número de Ficha:</span> {ficha['numero_ficha']:07d}</p>
                        <p><span class="label">Número de Serie:</span> {raypac['numero_serie']}</p>
                        <p><span class="label">Cliente:</span> {raypac['cliente']}</p>
                        <p><span class="label">Fecha de Finalización:</span> {fecha_egreso}</p>
                        <p><span class="label">Ticket de Seguimiento:</span> {ficha['numero_ticket'] or 'N/A'}</p>
                    </div>
                    <p>Por favor, contacte con nuestro departamento técnico para coordinar el retiro del equipo.</p>
                    <p>Gracias por confiar en <strong>DML Electricidad Industrial SRL</strong>.</p>
                </div>
                <div class="footer">
                    <p>Este es un mensaje automático. No responda a este correo.</p>
                    <p>DML Electricidad Industrial SRL - Servicio Técnico</p>
                </div>
            </div>
            </body>
            </html>
            """
            mail_sent = send_mail(raypac['mail_comercial'], 
                                 f"✅ Máquina Lista: Ficha #{ficha['numero_ficha']:07d}",
                                 html_body)
            mail_status = "enviada" if mail_sent else "fallida (revisar logs)"
        else:
            mail_status = "sin email configurado"
        
        log_action(user['id'], "CLOSE", "dml_fichas", id, None, 
                  f"Ficha finalizada - Notificación {mail_status} - Comercial: {raypac['comercial'] if raypac else 'N/A'}")
        
        flash(f"✅ Ficha #{ficha['numero_ficha']} cerrada y marcada como ENTREGADA. Notificación {mail_status}.", "success")
        return redirect(url_for("dml_view", id=id))
    except Exception as e:
        flash(f"Error al cerrar ficha: {str(e)}", "error")
        return redirect(url_for("dml_view", id=id))

@app.route("/dml/<int:id>/acuse", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST", "RAYPAC")
def dml_registrar_acuse(id):
    """Registra el acuse de recibo de una máquina entregada."""
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_entregadas"))
    
    if ficha['estado_reparacion'] != 'ENTREGADA':
        flash("Solo se puede registrar acuse de fichas marcadas como ENTREGADA.", "error")
        return redirect(url_for("dml_view", id=id))
    
    try:
        fecha_entrega = request.form.get("fecha_entrega_cliente")
        recibido_por = request.form.get("recibido_por", "").strip()
        observaciones = request.form.get("observaciones_entrega", "").strip()
        
        if not fecha_entrega or not recibido_por:
            flash("La fecha de entrega y el nombre de quien recibe son obligatorios.", "error")
            return redirect(url_for("dml_entregadas"))
        
        # Actualizar acuse de recibo
        db.execute("""
            UPDATE dml_fichas 
            SET fecha_entrega_cliente = ?, recibido_por = ?, 
                observaciones = CASE 
                    WHEN observaciones IS NOT NULL AND observaciones != '' 
                    THEN observaciones || ' | ENTREGA: ' || ?
                    ELSE 'ENTREGA: ' || ?
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (fecha_entrega, recibido_por, observaciones, observaciones, id))
        
        db.commit()
        
        log_action(user['id'], "UPDATE", "dml_fichas", id, None, 
                  f"Acuse de recibo registrado - Recibido por: {recibido_por}")
        
        flash(f"✅ Acuse de recibo registrado correctamente para Ficha #{ficha['numero_ficha']}.", "success")
        
    except Exception as e:
        flash(f"Error al cerrar ficha: {str(e)}", "error")
    
    return redirect(url_for("dml_view", id=id))

@app.route("/tickets")
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "DML_ST", "RAYPAC")
def tickets_list():
    """Listado de tickets activos (no cerrados) con búsqueda y filtro."""
    db = get_db()
    
    buscar = request.args.get("buscar", "")
    estado = request.args.get("estado", "")
    mostrar_cerrados = request.args.get("cerrados", "0") == "1"  # Por defecto no mostrar cerrados
    
    # LEFT JOIN porque tickets pueden existir sin ficha aún
    query = """
        SELECT t.*, f.numero_ficha, f.estado_reparacion,
               r.cliente, r.modelo_maquina, r.comercial
        FROM tickets t 
        LEFT JOIN dml_fichas f ON t.ficha_id = f.id
        LEFT JOIN raypac_entries r ON t.raypac_id = r.id
        WHERE 1=1
    """
    params = []
    
    # Por defecto, solo mostrar tickets activos (no cerrados)
    if not mostrar_cerrados:
        query += " AND (t.estado IS NULL OR t.estado != 'CERRADO')"
    
    if buscar:
        query += " AND (t.numero_ticket LIKE ? OR t.numero_serie LIKE ?)"
        params.extend([f"%{buscar}%", f"%{buscar}%"])
    
    if estado:
        query += " AND t.estado = ?"
        params.append(estado)
    
    query += " ORDER BY t.fecha_creacion DESC"
    
    tickets = db.execute(query, params).fetchall()
    
    return render_template("tickets_list.html", tickets=tickets, buscar=buscar, estado=estado, mostrar_cerrados=mostrar_cerrados)

@app.route("/ticket/<numero_ticket>")
def ticket_view(numero_ticket):
    """Vista pública del seguimiento de un ticket (sin login requerido)."""
    db = get_db()
    
    # LEFT JOIN porque el ticket puede existir sin ficha aún (nuevo flujo)
    ticket = db.execute("""
        SELECT t.*, 
               f.numero_ficha, f.estado_reparacion, f.diagnostico_inicial, f.diagnostico_reparacion,
               r.cliente, r.numero_serie, r.modelo_maquina, r.comercial
        FROM tickets t
        LEFT JOIN dml_fichas f ON t.ficha_id = f.id
        LEFT JOIN raypac_entries r ON t.raypac_id = r.id
        WHERE t.numero_ticket = ?
    """, (numero_ticket,)).fetchone()
    
    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("index"))
    
    # Obtener historial
    historial = db.execute("""
        SELECT * FROM ticket_historial WHERE ticket_id = ? ORDER BY fecha DESC
    """, (ticket['id'],)).fetchall()
    
    return render_template("ticket_view.html", ticket=ticket, historial=historial)

@app.route("/ticket/<numero_ticket>/print")
def ticket_print(numero_ticket):
    """Imprime el ticket en formato solapa/etiqueta (print-friendly)."""
    from datetime import datetime
    db = get_db()
    
    # LEFT JOIN porque el ticket puede existir sin ficha (nuevo flujo)
    ticket = db.execute("""
        SELECT t.*, f.numero_ficha, f.estado_reparacion, 
               r.numero_serie, r.cliente, r.comercial, r.modelo_maquina
        FROM tickets t
        LEFT JOIN dml_fichas f ON t.ficha_id = f.id
        LEFT JOIN raypac_entries r ON t.raypac_id = r.id
        WHERE t.numero_ticket = ?
    """, (numero_ticket,)).fetchone()
    
    if not ticket:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("index"))
    
    return render_template("ticket_print.html", ticket=ticket, now=datetime.now())

# ======================== ENVIOS DE REPUESTOS ========================

@app.route("/envios")
@login_required
@role_required("ADMIN", "RAYPAC", "DML_REPUESTOS", "DML_ST")
def envios_list():
    db = get_db()
    envios = db.execute(
        """
        SELECT e.*, 
               (SELECT COUNT(*) FROM envios_repuestos_detalles d WHERE d.envio_id = e.id) AS items_count
        FROM envios_repuestos e
        ORDER BY e.created_at DESC
        """
    ).fetchall()
    return render_template("envios_list.html", envios=envios)


@app.route("/envios/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def envios_new():
    user = get_current_user()
    db = get_db()

    stock_raypac = db.execute(
        """
        SELECT m.codigo_repuesto, m.item, COALESCE(su.cantidad, 0) AS cantidad
        FROM matriz_repuestos m
        LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = m.codigo_repuesto AND su.ubicacion = 'RAYPAC'
        ORDER BY m.codigo_repuesto
        """
    ).fetchall()

    if request.method == "POST":
        try:
            # Tipo de entrega
            tipo_entrega = request.form.get("tipo_entrega", "REPUESTOS")
            
            # OBLIGATORIO: Número de remito manual
            numero_remito_input = (request.form.get("numero_remito") or "").strip()
            
            if not numero_remito_input:
                flash("⚠️ El número de remito es OBLIGATORIO para enviar repuestos.", "error")
                return render_template("envios_form.html", stock=stock_raypac)
            
            # Auto-completar formato si solo ingresa 4 dígitos (últimos)
            import re
            if re.match(r'^\d{1,4}$', numero_remito_input):
                # Usuario ingresó solo números (1-4 dígitos), auto-completar
                ultimo = numero_remito_input.zfill(4)  # Rellenar con ceros a la izquierda
                numero_remito = f"00001-{ultimo}"  # Formato: 00001-XXXX
                flash(f"📋 Remito auto-completado: {numero_remito}", "info")
            elif re.match(r'^\d{4,5}-\d{4,7}$', numero_remito_input):
                numero_remito = numero_remito_input
            else:
                flash("⚠️ Formato de remito inválido. Ingresa solo los últimos 4 dígitos (ej: 4222) o el formato completo ####-#### (ej: 00001-04222).", "error")
                return render_template("envios_form.html", stock=stock_raypac)
            
            # Verificar que no exista ya
            existe = db.execute("SELECT id FROM envios_repuestos WHERE numero_remito = ?", (numero_remito,)).fetchone()
            if existe:
                flash(f"⚠️ El número de remito {numero_remito} ya existe en el sistema.", "error")
                return render_template("envios_form.html", stock=stock_raypac)
            
            seleccionados = []
            
            # Procesar repuestos de la tabla principal
            for row in stock_raypac:
                qty_raw = (request.form.get(f"qty_{row['codigo_repuesto']}") or "0").strip()
                try:
                    qty = int(qty_raw or 0)
                except ValueError:
                    qty = 0
                if qty > 0:
                    seleccionados.append((row['codigo_repuesto'], row['item'], qty))
            
            # Procesar repuestos adicionales (no listados)
            for key in request.form.keys():
                if key.startswith('codigo_adicional_'):
                    idx = key.replace('codigo_adicional_', '')
                    codigo = request.form.get(f'codigo_adicional_{idx}', '').strip().upper()
                    descripcion = request.form.get(f'descripcion_adicional_{idx}', '').strip()
                    cantidad = request.form.get(f'cantidad_adicional_{idx}', '0').strip()
                    
                    try:
                        qty = int(cantidad or 0)
                    except ValueError:
                        qty = 0
                    
                    if codigo and qty > 0:
                        # Si no tiene descripción, buscarla en la matriz
                        if not descripcion:
                            rep = db.execute("SELECT item FROM matriz_repuestos WHERE codigo_repuesto = ?", (codigo,)).fetchone()
                            descripcion = rep['item'] if rep else f"Repuesto {codigo}"
                        
                        seleccionados.append((codigo, descripcion, qty))
            
            if not seleccionados:
                flash("Selecciona al menos un repuesto con cantidad mayor a 0.", "error")
                return render_template("envios_form.html", stock=stock_raypac)

            fecha_envio = datetime.now().strftime("%Y-%m-%d")

            db.execute(
                """INSERT INTO envios_repuestos 
                   (numero_remito, fecha_envio, tipo_entrega, estado_envio, is_frozen) 
                   VALUES (?, ?, ?, 'ENVIADO', 1)""",
                (numero_remito, fecha_envio, tipo_entrega)
            )
            envio_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']

            # Guardar detalles del envío
            # IMPORTANTE: NO descontamos stock de RAYPAC (ellos no controlan stock desde este software)
            for codigo, item, qty in seleccionados:
                db.execute(
                    "INSERT INTO envios_repuestos_detalles (envio_id, codigo_repuesto, cantidad) VALUES (?, ?, ?)",
                    (envio_id, codigo, qty)
                )

            db.commit()

            log_action(user['id'], "CREATE", "envios_repuestos", envio_id, None,
                      f"Remito {numero_remito} con {len(seleccionados)} items")

            flash(f"Envío generado: {numero_remito}", "success")
            return redirect(url_for("envios_view", id=envio_id))
        except Exception as e:
            db.rollback()
            flash(f"Error al generar envío: {e}", "error")
            return render_template("envios_form.html", stock=stock_raypac)

    return render_template("envios_form.html", stock=stock_raypac)


@app.route("/envios/<int:id>")
@login_required
@role_required("ADMIN", "RAYPAC", "DML_REPUESTOS", "DML_ST")
def envios_view(id):
    db = get_db()
    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = ?", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios_list"))
    detalles = db.execute(
        """
        SELECT d.*, m.item 
        FROM envios_repuestos_detalles d
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto
        WHERE d.envio_id = ?
        ORDER BY d.codigo_repuesto
        """,
        (id,)
    ).fetchall()
    return render_template("envios_view.html", envio=envio, detalles=detalles)


@app.route("/envios/<int:id>/confirmar", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "DML_ST")
def envios_confirmar(id):
    user = get_current_user()
    db = get_db()
    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = ?", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios_list"))
    if envio.get('estado_envio') == 'RECIBIDO':
        flash("El envío ya fue confirmado.", "warning")
        return redirect(url_for("envios_view", id=id))

    detalles = db.execute(
        "SELECT d.*, m.item FROM envios_repuestos_detalles d LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto WHERE d.envio_id = ?",
        (id,)
    ).fetchall()
    if not detalles:
        flash("No hay detalles de repuestos para este envío.", "error")
        return redirect(url_for("envios_view", id=id))

    try:
        fecha_recepcion = datetime.now().strftime("%Y-%m-%d")
        
        # Actualizar stock DML con los repuestos recibidos
        for det in detalles:
            codigo = det['codigo_repuesto']
            qty = det['cantidad']
            
            # Agregar a stock de DML
            ajustar_stock_ubicacion(codigo, "DML", qty)
            actualizar_estado_alerta_stock(codigo)
        
        # Marcar envío como recibido
        db.execute(
            """UPDATE envios_repuestos 
               SET estado_envio = 'RECIBIDO', 
                   fecha_recepcion_dml = ?, 
                   usuario_recepcion_id = ?,
                   updated_at = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (fecha_recepcion, user['id'], id)
        )
        db.commit()

        log_action(user['id'], "CONFIRM", "envios_repuestos", id, None, "Recepción en DML")

        # Aviso a RAYPAC de recepción
        try:
            lineas = """
            <ul>
            %s
            </ul>
            """ % "\n".join([
                f"<li>{det['codigo_repuesto']} - {det['item'] or ''} x {det['cantidad']}</li>" for det in detalles
            ])
            html_body = f"""
            <h3>Confirmación de recepción de repuestos</h3>
            <p>Remito: <strong>{envio['numero_remito']}</strong></p>
            <p>Fecha recepción: {datetime.now().strftime('%Y-%m-%d')}</p>
            <p>Detalle:</p>
            {lineas}
            <p>Los repuestos fueron cargados en stock DML.</p>
            """
            send_mail("raypac@dml.local", f"Recepción remito {envio['numero_remito']} en DML", html_body)
        except Exception as e:
            print(f"Error enviando mail de recepción a Raypac: {e}")

        flash("Envío confirmado y stock actualizado.", "success")
        return redirect(url_for("envios_view", id=id))
    except Exception as e:
        db.rollback()
        flash(f"Error al confirmar envío: {e}", "error")
        return redirect(url_for("envios_view", id=id))

@app.route("/envios/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def envios_edit(id):
    """Editar envío congelado (solo corrección de errores)"""
    user = get_current_user()
    db = get_db()
    
    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = ?", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios_list"))
    
    if request.method == "POST":
        try:
            nuevo_remito = request.form.get("numero_remito", "").strip()
            
            if not nuevo_remito:
                flash("El número de remito es obligatorio.", "error")
                return redirect(url_for("envios_edit", id=id))
            
            # Verificar que no exista otro envío con ese remito
            existe = db.execute(
                "SELECT id FROM envios_repuestos WHERE numero_remito = ? AND id != ?", 
                (nuevo_remito, id)
            ).fetchone()
            
            if existe:
                flash(f"Ya existe otro envío con el remito {nuevo_remito}.", "error")
                return redirect(url_for("envios_edit", id=id))
            
            db.execute(
                "UPDATE envios_repuestos SET numero_remito = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (nuevo_remito, id)
            )
            db.commit()
            
            log_action(user['id'], "UPDATE", "envios_repuestos", id, 
                      f"Remito: {envio['numero_remito']} → {nuevo_remito}", 
                      "Corrección de remito")
            
            flash(f"✅ Remito actualizado a: {nuevo_remito}", "success")
            return redirect(url_for("envios_view", id=id))
            
        except Exception as e:
            db.rollback()
            flash(f"Error al actualizar envío: {e}", "error")
            return redirect(url_for("envios_edit", id=id))
    
    detalles = db.execute(
        """SELECT d.*, m.item 
           FROM envios_repuestos_detalles d
           LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = d.codigo_repuesto
           WHERE d.envio_id = ?
           ORDER BY d.codigo_repuesto""",
        (id,)
    ).fetchall()
    
    return render_template("envios_edit.html", envio=envio, detalles=detalles)

@app.route("/envios/<int:id>/unfreeze", methods=["POST"])
@login_required
@role_required("ADMIN")
def envios_unfreeze(id):
    """Desfreezar envío definitivamente (solo ADMIN con código)"""
    user = get_current_user()
    db = get_db()
    
    envio = db.execute("SELECT * FROM envios_repuestos WHERE id = ?", (id,)).fetchone()
    if not envio:
        flash("Envío no encontrado.", "error")
        return redirect(url_for("envios_list"))
    
    # Verificar código de desfreeze (últimos 4 dígitos del remito)
    codigo = request.form.get("unfreeze_code", "").strip()
    remito_digitos = envio['numero_remito'][-4:]
    
    if codigo != remito_digitos:
        flash("❌ Código incorrecto. Ingresa los últimos 4 dígitos del remito.", "error")
        return redirect(url_for("envios_view", id=id))
    
    try:
        db.execute(
            "UPDATE envios_repuestos SET is_frozen = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (id,)
        )
        db.commit()
        
        log_action(user['id'], "UNFREEZE", "envios_repuestos", id, None, 
                  f"Envío descongelado por ADMIN")
        
        flash("🔓 Envío descongelado correctamente.", "success")
        return redirect(url_for("envios_view", id=id))
        
    except Exception as e:
        db.rollback()
        flash(f"Error al descongelar envío: {e}", "error")
        return redirect(url_for("envios_view", id=id))

# ======================== STOCK ========================

@app.route("/stock")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["DML_REPUESTOS", "RAYPAC"])
def stock_list(readonly=False):
    user = get_current_user()
    db = get_db()
    
    # Determinar ubicación según rol del usuario
    if user['role'] == 'RAYPAC':
        # RAYPAC solo ve su stock (RAYPAC)
        ubicacion = "RAYPAC"
    elif user['role'] in ['DML_REPUESTOS', 'DML_ST']:
        # DML_REPUESTOS y DML_ST ven stock de DML
        ubicacion = "DML"
    else:
        # ADMIN puede ver ambos (parámetro en URL)
        ubicacion = request.args.get("ubicacion", "DML")
    
    buscar = request.args.get("buscar", "")
    
    # Query con filtro por ubicación
    query = """SELECT DISTINCT m.*, COALESCE(su.cantidad, 0) as cantidad
              FROM matriz_repuestos m
              LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = m.codigo_repuesto AND su.ubicacion = ?
              WHERE 1=1"""
    params = [ubicacion]
    
    if buscar:
        query += " AND (m.codigo_repuesto LIKE ? OR m.item LIKE ?)"
        params.extend([f"%{buscar}%", f"%{buscar}%"])
    
    stocks = db.execute(query + " ORDER BY m.codigo_repuesto", params).fetchall()
    
    # Agregar información de alerta
    stocks_con_alerta = []
    for stock in stocks:
        alerta = check_stock_alert(stock['codigo_repuesto'], ubicacion)
        stocks_con_alerta.append({
            **dict(stock),
            'alerta': alerta,
            'ubicacion': ubicacion
        })
    
    # Para ADMIN, mostrar opción de cambiar ubicación
    ubicaciones_disponibles = []
    if user['role'] == 'ADMIN':
        ubicaciones_disponibles = ["RAYPAC", "DML"]
    
    return render_template("stock_list.html", 
                         user=user, 
                         rows=stocks_con_alerta, 
                         ubicacion=ubicacion,
                         ubicaciones_disponibles=ubicaciones_disponibles,
                         readonly=readonly)

@app.route("/stock/new", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def stock_new():
    user = get_current_user()
    db = get_db()
    
    # Determinar ubicación según rol
    if user['role'] == 'RAYPAC':
        ubicacion = "RAYPAC"
    elif user['role'] == 'DML_REPUESTOS':
        ubicacion = "DML"
    else:
        ubicacion = request.args.get("ubicacion", "DML")  # ADMIN puede elegir
    
    if request.method == "POST":
        try:
            # Solo ADMIN necesita contraseña
            if user['role'] == 'ADMIN':
                admin_password = (request.form.get("admin_password") or "").strip()
                if admin_password != "ADMIN2024":
                    flash("Contraseña de administración incorrecta.", "error")
                    return render_template("stock_new.html", ubicacion=ubicacion, user=user)
            
            codigo = request.form.get("codigo_repuesto")
            item = request.form.get("item")
            cantidad = int(request.form.get("cantidad", 0))
            
            if not codigo or not item:
                flash("Código e Item son obligatorios.", "error")
                return render_template("stock_new.html", ubicacion=ubicacion)
            
            # Verificar que el repuesto existe en matriz o crearlo
            existe_matriz = db.execute(
                "SELECT id FROM matriz_repuestos WHERE codigo_repuesto = ?",
                (codigo,)
            ).fetchone()
            
            if not existe_matriz:
                # Crear en matriz si no existe
                numero = db.execute("SELECT MAX(numero) as max FROM matriz_repuestos").fetchone()['max'] or 0
                db.execute("""
                    INSERT INTO matriz_repuestos 
                    (numero, codigo_repuesto, item)
                    VALUES (?, ?, ?)
                """, (numero + 1, codigo, item))
            
            # Verificar que no existe en esa ubicación
            existe_stock = db.execute(
                "SELECT id FROM stock_ubicaciones WHERE codigo_repuesto = ? AND ubicacion = ?",
                (codigo, ubicacion)
            ).fetchone()
            
            if existe_stock:
                flash(f"Este repuesto ya existe en {ubicacion}.", "error")
                return render_template("stock_new.html", ubicacion=ubicacion, user=user)
            
            # Insertar en stock_ubicaciones
            db.execute("""
                INSERT INTO stock_ubicaciones 
                (codigo_repuesto, ubicacion, cantidad)
                VALUES (?, ?, ?)
            """, (codigo, ubicacion, cantidad))
            db.commit()
            
            log_action(user['id'], "CREATE", "stock_ubicaciones", None, None, 
                      f"{codigo} - {item} en {ubicacion}")
            
            flash(f"Repuesto {codigo} agregado al stock de {ubicacion}.", "success")
            return redirect(url_for("stock_list", ubicacion=ubicacion))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
            return render_template("stock_new.html", ubicacion=ubicacion, user=user)
    
    return render_template("stock_new.html", ubicacion=ubicacion, user=user)

@app.route("/stock/<codigo>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "RAYPAC")
def stock_edit(codigo):
    user = get_current_user()
    db = get_db()
    
    # Determinar ubicación según rol o parámetro
    if user['role'] == 'RAYPAC':
        ubicacion = "RAYPAC"
    elif user['role'] == 'DML_REPUESTOS':
        ubicacion = "DML"
    else:
        ubicacion = request.args.get("ubicacion", "DML")
    
    stock = db.execute(
        "SELECT * FROM stock_ubicaciones WHERE codigo_repuesto = ? AND ubicacion = ?",
        (codigo, ubicacion)
    ).fetchone()
    
    if not stock:
        flash("Repuesto no encontrado en " + ubicacion + ".", "error")
        return redirect(url_for("stock_list"))
    
    if request.method == "POST":
        try:
            # Solo ADMIN necesita contraseña
            if user['role'] == 'ADMIN':
                admin_password = (request.form.get("admin_password") or "").strip()
                if admin_password != "ADMIN2024":
                    flash("Contraseña de administración incorrecta.", "error")
                    return render_template("stock_edit.html", stock=stock, ubicacion=ubicacion, user=user)

            cantidad = int(request.form.get("cantidad", 0))
            
            db.execute("""
                UPDATE stock_ubicaciones 
                SET cantidad = ?, updated_at = CURRENT_TIMESTAMP
                WHERE codigo_repuesto = ? AND ubicacion = ?
            """, (cantidad, codigo, ubicacion))
            db.commit()
            
            log_action(user['id'], "UPDATE", "stock_ubicaciones", None, 
                      f"Anterior: {stock['cantidad']}", f"Nuevo: {cantidad}")
            
            flash("Stock actualizado.", "success")
            return redirect(url_for("stock_list", ubicacion=ubicacion))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    return render_template("stock_edit.html", stock=stock, ubicacion=ubicacion, user=user)

@app.route("/stock/<codigo>/delete", methods=["POST"])
@login_required
@role_required("ADMIN")  # Solo ADMIN puede eliminar
def stock_delete(codigo):
    user = get_current_user()
    db = get_db()
    
    # Obtener ubicación del parámetro
    ubicacion = request.args.get("ubicacion", "DML")
    
    # Solo ADMIN necesita contraseña
    admin_password = (request.form.get("admin_password") or "").strip()
    if admin_password != "ADMIN2024":
        flash("Contraseña de administración incorrecta.", "error")
        return redirect(url_for("stock_list", ubicacion=ubicacion))
    
    db.execute(
        "DELETE FROM stock_ubicaciones WHERE codigo_repuesto = ? AND ubicacion = ?",
        (codigo, ubicacion)
    )
    db.commit()
    
    log_action(user['id'], "DELETE", "stock_ubicaciones", None, codigo, None)
    
    flash(f"Repuesto eliminado del stock de {ubicacion}.", "success")
    return redirect(url_for("stock_list", ubicacion=ubicacion))

# ======================== PDF GENERATION ========================

# Función generate_ficha_pdf completamente reescrita basada en CAMPOS DE INGRESO DML.xlsx

def generate_ficha_pdf(ficha_id):
    """Genera PDF idéntico al Excel CAMPOS DE INGRESO DML."""
    try:
        db = get_db()
        ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (ficha_id,)).fetchone()
        
        if not ficha:
            raise ValueError(f"No se encontró ficha con ID {ficha_id}")
        
        # Obtener datos relacionados
        raypac = None
        if ficha['raypac_id']:
            raypac = db.execute("SELECT * FROM raypac_entries WHERE id = ?", (ficha['raypac_id'],)).fetchone()
        
        partes = db.execute("SELECT * FROM dml_partes WHERE ficha_id = ? ORDER BY id", (ficha_id,)).fetchall()
        repuestos = db.execute("SELECT * FROM dml_repuestos WHERE ficha_id = ? ORDER BY id", (ficha_id,)).fetchall()
        
        # Crear PDF
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, 
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.5*inch, rightMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        # Estilos
        title_style = ParagraphStyle('Title', parent=styles['Normal'], fontSize=14, 
                                     fontName='Helvetica-Bold', alignment=1)
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10)
        label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, 
                                    fontName='Helvetica-Bold')
        small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)
        
        gray_bg = colors.HexColor('#d9d9d9')
        
        # ===== ENCABEZADO =====
        # Cargar logo
        logo_path = os.path.join(app.static_folder, 'raypac_logo.png')
        logo_img = None
        if os.path.exists(logo_path):
            try:
                logo_img = Image(logo_path, width=1.5*inch, height=0.6*inch)
            except:
                pass
        
        header_data = [[
            Paragraph(f"<b>Nº Ficha</b><br/>{ficha['numero_ficha']:07d}", normal_style),
            logo_img if logo_img else "",
            Paragraph("<b><u>INFORME DML SOBRE EL<br/>EQUIPO EN REVISION</u></b>", title_style)
        ]]
        header_table = Table(header_data, colWidths=[1.5*inch, 2*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (2, 0), (2, 0), 1, colors.black),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # Servicio Técnico
        elements.append(Paragraph("<b>Servicio Técnico</b>", title_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== DATOS PRINCIPALES + ESTADO DEL EQUIPO =====
        # Columna izquierda: Info
        info_data = [
            [Paragraph("<b>Fecha de recepción Raypac:</b>", label_style), 
             Paragraph(str(raypac['fecha_recepcion'] if raypac else ''), normal_style)],
            [Paragraph("<b>Comercial responsable:</b>", label_style), 
             Paragraph(str(raypac['comercial'] if raypac else ''), normal_style)],
            [Paragraph("<b>Nombre del Cliente:</b>", label_style), 
             Paragraph(str(raypac['cliente'] if raypac else ''), normal_style)],
            [Paragraph("<b>Equipo Recibido:</b>", label_style), 
             Paragraph(f"{raypac['modelo_maquina'] if raypac else ''}     <b>Serie N°:</b> {raypac['numero_serie'] if raypac else ''}", normal_style)],
            [Paragraph("<b>Fecha de ingreso DML:</b>", label_style), 
             Paragraph(f"{ficha['fecha_ingreso']}     <b>Bat N°:</b> {raypac['numero_bateria'] if raypac else 'NO APLICA'}", normal_style)],
            [Paragraph("<b>Fecha de egreso DML:</b>", label_style), 
             Paragraph(f"{ficha['fecha_egreso'] or ''}     <b>Cargador N°:</b> {raypac['numero_cargador'] if raypac else 'NO APLICA'}", normal_style)],
        ]
        
        # Columna derecha: Estado del Equipo
        estado_data = [[Paragraph("<b>ESTADO DEL EQUIPO</b>", label_style), ""]]
        for parte in partes:
            estado_data.append([
                Paragraph(f"<b>{parte['nombre_parte']}</b>", small_style),
                Paragraph(str(parte['estado'] or 'BUENO'), small_style)
            ])
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        estado_table = Table(estado_data, colWidths=[1.5*inch, 1*inch])
        estado_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), gray_bg),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        
        main_table = Table([[info_table, estado_table]], colWidths=[5*inch, 2.5*inch])
        elements.append(main_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== DIAGNÓSTICO DEL DEPARTAMENTO TÉCNICO =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>DIAGNOSTICO DEL DEPARTAMENTO TECNICO</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        diag_box = Paragraph(ficha['diagnostico_inicial'] or '', normal_style)
        elements.append(diag_box)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== OBSERVACIONES =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>OBSERVACIONES</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        obs_box = Paragraph(ficha['observaciones'] or '', normal_style)
        elements.append(obs_box)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== DIAGNÓSTICO DE REPARACIÓN =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>DIAGNOSTICO DE REPARACIÓN</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        diag_rep_box = Paragraph(ficha['diagnostico_reparacion'] or '', normal_style)
        elements.append(diag_rep_box)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== REPUESTOS COLOCADOS =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>REPUESTOS COLOCADOS</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        
        repuestos_data = [[
            Paragraph("<b>Cantidad</b>", small_style),
            Paragraph("<b>Codigo</b>", small_style),
            Paragraph("<b>DESCRIPCION</b>", small_style),
            Paragraph("<b>EN STOCK</b>", small_style),
            Paragraph("<b>EN FALTA</b>", small_style)
        ]]
        
        for repuesto in repuestos[:8]:  # Máximo 8
            repuestos_data.append([
                Paragraph(str(repuesto['cantidad_utilizada'] or repuesto['cantidad']), small_style),
                Paragraph(str(repuesto['codigo_repuesto']), small_style),
                Paragraph(str(repuesto['descripcion']), small_style),
                Paragraph("✓" if repuesto['en_stock'] else "", small_style),
                Paragraph("✗" if repuesto['en_falta'] else "", small_style)
            ])
        
        # Rellenar hasta 8 filas
        for _ in range(len(repuestos), 8):
            repuestos_data.append([
                Paragraph("0", small_style),
                Paragraph("0", small_style),
                Paragraph("", small_style),
                Paragraph("", small_style),
                Paragraph("", small_style)
            ])
        
        repuestos_table = Table(repuestos_data, colWidths=[0.7*inch, 1*inch, 3.5*inch, 0.8*inch, 0.8*inch])
        repuestos_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), gray_bg),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(repuestos_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== N° DE CICLOS =====
        ciclos_data = [[
            Paragraph("<b>N° DE CICLOS DE LA MÁQUINA CON LAS QUE SALE DE ST</b>", label_style),
            Paragraph(str(ficha['n_ciclos'] or 0), normal_style)
        ]]
        ciclos_table = Table(ciclos_data, colWidths=[4.5*inch, 2.5*inch])
        ciclos_table.setStyle(TableStyle([
            ('BOX', (1, 0), (1, 0), 0.5, colors.black),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ]))
        elements.append(ciclos_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== MARCAR CON UNA CRUZ =====
        elements.append(Paragraph("<para alignment='center' backColor='#d9d9d9'><b>MARCAR CON UNA CRUZ LO QUE CORRESPONDA</b></para>", normal_style))
        elements.append(Spacer(1, 0.05*inch))
        
        info_final = [
            ["TIPO DE MAQUINA QUE INGRESO AL ST", raypac['tipo_maquina'] if raypac else 'A BATERIA'],
            ["El módulo reparación Base es de tres (3hs)", ""],
            ["HORAS ADICIONALES DE TRABAJO", ficha['horas_adic'] or 'NO APLICA'],
            ["MECANIZADO ADICIONAL REALIZADO A LA MAQUINA", ficha['mecanizado_adic'] or 'NO APLICA'],
            ["TIPO DE TRABAJO REALIZADO", "REPARACIÓN"],
            ["TÉCNICO RESPONSABLE DEL ST DE DML", ficha['tecnico_resp'] or '']
        ]
        
        for item in info_final:
            row_data = [[Paragraph(f"<b>{item[0]}</b>", label_style), Paragraph(str(item[1]), normal_style)]]
            row_table = Table(row_data, colWidths=[4.5*inch, 2.5*inch])
            row_table.setStyle(TableStyle([
                ('BOX', (1, 0), (1, 0), 0.5, colors.black),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ]))
            elements.append(row_table)
            elements.append(Spacer(1, 0.05*inch))
        
        # ===== FOOTER =====
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("<para alignment='center'><b>SERVICIO TÉCNICO- DML ELECTRICIDAD INDUSTRIAL SRL</b></para>", normal_style))
        
        # Construir PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        return pdf_buffer
    
    except Exception as e:
        print(f"ERROR en generate_ficha_pdf_new: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


@app.route("/dml/<int:id>/generar-ficha", methods=["POST"])
@login_required
@role_required("ADMIN", "DML_ST")
def generar_ficha(id):
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    # Verificar que esté en "MÁQUINA LISTA PARA RETIRAR"
    if ficha['estado_reparacion'] != 'MÁQUINA LISTA PARA RETIRAR':
        flash("La máquina debe estar en estado 'MÁQUINA LISTA PARA RETIRAR'.", "error")
        return redirect(url_for("dml_view", id=id))
    
    try:
        # Generar PDF para validar que no hay errores
        pdf_buffer = generate_ficha_pdf(id)
        
        # Guardar en BD
        db.execute(
            "UPDATE dml_fichas SET ficha_generada = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (id,)
        )
        db.commit()
        
        # Intentar enviar correo al comercial (no bloquear si falla)
        try:
            raypac = db.execute(
                "SELECT mail_comercial FROM raypac_entries WHERE id = ?",
                (ficha['raypac_id'],)
            ).fetchone()
            
            if raypac and raypac['mail_comercial']:
                html_body = f"""
                <html>
                <body>
                <h2>Máquina Lista para Entregar</h2>
                <p>La máquina <strong>{ficha['numero_ficha']}</strong> se encuentra lista para retirar.</p>
                <p>Datos del ticket: {ficha['numero_ticket']}</p>
                <p>Saludos, DML</p>
                </body>
                </html>
                """
                send_mail(raypac['mail_comercial'], 
                         f"Máquina {ficha['numero_ticket']} - Lista para Retirar",
                         html_body)
                
                db.execute(
                    "UPDATE dml_fichas SET ticket_enviado = 1 WHERE id = ?",
                    (id,)
                )
                db.commit()
        except Exception as e:
            print(f"Error al enviar email: {str(e)}")
        
        log_action(user['id'], "GENERATE_FICHA", "dml_fichas", id, None, 
                  f"Ficha #{ficha['numero_ficha']}")
        
        flash("Ficha generada exitosamente. Descarga el PDF con el botón disponible.", "success")
        return redirect(url_for("dml_view", id=id))
        
    except Exception as e:
        flash(f"Error al generar ficha: {str(e)}", "error")
        return redirect(url_for("dml_view", id=id))

@app.route("/dml/<int:id>/pdf", methods=["GET"])
@login_required
@role_required("ADMIN", "DML_ST", "DML_REPUESTOS")
def descargar_ficha_pdf(id):
    """Genera y descarga el PDF de una ficha de reparación."""
    user = get_current_user()
    db = get_db()
    
    ficha = db.execute("SELECT * FROM dml_fichas WHERE id = ?", (id,)).fetchone()
    if not ficha:
        flash("Ficha no encontrada.", "error")
        return redirect(url_for("dml_list"))
    
    # Generar PDF on-demand
    pdf_buffer = generar_ficha_pdf(id)
    
    if not pdf_buffer:
        flash("No se pudo generar el PDF.", "error")
        return redirect(url_for("dml_view", id=id))
    
    log_action(user['id'], "DOWNLOAD_FICHA_PDF", "dml_fichas", id, None,
              f"Ficha #{ficha['numero_ficha']}")
    
    # Devolver PDF
    return send_file(pdf_buffer, mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"ficha_{ficha['numero_ficha']:07d}.pdf")

# ======================== USUARIOS ========================

@app.route("/admin/usuarios")
@login_required
@role_required("ADMIN")
def usuarios_list():
    db = get_db()
    user = get_current_user()
    usuarios = db.execute("SELECT * FROM users ORDER BY email").fetchall()
    return render_template("usuarios_list.html", usuarios=usuarios, user=user)

@app.route("/admin/reset-database-with-seeds", methods=["POST", "GET"])
def reset_database_temp():
    """Endpoint temporal para resetear BD con seeds (SOLO PRODUCCIÓN)"""
    import sys
    
    output = []
    try:
        # Borrar BD actual
        db_path = app.config["DATABASE"]
        output.append(f"[RESET] Ruta BD: {db_path}")
        print(f"[RESET] Ruta BD: {db_path}", file=sys.stderr, flush=True)
        
        if os.path.exists(db_path):
            os.remove(db_path)
            output.append("[RESET] ✅ Base de datos eliminada")
            print("[RESET] ✅ Base de datos eliminada", file=sys.stderr, flush=True)
        else:
            output.append("[RESET] ⚠️ BD no existía")
            print("[RESET] ⚠️ BD no existía", file=sys.stderr, flush=True)
        
        # Recrear con seeds
        output.append("[RESET] Iniciando recreación...")
        print("[RESET] Iniciando recreación...", file=sys.stderr, flush=True)
        
        # Forzar reset del flag de migraciones
        if hasattr(app, '_migrations_applied'):
            delattr(app, '_migrations_applied')
        
        init_db()
        output.append("[RESET] ✅ Base de datos recreada con seeds")
        print("[RESET] ✅ Base de datos recreada con seeds", file=sys.stderr, flush=True)
        
        # Verificar datos
        db = get_db()
        user_count = db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
        stock_count = db.execute("SELECT COUNT(*) as c FROM stock_ubicaciones").fetchone()['c']
        
        output.append(f"[RESET] Usuarios creados: {user_count}")
        output.append(f"[RESET] Items en stock: {stock_count}")
        print(f"[RESET] Usuarios: {user_count}, Stock: {stock_count}", file=sys.stderr, flush=True)
        
        result = "<br>".join(output)
        result += "<br><br><strong>Login: admin@dml.local / admin</strong>"
        result += "<br><a href='/login'>Ir al login</a>"
        return result, 200
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        trace = traceback.format_exc()
        output.append(f"[RESET] ❌ Error: {error_msg}")
        print(f"[RESET] ❌ Error: {error_msg}", file=sys.stderr, flush=True)
        print(trace, file=sys.stderr, flush=True)
        
        result = "<br>".join(output)
        result += f"<br><br><pre>{trace}</pre>"
        return result, 500

@app.route("/admin/cargar-stock-csv", methods=["POST", "GET"])
def cargar_stock_desde_web():
    """Endpoint para cargar stock desde el CSV en producción"""
    import csv
    import sys
    
    output = []
    try:
        # Ruta al CSV
        csv_path = os.path.join(BASE_DIR, "DOCUMENTOS DML", "Copia de NUEVO STOCK DE REPUESTOS COMPLETO.csv")
        output.append(f"[STOCK] Buscando CSV: {csv_path}")
        print(f"[STOCK] Buscando CSV: {csv_path}", file=sys.stderr, flush=True)
        
        if not os.path.exists(csv_path):
            output.append("[STOCK] ❌ Archivo CSV no encontrado")
            return "<br>".join(output), 404
        
        output.append("[STOCK] ✅ CSV encontrado, iniciando carga...")
        print("[STOCK] ✅ CSV encontrado", file=sys.stderr, flush=True)
        
        db = get_db()
        repuestos_cargados = 0
        repuestos_actualizados = 0
        errores = 0
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            
            # Saltar las primeras 4 filas (encabezados)
            for _ in range(4):
                next(reader, None)
            
            for idx, row in enumerate(reader, start=1):
                if len(row) < 11:
                    continue
                
                try:
                    # Extraer datos
                    codigo = row[2].strip() if len(row) > 2 and row[2] else None
                    item = row[3].strip() if len(row) > 3 and row[3] else None
                    cantidad_str = row[4].strip() if len(row) > 4 and row[4] else "0"
                    codigo_ubicacion = row[9].strip() if len(row) > 9 and row[9] else "SIN UBICACIÓN"
                    
                    if not codigo or not item:
                        continue
                    
                    # Limpiar y convertir cantidad
                    cantidad_str = cantidad_str.replace(',', '')
                    try:
                        cantidad = int(float(cantidad_str))
                    except:
                        errores += 1
                        continue
                    
                    if cantidad <= 0:
                        continue
                    
                    # 1. Insertar o actualizar en matriz_repuestos
                    cursor = db.execute("SELECT id FROM matriz_repuestos WHERE codigo_repuesto = ?", (codigo,))
                    existe_matriz = cursor.fetchone()
                    
                    if not existe_matriz:
                        numero_correlativo = idx
                        db.execute("""
                            INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                            VALUES (?, ?, ?, ?, ?, 'DML')
                        """, (numero_correlativo, codigo, item, cantidad, cantidad))
                        repuestos_cargados += 1
                    else:
                        db.execute("""
                            UPDATE matriz_repuestos 
                            SET item = ?, cantidad_actual = ?
                            WHERE codigo_repuesto = ?
                        """, (item, cantidad, codigo))
                        repuestos_actualizados += 1
                    
                    # 2. Insertar o actualizar en stock_ubicaciones (DML)
                    cursor = db.execute("""
                        SELECT id FROM stock_ubicaciones 
                        WHERE codigo_repuesto = ? AND ubicacion = 'DML'
                    """, (codigo,))
                    
                    existe_stock = cursor.fetchone()
                    
                    if not existe_stock:
                        db.execute("""
                            INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                            VALUES (?, 'DML', ?, ?)
                        """, (codigo, cantidad, codigo_ubicacion))
                    else:
                        db.execute("""
                            UPDATE stock_ubicaciones 
                            SET cantidad = ?, codigo_ubicacion_fisica = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE codigo_repuesto = ? AND ubicacion = 'DML'
                        """, (cantidad, codigo_ubicacion, codigo))
                    
                except Exception as e:
                    errores += 1
                    continue
        
        db.commit()
        
        output.append(f"[STOCK] ✅ Carga completada!")
        output.append(f"[STOCK] 📦 Repuestos nuevos: {repuestos_cargados}")
        output.append(f"[STOCK] 🔄 Repuestos actualizados: {repuestos_actualizados}")
        output.append(f"[STOCK] ⚠️ Errores: {errores}")
        
        print(f"[STOCK] Nuevos: {repuestos_cargados}, Actualizados: {repuestos_actualizados}, Errores: {errores}", 
              file=sys.stderr, flush=True)
        
        result = "<br>".join(output)
        result += "<br><br><a href='/stock'>Ver Stock Cargado</a>"
        return result, 200
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        trace = traceback.format_exc()
        output.append(f"[STOCK] ❌ Error: {error_msg}")
        print(f"[STOCK] ❌ Error: {error_msg}", file=sys.stderr, flush=True)
        print(trace, file=sys.stderr, flush=True)
        
        result = "<br>".join(output)
        result += f"<br><br><pre>{trace}</pre>"
        return result, 500

@app.route("/admin/usuarios/nueva", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def usuario_new():
    user = get_current_user()
    db = get_db()
    
    if request.method == "POST":
        try:
            email = request.form.get("email")
            password = request.form.get("password")
            nombre = request.form.get("nombre")
            role = request.form.get("role")
            
            roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
            
            if not all([email, password, role]):
                flash("Completa los campos obligatorios.", "error")
                return render_template("usuario_form.html", roles=roles)
            
            existe = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existe:
                flash("Este email ya existe.", "error")
                return render_template("usuario_form.html", roles=roles)
            
            hash_pwd = generate_password_hash(password)
            db.execute("""
                INSERT INTO users (email, password_hash, nombre, role, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (email, hash_pwd, nombre, role))
            db.commit()
            
            log_action(user['id'], "CREATE", "users", None, None, f"{email} - {role}")
            
            flash(f"Usuario {email} creado.", "success")
            return redirect(url_for("usuarios_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_form.html", roles=roles)

@app.route("/admin/usuarios/<int:id>/edit", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def usuario_edit(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
    
    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios_list"))
    
    if request.method == "POST":
        try:
            role = request.form.get("role")
            new_password = (request.form.get("password") or "").strip()

            if not role:
                flash("Selecciona un rol.", "error")
                return redirect(url_for("usuario_edit", id=id))

            if new_password:
                hash_pwd = generate_password_hash(new_password)
                db.execute(
                    "UPDATE users SET role = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (role, hash_pwd, id)
                )
            else:
                db.execute(
                    "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (role, id)
                )
            db.commit()
            
            log_action(user['id'], "UPDATE", "users", id, None, f"{usuario['email']}")
            
            if new_password:
                flash("Usuario actualizado y contraseña cambiada.", "success")
            else:
                flash("Usuario actualizado.", "success")
            return redirect(url_for("usuarios_list"))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
    
    roles = ["ADMIN", "RAYPAC", "DML_ST", "DML_REPUESTOS"]
    return render_template("usuario_edit.html", target_user=usuario, roles=roles)

@app.route("/admin/usuarios/<int:id>/toggle", methods=["POST"])
@login_required
@role_required("ADMIN")
def usuario_toggle(id):
    user = get_current_user()
    db = get_db()
    usuario = db.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
    
    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios_list"))
    
    nuevo_estado = 1 - usuario['is_active']
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (nuevo_estado, id))
    db.commit()
    
    log_action(user['id'], "TOGGLE", "users", id, str(usuario['is_active']), str(nuevo_estado))
    
    estado_texto = "activado" if nuevo_estado else "desactivado"
    flash(f"Usuario {estado_texto} correctamente.", "success")
    return redirect(url_for("usuarios_list"))

# ======================== ESTADÍSTICAS ========================

@app.route("/estadisticas")
@login_required
@permission_required(read_roles=["DML_ST"], write_roles=["DML_REPUESTOS"])
def estadisticas(readonly=False):
    """Dashboard de estadísticas de repuestos más utilizados."""
    user = get_current_user()
    db = get_db()
    
    # Determinar ubicación según rol
    if user['role'] == 'ADMIN':
        ubicacion = request.args.get("ubicacion", "DML")
        ubicaciones_disponibles = ["RAYPAC", "DML"]
    else:
        ubicacion = "DML"  # DML_REPUESTOS y DML_ST solo ven DML
        ubicaciones_disponibles = []
    
    # Top 10 repuestos más utilizados (solo tiene sentido para DML, donde se usan en reparaciones)
    if ubicacion == "DML":
        top_repuestos = db.execute("""
            SELECT 
                e.codigo_repuesto,
                e.item,
                e.total_usos,
                e.cantidad_utilizada,
                e.fecha_ultimo_uso,
                COALESCE(su.cantidad, 0) as stock_actual
            FROM estadisticas_repuestos e
            LEFT JOIN stock_ubicaciones su ON su.codigo_repuesto = e.codigo_repuesto AND su.ubicacion = 'DML'
            ORDER BY e.total_usos DESC
            LIMIT 10
        """).fetchall()
    else:
        # RAYPAC no tiene "top usos" porque no usa repuestos, solo envía
        top_repuestos = []
    
    # Repuestos críticos (stock bajo) por ubicación
    repuestos_criticos = db.execute("""
        SELECT 
            su.codigo_repuesto,
            m.item,
            su.cantidad as stock_actual,
            su.ubicacion
        FROM stock_ubicaciones su
        LEFT JOIN matriz_repuestos m ON m.codigo_repuesto = su.codigo_repuesto
        WHERE su.cantidad <= 2 AND su.ubicacion = ?
        ORDER BY su.cantidad ASC
    """, (ubicacion,)).fetchall()
    
    # Estadísticas generales
    stats = {
        "total_repuestos": db.execute("SELECT COUNT(*) as cnt FROM matriz_repuestos").fetchone()['cnt'],
        "repuestos_en_ubicacion": db.execute(
            "SELECT COUNT(*) as cnt FROM stock_ubicaciones WHERE ubicacion = ?",
            (ubicacion,)
        ).fetchone()['cnt'],
        "total_movimientos": db.execute("SELECT SUM(total_usos) as total FROM estadisticas_repuestos").fetchone()['total'] or 0 if ubicacion == "DML" else 0,
        "fichas_completadas": db.execute("SELECT COUNT(*) as cnt FROM dml_fichas WHERE is_closed = 1").fetchone()['cnt'] if ubicacion == "DML" else 0,
    }
    
    return render_template(
        "estadisticas.html",
        user=user,
        top_repuestos=top_repuestos,
        repuestos_criticos=repuestos_criticos,
        stats=stats,
        ubicacion=ubicacion,
        ubicaciones_disponibles=ubicaciones_disponibles,
        readonly=readonly
    )

# ======================== EXPORTACIONES CSV ========================

@app.route("/export/fichas-csv")
@login_required
@role_required("ADMIN", "DML_ST")
def export_fichas_csv():
    """Exportar fichas DML a CSV"""
    import csv
    from io import StringIO
    
    db = get_db()
    fichas = db.execute("""
        SELECT f.numero_ficha, f.fecha_ingreso, f.fecha_egreso, f.estado_reparacion,
               f.tecnico, f.tecnico_resp, f.n_ciclos, f.numero_remito_salida,
               r.cliente, r.numero_serie, r.modelo_maquina
        FROM dml_fichas f
        LEFT JOIN raypac_entries r ON f.raypac_id = r.id
        ORDER BY f.created_at DESC
    """).fetchall()
    
    # Crear CSV en memoria
    si = StringIO()
    writer = csv.writer(si)
    
    # Header
    writer.writerow([
        'N° Ficha', 'Cliente', 'Serie', 'Modelo', 'Estado',
        'Fecha Ingreso', 'Fecha Egreso', 'Técnico', 'Responsable',
        'N° Ciclos', 'Remito Salida'
    ])
    
    # Datos
    for f in fichas:
        writer.writerow([
            f['numero_ficha'], f['cliente'], f['numero_serie'], f['modelo_maquina'],
            f['estado_reparacion'], f['fecha_ingreso'], f['fecha_egreso'] or '',
            f['tecnico'], f['tecnico_resp'], f['n_ciclos'], f['numero_remito_salida'] or ''
        ])
    
    # Preparar respuesta
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=fichas_dml_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    
    return output

@app.route("/export/stock-csv")
@login_required
@role_required("ADMIN", "DML_REPUESTOS", "RAYPAC")
def export_stock_csv():
    """Exportar stock a CSV"""
    import csv
    from io import StringIO
    
    db = get_db()
    stock = db.execute("""
        SELECT m.codigo_repuesto, m.item,
               COALESCE(su_dml.cantidad, 0) as stock_dml,
               COALESCE(su_raypac.cantidad, 0) as stock_raypac,
               (COALESCE(su_dml.cantidad, 0) + COALESCE(su_raypac.cantidad, 0)) as stock_total
        FROM matriz_repuestos m
        LEFT JOIN stock_ubicaciones su_dml ON su_dml.codigo_repuesto = m.codigo_repuesto AND su_dml.ubicacion = 'DML'
        LEFT JOIN stock_ubicaciones su_raypac ON su_raypac.codigo_repuesto = m.codigo_repuesto AND su_raypac.ubicacion = 'RAYPAC'
        ORDER BY m.codigo_repuesto
    """).fetchall()
    
    # Crear CSV en memoria
    si = StringIO()
    writer = csv.writer(si)
    
    # Header
    writer.writerow(['Código', 'Descripción', 'Stock DML', 'Stock RAYPAC', 'Stock Total'])
    
    # Datos
    for s in stock:
        writer.writerow([
            s['codigo_repuesto'], s['item'], s['stock_dml'],
            s['stock_raypac'], s['stock_total']
        ])
    
    # Preparar respuesta
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=stock_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    
    return output

@app.route("/export/raypac-csv")
@login_required
@role_required("ADMIN", "RAYPAC")
def export_raypac_csv():
    """Exportar ingresos RAYPAC a CSV"""
    import csv
    from io import StringIO
    
    db = get_db()
    entries = db.execute("""
        SELECT r.numero_correlativo, r.fecha_recepcion, r.tipo_solicitud, r.cliente,
               r.numero_serie, r.modelo_maquina, r.comercial, r.numero_remito,
               r.is_frozen, r.contacto_cliente, r.email_cliente
        FROM raypac_entries r
        ORDER BY r.created_at DESC
    """).fetchall()
    
    # Crear CSV en memoria
    si = StringIO()
    writer = csv.writer(si)
    
    # Header
    writer.writerow([
        'N° Correlativo', 'Fecha Recepción', 'Tipo', 'Cliente', 'Serie',
        'Modelo', 'Comercial', 'Remito', 'Estado', 'Contacto', 'Email'
    ])
    
    # Datos
    for e in entries:
        estado = 'Freezado' if e['is_frozen'] else 'Editable'
        writer.writerow([
            e['numero_correlativo'], e['fecha_recepcion'], e['tipo_solicitud'],
            e['cliente'], e['numero_serie'], e['modelo_maquina'], e['comercial'],
            e['numero_remito'] or '', estado, e['contacto_cliente'] or '',
            e['email_cliente'] or ''
        ])
    
    # Preparar respuesta
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=raypac_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    
    return output

# ===================================
# API ENDPOINTS
# ===================================

@app.route("/api/verificar-stock/<codigo>")
@login_required
def verificar_stock_api(codigo):
    """API para verificar existencia y stock de un repuesto en tiempo real"""
    repuesto = db.execute(
        "SELECT codigo_repuesto, descripcion, stock FROM stock_repuestos WHERE codigo_repuesto = ?",
        (codigo.upper(),)
    )
    
    if repuesto:
        return jsonify({
            "existe": True,
            "stock": repuesto[0]['stock'],
            "descripcion": repuesto[0]['descripcion'],
            "codigo": repuesto[0]['codigo_repuesto']
        })
    else:
        return jsonify({
            "existe": False,
            "stock": 0,
            "descripcion": "",
            "codigo": codigo.upper()
        })

# ======================== MAIN ========================

if __name__ == "__main__":
    import sys
    
    # Inicializar BD si no existe
    with app.app_context():
        db_path = app.config["DATABASE"]
        if not os.path.exists(db_path):
            print("[DB] Creando base de datos...")
            init_db()
            print("[DB] Base de datos creada exitosamente")
        else:
            # Aplicar migraciones a BD existente
            migrate_db()
    
    if len(sys.argv) > 1 and sys.argv[1] == "init-db":
        with app.app_context():
            init_db()
        print("Base de datos inicializada.")
    else:
        app.run(debug=True)
