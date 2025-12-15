"""
Script de prueba para verificar todas las alertas de email del sistema DML
Ejecutar después de configurar SMTP en Render
"""
import sqlite3
import sys
from datetime import datetime

def test_email_alerts():
    """Verifica configuración y preparación para pruebas de emails"""
    
    print("=" * 70)
    print("🧪 VERIFICACIÓN DE ALERTAS DE EMAIL - SISTEMA DML")
    print("=" * 70)
    
    try:
        # Conectar a la base de datos
        db = sqlite3.connect("dml.db")
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        print("\n📊 ESTADO ACTUAL DEL SISTEMA:")
        print("-" * 70)
        
        # 1. Verificar ingresos RAYPAC con email
        raypac_entries = cursor.execute("""
            SELECT id, numero_serie, comercial, mail_comercial, is_frozen
            FROM raypac_entries
            WHERE mail_comercial IS NOT NULL AND mail_comercial != ''
            ORDER BY fecha_recepcion DESC LIMIT 5
        """).fetchall()
        
        print(f"\n1️⃣  INGRESOS RAYPAC CON EMAIL CONFIGURADO: {len(raypac_entries)}")
        if raypac_entries:
            for entry in raypac_entries:
                print(f"   - ID {entry['id']}: Serie {entry['numero_serie']} | Email: {entry['mail_comercial']}")
                print(f"     Comercial: {entry['comercial']} | Frozen: {entry['is_frozen']}")
        else:
            print("   ⚠️  No hay ingresos con email. Necesario para probar alertas 1 y 2")
        
        # 2. Verificar tickets creados
        tickets = cursor.execute("""
            SELECT numero_ticket, ficha_id, estado, fecha_creacion
            FROM tickets
            ORDER BY fecha_creacion DESC LIMIT 5
        """).fetchall()
        
        print(f"\n2️⃣  TICKETS CREADOS: {len(tickets)}")
        if tickets:
            for ticket in tickets:
                print(f"   - {ticket['numero_ticket']} | Estado: {ticket['estado']} | Fecha: {ticket['fecha_creacion']}")
        else:
            print("   ℹ️  No hay tickets registrados aún")
        
        # 3. Verificar fichas cerradas con email
        fichas_cerradas = cursor.execute("""
            SELECT f.id, f.numero_ficha, f.estado_reparacion, r.mail_comercial
            FROM dml_fichas f
            JOIN raypac_entries r ON f.raypac_id = r.id
            WHERE f.estado_reparacion LIKE '%ENTREGADA%'
            ORDER BY f.fecha_egreso DESC LIMIT 5
        """).fetchall()
        
        print(f"\n3️⃣  FICHAS CERRADAS: {len(fichas_cerradas)}")
        if fichas_cerradas:
            for ficha in fichas_cerradas:
                email = ficha['mail_comercial'] or "Sin email"
                print(f"   - Ficha #{ficha['numero_ficha']:07d} | Estado: {ficha['estado_reparacion']} | Email: {email}")
        else:
            print("   ℹ️  No hay fichas cerradas aún")
        
        # 4. Verificar envíos de repuestos confirmados
        envios = cursor.execute("""
            SELECT id, numero_remito, estado, fecha_envio, fecha_recepcion
            FROM envios_repuestos
            WHERE estado = 'CONFIRMADO'
            ORDER BY fecha_envio DESC LIMIT 5
        """).fetchall()
        
        print(f"\n4️⃣  ENVÍOS DE REPUESTOS: {len(envios)}")
        if envios:
            for envio in envios:
                estado_text = "✅ Recibido" if envio['fecha_recepcion'] else "📦 Confirmado"
                print(f"   - Remito {envio['numero_remito']} | {estado_text}")
                if envio['fecha_recepcion']:
                    print(f"     Recepción: {envio['fecha_recepcion']}")
        else:
            print("   ℹ️  No hay envíos registrados aún")
        
        # 5. Verificar repuestos con stock bajo
        stock_bajo = cursor.execute("""
            SELECT s.codigo_repuesto, m.item, s.cantidad, s.ubicacion
            FROM stock_ubicaciones s
            LEFT JOIN matriz_repuestos m ON s.codigo_repuesto = m.codigo_repuesto
            WHERE s.cantidad <= 2 AND s.cantidad >= 0
            ORDER BY s.cantidad ASC, s.codigo_repuesto
        """).fetchall()
        
        print(f"\n5️⃣  REPUESTOS CON STOCK BAJO (≤2): {len(stock_bajo)}")
        if stock_bajo:
            for item in stock_bajo:
                if item['cantidad'] == 0:
                    nivel = "🔴 AGOTADO"
                elif item['cantidad'] == 1:
                    nivel = "🟡 ÚLTIMO"
                else:
                    nivel = "🟠 BAJO"
                print(f"   {nivel} {item['codigo_repuesto']}: {item['item']} | Cantidad: {item['cantidad']} ({item['ubicacion']})")
        else:
            print("   ℹ️  No hay repuestos con stock bajo")
        
        print("\n" + "=" * 70)
        print("📋 GUÍA DE PRUEBAS:")
        print("=" * 70)
        
        print("\n✅ PRUEBA 1: Ticket de Seguimiento")
        if raypac_entries and any(not e['is_frozen'] for e in raypac_entries):
            entry = next(e for e in raypac_entries if not e['is_frozen'])
            print(f"   1. Usar ingreso RAYPAC ID {entry['id']} (Serie: {entry['numero_serie']})")
            print(f"   2. Freezar con remito (ej: 12345)")
            print(f"   3. Crear ticket desde DML")
            print(f"   4. Verificar email en: {entry['mail_comercial']}")
        else:
            print("   ⚠️  Crear nuevo ingreso RAYPAC con email primero")
        
        print("\n✅ PRUEBA 2: Máquina Lista")
        if tickets:
            ticket = tickets[0]
            print(f"   1. Abrir ticket {ticket['numero_ticket']}")
            print(f"   2. Completar ficha asociada")
            print(f"   3. Cambiar estado a 'MÁQUINA ENTREGADA'")
            print(f"   4. Cerrar ficha")
            print(f"   5. Verificar email en: {ticket['mail_comercial']}")
        else:
            print("   ⚠️  Completar Prueba 1 primero")
        
        print("\n✅ PRUEBA 3: Confirmación Recepción Repuestos")
        print("   1. RAYPAC: Crear envío de repuestos")
        print("   2. Agregar repuestos al envío")
        print("   3. Freezar con número de remito")
        print("   4. DML: Ir a 'Envíos de Repuestos'")
        print("   5. Confirmar recepción del envío")
        print("   6. Verificar email de confirmación")
        
        print("\n✅ PRUEBA 4: Alertas de Stock")
        print("   1. Crear repuesto nuevo con cantidad = 2")
        print("   2. Usar ese repuesto en una ficha (stock pasa a 1)")
        print("   3. Verificar email AMARILLO (último repuesto)")
        print("   4. Usar nuevamente el repuesto (stock pasa a 0)")
        print("   5. Verificar email ROJO (agotado)")
        
        print("\n" + "=" * 70)
        print("💡 TIPS:")
        print("   - Todos los emails llegarán a: sistemadegestiondml@gmail.com")
        print("   - Revisar bandeja de entrada Y spam")
        print("   - Los emails tienen asuntos descriptivos (🎫, ✅, 🔔)")
        print("=" * 70 + "\n")
        
        db.close()
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ ERROR DE BASE DE DATOS: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n")
    success = test_email_alerts()
    sys.exit(0 if success else 1)
