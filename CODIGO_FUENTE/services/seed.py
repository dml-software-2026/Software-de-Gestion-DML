import os
import csv

from werkzeug.security import generate_password_hash

from CODIGO_FUENTE.config import BASE_DIR


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
                    INSERT INTO matriz_repuestos
                    (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                    VALUES (%s, %s, %s, %s, %s, 'DML')
                    ON CONFLICT (codigo_repuesto) DO NOTHING
                """, (idx, codigo, item, cantidad, cantidad))

                # 2. Insertar en stock_ubicaciones (ubicación DML)
                db.execute("""
                    INSERT INTO stock_ubicaciones
                    (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                    VALUES (%s, 'DML', %s, %s)
                    ON CONFLICT (codigo_repuesto, ubicacion) DO NOTHING
                """, (codigo, cantidad, codigo_ubicacion))

                repuestos_cargados += 1

                if idx % 50 == 0:
                    db.commit()

        db.commit()

        # 3. Inicializar stock RAYPAC con cantidades desde matriz_repuestos
        print("[STOCK CSV] 📦 Inicializando stock RAYPAC...")
        db.execute("""
            INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
            SELECT codigo_repuesto, 'RAYPAC', cantidad_actual, 'SIN UBICACIÓN'
            FROM matriz_repuestos
            WHERE codigo_repuesto NOT IN (SELECT codigo_repuesto FROM stock_ubicaciones WHERE ubicacion = 'RAYPAC')
            ON CONFLICT (codigo_repuesto, ubicacion) DO NOTHING
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
        from CODIGO_FUENTE.extensions import get_db
        db = get_db()

    # ======================== CREAR USUARIOS POR DEFECTO ========================
    print("[SEED] 👥 Verificando usuarios...")
    check_users = db.execute("SELECT COUNT(*) as total FROM users").fetchone()
    if check_users and check_users['total'] == 0:
        print("[SEED] 🔧 Creando usuarios por defecto...")
        usuarios = [
            ('admin@dml.local', 'admin', 'Administrador', 'ADMIN'),
            ('raypac@dml.local', 'raypac', 'Casa Matriz RAYPAC', 'RAYPAC'),
            ('tecnico@dml.local', 'tecnico', 'Juan Pérez', 'DML_ST'),
            ('repuestos@dml.local', 'repuestos', 'Carlos López', 'DML_REPUESTOS'),
        ]

        for email, pwd, nombre, role in usuarios:
            db.execute("""
                INSERT INTO users (email, password_hash, nombre, role, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (email, generate_password_hash(pwd), nombre, role))
        db.commit()
        print(f"[SEED] ✅ {len(usuarios)} usuarios creados")
    else:
        print(f"[SEED] ✓ Ya hay {check_users['total']} usuarios en el sistema")

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
                VALUES (%s, %s, %s, 0, 0, 'DML')
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
                VALUES (%s, 'RAYPAC', %s)
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
                VALUES (%s, 'DML', %s)
            """, (codigo, cant))
            # Legacy stock_dml para compatibilidad
            db.execute("""
                INSERT INTO stock_dml (codigo_repuesto, item, cantidad, cantidad_minima, estado_alerta)
                SELECT %s, item, %s, 2, 'OK'
                FROM matriz_repuestos WHERE codigo_repuesto = %s
            """, (codigo, cant, codigo))

    # DATOS DE EJEMPLO REMOVIDOS - Solo CSV carga permanente
    print(f"[SEED] ✅ {repuestos_count} repuestos cargados desde CSV")
    print("[SEED] Sistema listo para usar")