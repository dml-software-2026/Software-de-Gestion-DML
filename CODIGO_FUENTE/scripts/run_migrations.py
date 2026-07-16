"""
Script de migraciones para producción
Ejecutar ANTES del primer uso después del deploy
"""
import sqlite3
import sys

def migrate_envios_repuestos(db):
    """Agregar columnas faltantes a envios_repuestos"""
    print("\n[1/2] Migrando envios_repuestos...")
    cursor = db.cursor()
    
    columns = [col[1] for col in cursor.execute("PRAGMA table_info(envios_repuestos)").fetchall()]
    changed = False
    
    if 'estado_envio' not in columns:
        cursor.execute("ALTER TABLE envios_repuestos ADD COLUMN estado_envio TEXT DEFAULT 'ENVIADO'")
        print("  ✅ Columna estado_envio agregada")
        changed = True
    
    if 'is_frozen' not in columns:
        cursor.execute("ALTER TABLE envios_repuestos ADD COLUMN is_frozen INTEGER DEFAULT 1")
        print("  ✅ Columna is_frozen agregada")
        changed = True
    
    if 'tipo_entrega' not in columns:
        cursor.execute("ALTER TABLE envios_repuestos ADD COLUMN tipo_entrega TEXT DEFAULT 'REPUESTOS'")
        print("  ✅ Columna tipo_entrega agregada")
        changed = True
    
    if not changed:
        print("  ⏭️  Ya tiene todas las columnas necesarias")
    
    return changed

def migrate_tickets(db):
    """Recrear tabla tickets con todas las columnas necesarias"""
    print("\n[2/2] Migrando tickets...")
    cursor = db.cursor()
    
    columns = [col[1] for col in cursor.execute("PRAGMA table_info(tickets)").fetchall()]
    
    if 'tecnico_responsable' not in columns:
        print("  ⚠️  Recreando tabla con todas las columnas...")
        
        # Backup
        cursor.execute("""
            CREATE TABLE tickets_backup AS 
            SELECT id, numero_ticket, ficha_id, numero_serie, estado, 
                   fecha_creacion, fecha_cierre, created_at, updated_at
            FROM tickets
        """)
        
        # Drop
        cursor.execute("DROP TABLE tickets")
        
        # Recreate
        cursor.execute("""
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
                email_enviado INTEGER DEFAULT 0,
                FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE,
                UNIQUE(numero_ticket)
            )
        """)
        
        # Restore
        cursor.execute("""
            INSERT INTO tickets 
            (id, numero_ticket, ficha_id, numero_serie, estado, fecha_creacion, fecha_cierre, created_at, updated_at)
            SELECT id, numero_ticket, ficha_id, numero_serie, estado, fecha_creacion, fecha_cierre, created_at, updated_at
            FROM tickets_backup
        """)
        
        # Cleanup
        cursor.execute("DROP TABLE tickets_backup")
        
        print("  ✅ Tabla tickets recreada con todas las columnas")
        return True
    else:
        print("  ⏭️  Ya tiene todas las columnas necesarias")
        return False

def main():
    print("=" * 70)
    print("MIGRACIONES DE BASE DE DATOS - SISTEMA DML")
    print("=" * 70)
    
    try:
        db = sqlite3.connect('dml.db')
        db.row_factory = sqlite3.Row
        
        changes = []
        
        # Ejecutar migraciones
        if migrate_envios_repuestos(db):
            changes.append("envios_repuestos")
        
        if migrate_tickets(db):
            changes.append("tickets")
        
        # Commit
        db.commit()
        
        print("\n" + "=" * 70)
        if changes:
            print(f"✅ MIGRACIONES COMPLETADAS: {', '.join(changes)}")
        else:
            print("✅ BASE DE DATOS YA ESTÁ ACTUALIZADA")
        print("=" * 70)
        
        db.close()
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR EN MIGRACIÓN: {e}")
        import traceback
        traceback.print_exc()
        try:
            db.rollback()
            db.close()
        except:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
