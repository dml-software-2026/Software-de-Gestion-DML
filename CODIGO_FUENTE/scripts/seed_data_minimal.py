#!/usr/bin/env python
"""
Script para cargar datos MÍNIMOS REALISTAS de prueba.
Ejecutar con: python seed_data_minimal.py
"""
import os
import sys
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'CODIGO_FUENTE'))

from app import app, crear_ticket, generate_ficha_number, get_db, init_db


def seed_minimal():
    """Carga datos mínimos realistas para demostración."""
    
    with app.app_context():
        # Inicializar BD (crear tablas)
        print("[SEED] Inicializando BD...")
        init_db()
        print("✓ BD inicializada")
        
        db = get_db()
        
        print("\n[SEED] Limpiando base de datos...")
        # Limpiar TODO
        tables = [
            "ticket_historial", "audit_log", "mail_log", "stock_alertas",
            "estadisticas_repuestos", "tickets", "dml_repuestos", "dml_partes",
            "dml_fichas", "envios_repuestos_detalles", "envios_repuestos",
            "stock_ubicaciones", "stock_dml", "raypac_entries", "matriz_repuestos", "users"
        ]
        for table in tables:
            try:
                db.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        db.commit()
        print("✓ Base de datos limpiada")
        
        # ======================== USUARIOS ========================
        print("\n[SEED] Creando usuarios...")
        usuarios = [
            ('admin@dml.local', 'admin', 'Administrador', 'ADMIN'),
            ('raypac@dml.local', 'raypac', 'Casa Matriz RAYPAC', 'RAYPAC'),
            ('tecnico@dml.local', 'tecnico', 'Juan Pérez', 'DML_ST'),
            ('repuestos@dml.local', 'repuestos', 'Carlos López', 'DML_REPUESTOS'),
        ]
        
        for email, pwd, nombre, role in usuarios:
            db.execute("""
                INSERT INTO users (email, password_hash, nombre, role, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (email, generate_password_hash(pwd), nombre, role))
        db.commit()
        print(f"✓ {len(usuarios)} usuarios creados")
        
        # ======================== REPUESTOS (10 ejemplos) ========================
        print("\n[SEED] Cargando matriz de repuestos...")
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
        print(f"✓ {len(repuestos)} repuestos en matriz")
        
        # ======================== STOCK RAYPAC ========================
        print("\n[SEED] Cargando stock RAYPAC...")
        stock_raypac = [
            ("A000001", 15),  # OK
            ("A000002", 8),   # OK
            ("A000003", 3),   # OK
            ("A000004", 2),   # NARANJA
            ("A000005", 10),  # OK
            ("A000006", 1),   # AMARILLO
            ("A000007", 20),  # OK
            ("A000008", 5),   # OK
            ("A000009", 0),   # ROJO
            ("A000010", 12),  # OK
        ]
        
        for codigo, cant in stock_raypac:
            db.execute("""
                INSERT INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad)
                VALUES (?, 'RAYPAC', ?)
            """, (codigo, cant))
        db.commit()
        print(f"✓ Stock RAYPAC cargado ({len(stock_raypac)} ítems)")
        
        # ======================== STOCK DML ========================
        print("\n[SEED] Cargando stock DML...")
        stock_dml = [
            ("A000001", 5),   # OK
            ("A000002", 3),   # OK
            ("A000003", 2),   # NARANJA
            ("A000004", 1),   # AMARILLO
            ("A000005", 4),   # OK
            ("A000006", 0),   # ROJO
            ("A000007", 8),   # OK
            ("A000008", 2),   # NARANJA
            ("A000009", 3),   # OK
            ("A000010", 6),   # OK
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
        db.commit()
        print(f"✓ Stock DML cargado ({len(stock_dml)} ítems)")
        
        # ======================== INGRESO RAYPAC #1 ========================
        print("\n[SEED] Creando ingreso RAYPAC #1...")
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        fecha_ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        db.execute("""
            INSERT INTO raypac_entries 
            (numero_correlativo, fecha_recepcion, tipo_solicitud, cliente, numero_serie,
             modelo_maquina, tipo_maquina, numero_bateria, numero_cargador,
             diagnostico_ingreso, comercial, mail_comercial, numero_remito, is_frozen)
            VALUES (1, ?, 'REPARACION', 'ACME SA', 'EQ-2024-001',
                    'MB380', 'A BATERIA', 'BAT-001', 'CARG-001',
                    'Equipo no enciende, posible falla en motor de arrastre',
                    'María González', 'maria.gonzalez@raypac.com', 'RP-2024-00001', 1)
        """, (fecha_ayer,))
        raypac_id_1 = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        db.commit()
        print("✓ Ingreso RAYPAC #1 creado (freezado con remito)")
        
        # ======================== FICHA DML #1 ========================
        print("\n[SEED] Creando ficha DML #1 (en reparación)...")
        numero_ficha_1 = generate_ficha_number()
        
        db.execute("""
            INSERT INTO dml_fichas 
            (numero_ficha, raypac_id, fecha_ingreso, tecnico, diagnostico_inicial,
             diagnostico_reparacion, observaciones, estado_reparacion,
             n_ciclos, tecnico_resp, tipo_trabajo)
            VALUES (?, ?, ?, 'Juan Pérez', 'Motor de arrastre quemado, requiere reemplazo',
                    'Se reemplazó motor de arrastre y se probó funcionamiento', 
                    'Cliente reporta que el equipo dejó de funcionar tras una sobrecarga',
                    'EN REPARACION', 0, 'Juan Pérez', 'REPARACIÓN')
        """, (numero_ficha_1, raypac_id_1, fecha_ayer))
        ficha_id_1 = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        
        # Crear ticket
        numero_ticket_1 = crear_ticket(ficha_id_1, 'EQ-2024-001')
        
        # Partes del equipo
        partes = [
            ('ESTADO DEL EQUIPO', 'INSPECCIONADO'),
            ('CARCAZA', 'OK'),
            ('CUBRE FEEDWHEEL', 'OK'),
            ('MANGO', 'OK'),
            ('BOTONES', 'OK'),
            ('MOTOR DE ARRASTRE', 'REEMPLAZADO'),
            ('MOTOR DE SELLADO', 'OK'),
            ('CUCHILLA', 'OK'),
            ('SERVO', 'OK'),
            ('RUEDA DE ARRASTRE', 'OK'),
            ('RESORTE DE MANIJA', 'OK'),
            ('OTROS', 'OK')
        ]
        
        for nombre_parte, estado in partes:
            db.execute("""
                INSERT INTO dml_partes (ficha_id, nombre_parte, estado)
                VALUES (?, ?, ?)
            """, (ficha_id_1, nombre_parte, estado))
        
        # Repuesto utilizado (ya descontado del stock)
        db.execute("""
            INSERT INTO dml_repuestos 
            (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada,
             estado_repuesto, en_stock, en_falta)
            VALUES (?, 'A000001', 'MOTOR DE ARRASTRE', 1, 1, 'EN STOCK', 1, 0)
        """, (ficha_id_1,))
        
        # Registrar estadística de uso
        db.execute("""
            INSERT INTO estadisticas_repuestos 
            (codigo_repuesto, item, cantidad_utilizada, fecha_ultimo_uso, total_usos)
            VALUES ('A000001', 'MOTOR DE ARRASTRE', 1, ?, 1)
        """, (fecha_ayer,))
        
        db.commit()
        print(f"✓ Ficha DML #{numero_ficha_1} creada con ticket {numero_ticket_1}")
        
        # ======================== INGRESO RAYPAC #2 (SIN REMITO AÚN) ========================
        print("\n[SEED] Creando ingreso RAYPAC #2 (pendiente remito)...")
        db.execute("""
            INSERT INTO raypac_entries 
            (numero_correlativo, fecha_recepcion, tipo_solicitud, cliente, numero_serie,
             modelo_maquina, tipo_maquina, numero_bateria, numero_cargador,
             diagnostico_ingreso, comercial, mail_comercial, is_frozen)
            VALUES (2, ?, 'REPARACION', 'TechCorp SRL', 'EQ-2024-002',
                    'MB450', 'ELECTRICA', NULL, NULL,
                    'Cuchilla desgastada, requiere afilado o reemplazo',
                    'Pedro Martínez', 'pedro.martinez@raypac.com', 0)
        """, (fecha_hoy,))
        db.commit()
        print("✓ Ingreso RAYPAC #2 creado (sin remito, editable)")
        
        # ======================== ENVÍO DE REPUESTOS RAYPAC→DML ========================
        print("\n[SEED] Creando envío de repuestos RAYPAC→DML...")
        fecha_hace_2_dias = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        
        db.execute("""
            INSERT INTO envios_repuestos 
            (numero_remito, fecha_envio, fecha_recepcion, estado)
            VALUES ('RP-2024-00100', ?, ?, 'RECIBIDO')
        """, (fecha_hace_2_dias, fecha_ayer))
        envio_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
        
        # Detalles del envío (ya recibido y sumado a DML)
        detalles_envio = [
            ('A000002', 2),
            ('A000007', 5),
        ]
        
        for codigo, cant in detalles_envio:
            db.execute("""
                INSERT INTO envios_repuestos_detalles (envio_id, codigo_repuesto, cantidad)
                VALUES (?, ?, ?)
            """, (envio_id, codigo, cant))
        
        db.commit()
        print("✓ Envío RP-2024-00100 creado (recibido)")
        
        # ======================== RESUMEN ========================
        print("\n" + "="*60)
        print("✅ SEED MINIMAL COMPLETADO")
        print("="*60)
        print("\n📊 RESUMEN DE DATOS:")
        print(f"  • {len(usuarios)} usuarios creados")
        print(f"  • {len(repuestos)} repuestos en matriz")
        print(f"  • {len(stock_raypac)} ítems en stock RAYPAC")
        print(f"  • {len(stock_dml)} ítems en stock DML")
        print("  • 2 ingresos RAYPAC")
        print("  • 1 ficha DML con ticket")
        print("  • 1 envío de repuestos RAYPAC→DML")
        
        print("\n🔑 CREDENCIALES:")
        print("  • Admin:     admin@dml.local / admin")
        print("  • RAYPAC:    raypac@dml.local / raypac")
        print("  • Técnico:   tecnico@dml.local / tecnico")
        print("  • Repuestos: repuestos@dml.local / repuestos")
        
        print("\n📝 ESCENARIOS DE PRUEBA:")
        print("  1. Login RAYPAC → Ver stock RAYPAC (alertas naranjas/amarillas/rojas)")
        print("  2. Login RAYPAC → Completar ingreso #2 con remito y enviarlo")
        print("  3. Login Técnico → Ver ficha #" + str(numero_ficha_1) + " en reparación")
        print("  4. Login Repuestos → Ver stock DML, estadísticas, recepcionar envíos")
        print("  5. Login Admin → Cambiar entre RAYPAC/DML, ver estadísticas")
        
        print("\n🎯 ALERTAS DE STOCK CONFIGURADAS:")
        print("  RAYPAC:")
        print("    🔴 ROJO (0):     A000009 (CARGADOR)")
        print("    🟡 AMARILLO (1): A000006 (SERVO MOTOR)")
        print("    🟠 NARANJA (2):  A000004 (RUEDA DE ARRASTRE)")
        print("  DML:")
        print("    🔴 ROJO (0):     A000006 (SERVO MOTOR)")
        print("    🟡 AMARILLO (1): A000004 (RUEDA DE ARRASTRE)")
        print("    🟠 NARANJA (2):  A000003 (CUCHILLA), A000008 (BATERIA)")

if __name__ == "__main__":
    seed_minimal()
