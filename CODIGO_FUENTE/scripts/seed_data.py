#!/usr/bin/env python
"""
Script para cargar datos de prueba en la base de datos.
Ejecutar con: python seed_data.py
"""
import sys
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Agregar CODIGO_FUENTE al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'CODIGO_FUENTE'))

from app import app, get_db, generate_ticket_number

def seed_database():
    """Carga datos iniciales de prueba."""
    
    with app.app_context():
        db = get_db()
        
        print("[SEED] Iniciando carga de datos de prueba...")
        print("[SEED] Limpiando datos existentes...")
        
        # Limpiar datos existentes (respetando foreign keys)
        db.execute("DELETE FROM ticket_historial")
        db.execute("DELETE FROM logs_auditoria")
        db.execute("DELETE FROM freezing_log")
        db.execute("DELETE FROM tickets")
        db.execute("DELETE FROM dml_repuestos")
        db.execute("DELETE FROM dml_partes")
        db.execute("DELETE FROM dml_fichas")
        db.execute("DELETE FROM envios_repuestos_detalles")
        db.execute("DELETE FROM envios_repuestos")
        db.execute("DELETE FROM stock_ubicaciones WHERE ubicacion = 'RAYPAC'")
        db.execute("DELETE FROM raypac_entries")
        db.execute("DELETE FROM users WHERE email NOT IN ('admin@dml.local')")
        db.commit()
        print("[SEED] Datos existentes limpiados")
        
        # ======================== USUARIOS ========================
        print("\n[SEED] Creando usuarios...")
        usuarios = [
            ('raypac@dml.local', generate_password_hash('raypac'), 'RAYPAC', 'RAYPAC'),
            ('tecnico@dml.local', generate_password_hash('tecnico'), 'Juan Perez', 'DML_ST'),
            ('repuestos@dml.local', generate_password_hash('repuestos'), 'Carlos Lopez', 'DML_REPUESTOS'),
        ]
        
        for email, pwd_hash, nombre, role in usuarios:
            db.execute(
                "INSERT INTO users (email, password_hash, nombre, role, is_active) VALUES (?, ?, ?, ?, 1)",
                (email, pwd_hash, nombre, role)
            )
        db.commit()
        print("[SEED] 3 usuarios creados (+ 1 admin existente)")
        
        # ======================== INGRESOS RAYPAC ========================
        print("\n[SEED] Creando ingresos RAYPAC...")
        raypac_entries = [
            {
                'fecha': (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d'),
                'tipo': 'REPARACION',
                'cliente': 'FERRETERIA CENTRAL SRL',
                'serie': 'EQ-2024-0001',
                'modelo': 'CORTADORA INDUSTRIAL',
                'tipo_maq': 'A BATERIA',
                'bateria': 'BAT-001',
                'cargador': 'CARG-001',
                'diag': 'Motor no enciende, bateria defectuosa',
                'comercial': 'Fernando Garcia',
                'mail': 'fernando@raypac.com'
            },
            {
                'fecha': (datetime.now() - timedelta(days=12)).strftime('%Y-%m-%d'),
                'tipo': 'REPARACION',
                'cliente': 'CONSTRUCCIONES ALVAREZ',
                'serie': 'EQ-2024-0002',
                'modelo': 'TALADRO PROFESIONAL',
                'tipo_maq': 'A BATERIA',
                'bateria': 'BAT-002',
                'cargador': 'CARG-002',
                'diag': 'No mantiene carga, cuchilla floja',
                'comercial': 'Maria Rodriguez',
                'mail': 'maria@raypac.com'
            },
            {
                'fecha': (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d'),
                'tipo': 'REPARACION',
                'cliente': 'TALLERES MECANICOS GOMEZ',
                'serie': 'EQ-2024-0003',
                'modelo': 'MOLADORA ANGULAR',
                'tipo_maq': 'A BATERIA',
                'bateria': 'BAT-003',
                'cargador': 'CARG-003',
                'diag': 'Rueda descentrada, motor lento',
                'comercial': 'Roberto Sanchez',
                'mail': 'roberto@raypac.com'
            },
            {
                'fecha': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
                'tipo': 'REPARACION',
                'cliente': 'PINTURERIAS EXPRESS',
                'serie': 'EQ-2024-0004',
                'modelo': 'DESTORNILLADOR AUTOMATICO',
                'tipo_maq': 'A BATERIA',
                'bateria': 'BAT-004',
                'cargador': 'CARG-004',
                'diag': 'No gira, posible motor bloqueado',
                'comercial': 'Laura Martinez',
                'mail': 'laura@raypac.com'
            },
            {
                'fecha': datetime.now().strftime('%Y-%m-%d'),
                'tipo': 'REPARACION',
                'cliente': 'DISTRIBUIDORA INDUSTRIAL',
                'serie': 'EQ-2024-0005',
                'modelo': 'SIERRA CIRCULAR',
                'tipo_maq': 'A BATERIA',
                'bateria': 'BAT-005',
                'cargador': 'CARG-005',
                'diag': 'Pierde potencia, cuchilla gastada',
                'comercial': 'Diego Flores',
                'mail': 'diego@raypac.com'
            },
        ]
        
        raypac_ids = []
        for idx, entrada in enumerate(raypac_entries, 1):
            db.execute("""
                INSERT INTO raypac_entries 
                (numero_correlativo, fecha_recepcion, tipo_solicitud, cliente, numero_serie, 
                 modelo_maquina, tipo_maquina, numero_bateria, numero_cargador, 
                 diagnostico_ingreso, comercial, mail_comercial, is_frozen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (idx, entrada['fecha'], entrada['tipo'], entrada['cliente'], entrada['serie'],
                  entrada['modelo'], entrada['tipo_maq'], entrada['bateria'], entrada['cargador'],
                  entrada['diag'], entrada['comercial'], entrada['mail']))
            raypac_ids.append(db.execute("SELECT last_insert_rowid() as id").fetchone()['id'])
        
        db.commit()
        print(f"[SEED] {len(raypac_entries)} ingresos RAYPAC creados")

        # ======================== STOCK RAYPAC PARA ENVIOS ========================
        print("\n[SEED] Cargando stock disponible en RAYPAC para envios...")
        stock_raypac = [
            ('B000001', 2),  # Bateria
            ('C000001', 2),  # Cargador rapido
            ('P000001', 4),  # Pulsador inicio
            ('P000002', 3)   # Pulsador parada
        ]
        for codigo, cantidad in stock_raypac:
            db.execute(
                "INSERT OR REPLACE INTO stock_ubicaciones (codigo_repuesto, ubicacion, cantidad) VALUES (?, 'RAYPAC', ?)",
                (codigo, cantidad)
            )
        db.commit()
        print(f"[SEED] Stock RAYPAC cargado ({len(stock_raypac)} items)")
        
        # ======================== FICHAS DML ========================
        print("\n[SEED] Creando fichas ST (DML)...")
        
        fichas_data = [
            {
                'raypac_id': raypac_ids[0],
                'fecha': (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d'),
                'estado': 'EN REPARACION',
                'diag_inicial': 'Motor no responde a comando de encendido',
                'diag_rep': 'Se reemplazo motor de arrastre defectuoso',
                'obs': 'Equipo probado, funciona correctamente',
                'ciclos': 25,
            },
            {
                'raypac_id': raypac_ids[1],
                'fecha': (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'),
                'estado': 'MAQUINA LISTA PARA RETIRAR',
                'diag_inicial': 'Bateria no carga, falla servo izquierdo',
                'diag_rep': 'Se reemplazo bateria y servo izquierdo. Prueba exitosa',
                'obs': 'Revision completa realizada, equipo al 100%',
                'ciclos': 30,
            },
            {
                'raypac_id': raypac_ids[2],
                'fecha': (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d'),
                'estado': 'EN REPARACION',
                'diag_inicial': 'Descentramiento de rueda, motor debil',
                'diag_rep': 'En proceso de reparacion',
                'obs': 'Pendiente reemplazo de eje y calibracion',
                'ciclos': 0,
            },
            {
                'raypac_id': raypac_ids[3],
                'fecha': (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
                'estado': 'A LA ESPERA DE REPUESTOS',
                'diag_inicial': 'Motor bloqueado, no gira',
                'diag_rep': 'Requiere reemplazo de motor completo',
                'obs': 'Esperando llegada de motor de arrastre',
                'ciclos': 0,
            },
            {
                'raypac_id': raypac_ids[4],
                'fecha': datetime.now().strftime('%Y-%m-%d'),
                'estado': 'A LA ESPERA DE REVISION',
                'diag_inicial': 'Perdida de potencia, cuchilla gastada',
                'diag_rep': '',
                'obs': 'Ingreso reciente, pendiente inspeccion inicial',
                'ciclos': 0,
            },
        ]
        
        # Mapear serie por raypac_id para generar tickets
        raypac_series = {rid: raypac_entries[idx]['serie'] for idx, rid in enumerate(raypac_ids)}
        ficha_ids = []

        for idx, ficha_info in enumerate(fichas_data, 501):
            db.execute("""
                INSERT INTO dml_fichas
                (numero_ficha, raypac_id, fecha_ingreso, tecnico,
                 diagnostico_inicial, diagnostico_reparacion, observaciones,
                 estado_reparacion, n_ciclos, tecnico_resp, fecha_egreso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (idx, ficha_info['raypac_id'], ficha_info['fecha'], 'Juan Perez',
                  ficha_info['diag_inicial'], ficha_info['diag_rep'], ficha_info['obs'],
                  ficha_info['estado'], ficha_info['ciclos'], 'Juan Perez',
                  (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d') if ficha_info['estado'] == 'MAQUINA LISTA PARA RETIRAR' else None))
            
            ficha_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']
            ficha_ids.append(ficha_id)

            # Crear ticket asociado y actualizar ficha
            numero_serie = raypac_series.get(ficha_info['raypac_id'], "")
            numero_ticket = generate_ticket_number(numero_serie)
            db.execute(
                "INSERT INTO tickets (numero_ticket, ficha_id, numero_serie) VALUES (?, ?, ?)",
                (numero_ticket, ficha_id, numero_serie)
            )
            db.execute("UPDATE dml_fichas SET numero_ticket = ? WHERE id = ?", (numero_ticket, ficha_id))
            
            # Crear partes estandar
            partes = [
                "ESTADO DEL EQUIPO", "CARCAZA", "CUBRE FEEDWHEEL", "MANGO",
                "BOTONES", "MOTOR DE ARRASTRE", "MOTOR DE SELLADO", "CUCHILLA",
                "SERVO", "RUEDA DE ARRASTRE", "RESORTE DE MANIJA", "OTROS"
            ]
            
            estados_partes = {
                'A LA ESPERA DE REVISION': 'POR INSPECCIONAR',
                'EN REPARACION': 'EN REPARACION',
                'A LA ESPERA DE REPUESTOS': 'DAÑADO',
                'MAQUINA LISTA PARA RETIRAR': 'REPARADO',
            }
            
            estado_parte = estados_partes.get(ficha_info['estado'], 'POR INSPECCIONAR')
            
            for parte in partes:
                db.execute(
                    "INSERT INTO dml_partes (ficha_id, nombre_parte, estado) VALUES (?, ?, ?)",
                    (ficha_id, parte, estado_parte)
                )
        
        db.commit()
        print(f"[SEED] {len(fichas_data)} fichas DML creadas")
        
        # ======================== REPUESTOS UTILIZADOS ========================
        print("\n[SEED] Agregando repuestos utilizados a fichas...")
        
        # Ficha 1: Con repuestos
        db.execute("""
            INSERT INTO dml_repuestos (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
            VALUES (?, 'M000001', 'MOTOR ARRASTRE PRINCIPAL', 1, 1, 'EN STOCK', 1, 0)
        """, (ficha_ids[0],))
        
        db.execute("""
            INSERT INTO dml_repuestos (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
            VALUES (?, 'K000002', 'KIT SELLADO MOTOR', 1, 1, 'EN STOCK', 1, 0)
        """, (ficha_ids[0],))
        
        # Ficha 2: Con repuestos
        db.execute("""
            INSERT INTO dml_repuestos (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
            VALUES (?, 'B000001', 'BATERIA LITIO ITA24', 1, 1, 'EN STOCK', 1, 0)
        """, (ficha_ids[1],))
        
        db.execute("""
            INSERT INTO dml_repuestos (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
            VALUES (?, 'S000001', 'SERVO MOTOR IZQUIERDO', 1, 1, 'EN STOCK', 1, 0)
        """, (ficha_ids[1],))
        
        # Ficha 4: Con repuesto en falta
        db.execute("""
            INSERT INTO dml_repuestos (ficha_id, codigo_repuesto, descripcion, cantidad, cantidad_utilizada, estado_repuesto, en_stock, en_falta)
            VALUES (?, 'M000001', 'MOTOR ARRASTRE PRINCIPAL', 1, 0, 'EN FALTA', 0, 1)
        """, (ficha_ids[3],))
        
        db.commit()
        print("[SEED] Repuestos agregados a fichas")
        
        # ======================== ACTUALIZAR STOCK ========================
        print("\n[SEED] Actualizando stock segun uso...")
        
        # Disminuir stock por repuestos utilizados
        db.execute("UPDATE stock_dml SET cantidad = cantidad - 1 WHERE codigo_repuesto = 'M000001'")
        db.execute("UPDATE stock_dml SET cantidad = cantidad - 1 WHERE codigo_repuesto = 'K000002'")
        db.execute("UPDATE stock_dml SET cantidad = cantidad - 1 WHERE codigo_repuesto = 'B000001'")
        db.execute("UPDATE stock_dml SET cantidad = cantidad - 1 WHERE codigo_repuesto = 'S000001'")
        
        db.commit()
        print("[SEED] Stock actualizado")
        
        print("\n" + "="*60)
        print("[SEED] DATOS DE PRUEBA CARGADOS EXITOSAMENTE")
        print("="*60)
        print("\nDatos creados:")
        print("  - 3 nuevos usuarios + 1 admin existente")
        print("  - 5 Ingresos RAYPAC")
        print("  - 5 Fichas ST (DML)")
        print("  - Repuestos asignados a fichas")
        print("  - Stock actualizado automaticamente")
        print("\nCuentas de prueba:")
        print("  - admin@dml.local / admin")
        print("  - raypac@dml.local / raypac")
        print("  - tecnico@dml.local / tecnico")
        print("  - repuestos@dml.local / repuestos")
        print("\n")

if __name__ == "__main__":
    seed_database()
