import sqlite3

db = sqlite3.connect('dml.db')
cursor = db.cursor()

print("Agregando columnas faltantes a envios_repuestos...")

try:
    # Verificar columnas existentes
    columns = [col[1] for col in cursor.execute("PRAGMA table_info(envios_repuestos)").fetchall()]
    print(f"Columnas actuales: {', '.join(columns)}")
    
    if 'estado_envio' not in columns:
        cursor.execute("ALTER TABLE envios_repuestos ADD COLUMN estado_envio TEXT DEFAULT 'ENVIADO'")
        print("✅ Columna estado_envio agregada")
    else:
        print("⏭️  estado_envio ya existe")
    
    if 'is_frozen' not in columns:
        cursor.execute("ALTER TABLE envios_repuestos ADD COLUMN is_frozen INTEGER DEFAULT 1")
        print("✅ Columna is_frozen agregada")
    else:
        print("⏭️  is_frozen ya existe")
    
    if 'tipo_entrega' not in columns:
        cursor.execute("ALTER TABLE envios_repuestos ADD COLUMN tipo_entrega TEXT DEFAULT 'REPUESTOS'")
        print("✅ Columna tipo_entrega agregada")
    else:
        print("⏭️  tipo_entrega ya existe")
    
    db.commit()
    print("\n✅ Migración completada")
    
    # Mostrar columnas finales
    columns_final = [col[1] for col in cursor.execute("PRAGMA table_info(envios_repuestos)").fetchall()]
    print(f"Columnas finales: {', '.join(columns_final)}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
finally:
    db.close()
