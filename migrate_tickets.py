import sqlite3

db = sqlite3.connect('dml.db')
cursor = db.cursor()

print("Ejecutando migración de tabla tickets...")

try:
    # Verificar columnas existentes
    columns = [col[1] for col in cursor.execute("PRAGMA table_info(tickets)").fetchall()]
    print(f"Columnas actuales: {', '.join(columns)}")
    
    if 'tecnico_responsable' not in columns:
        print("\n⚠️  La tabla tickets necesita recrearse con todas las columnas")
        
        # Crear backup
        cursor.execute("""
            CREATE TABLE tickets_backup AS 
            SELECT id, numero_ticket, ficha_id, numero_serie, estado, 
                   fecha_creacion, fecha_cierre, created_at, updated_at
            FROM tickets
        """)
        print("✅ Backup creado")
        
        # Eliminar tabla original
        cursor.execute("DROP TABLE tickets")
        print("✅ Tabla original eliminada")
        
        # Recrear tabla con todas las columnas
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
        print("✅ Tabla recreada con todas las columnas")
        
        # Restaurar datos (agregando raypac_id)
        cursor.execute("""
            INSERT INTO tickets 
            (id, numero_ticket, ficha_id, numero_serie, estado, fecha_creacion, fecha_cierre, created_at, updated_at)
            SELECT id, numero_ticket, ficha_id, numero_serie, estado, fecha_creacion, fecha_cierre, created_at, updated_at
            FROM tickets_backup
        """)
        print("✅ Datos restaurados")
        
        # Eliminar backup
        cursor.execute("DROP TABLE tickets_backup")
        print("✅ Backup eliminado")
        
        db.commit()
        print("\n✅ Migración completada exitosamente")
        
        # Mostrar columnas finales
        columns_final = [col[1] for col in cursor.execute("PRAGMA table_info(tickets)").fetchall()]
        print(f"Columnas finales: {', '.join(columns_final)}")
    else:
        print("⏭️  La tabla ya tiene todas las columnas necesarias")
    
except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
    import traceback
    traceback.print_exc()
finally:
    db.close()
