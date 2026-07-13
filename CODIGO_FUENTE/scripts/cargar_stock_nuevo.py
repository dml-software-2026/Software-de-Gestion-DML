#!/usr/bin/env python3
"""
Script para cargar el stock completo desde el archivo CSV de David
Archivo: Copia de NUEVO STOCK DE REPUESTOS COMPLETO.csv
Columnas: C=CODIGO, D=ITEM, E=TOTAL, J=CODIGO DE UBICACION
"""

import csv
import sqlite3
import sys
import os

# Determinar la ruta de la base de datos

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.join(BASE_DIR, "..")  # Directorio raíz del proyecto

CSV_PATH = os.path.join(BASE_DIR, "DOCUMENTOS DML", "Copia de NUEVO STOCK DE REPUESTOS COMPLETO.csv")

def cargar_stock_desde_csv():
    """Carga el stock completo desde el CSV a la base de datos"""
    
    if not os.path.exists(CSV_PATH):
        print(f"❌ ERROR: No se encontró el archivo CSV en: {CSV_PATH}")
        return False
    
    if not os.path.exists(DB_PATH):
        print(f"❌ ERROR: No se encontró la base de datos en: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Activar foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")
    
    repuestos_cargados = 0
    repuestos_actualizados = 0
    errores = []
    
    print(f"📖 Leyendo archivo: {CSV_PATH}")
    print("=" * 80)
    
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            
            # Saltar las primeras 4 filas (encabezados)
            for _ in range(4):
                next(reader, None)
            
            for idx, row in enumerate(reader, start=1):
                if len(row) < 11:
                    continue
                
                # Extraer datos (columnas 0-indexed)
                tipo_maquina = row[1].strip() if len(row) > 1 and row[1] else "Bateria"
                codigo = row[2].strip() if len(row) > 2 and row[2] else None
                item = row[3].strip() if len(row) > 3 and row[3] else None
                cantidad_str = row[4].strip() if len(row) > 4 and row[4] else "0"
                codigo_ubicacion = row[9].strip() if len(row) > 9 and row[9] else "SIN UBICACIÓN"
                
                # Validaciones
                if not codigo or not item:
                    continue
                
                # Limpiar y convertir cantidad
                try:
                    cantidad = int(cantidad_str) if cantidad_str else 0
                except ValueError:
                    print(f"⚠️  Fila {idx}: Cantidad inválida '{cantidad_str}' para código {codigo}")
                    cantidad = 0
                
                # 1. Insertar o actualizar en matriz_repuestos
                cursor.execute("""
                    SELECT id FROM matriz_repuestos WHERE codigo_repuesto = ?
                """, (codigo,))
                
                existe_matriz = cursor.fetchone()
                
                if not existe_matriz:
                    # Generar número correlativo (usar el índice actual + 1)
                    numero_correlativo = idx + 1
                    cursor.execute("""
                        INSERT INTO matriz_repuestos (numero, codigo_repuesto, item, cantidad_inicial, cantidad_actual, ubicacion)
                        VALUES (?, ?, ?, ?, ?, 'DML')
                    """, (numero_correlativo, codigo, item, cantidad, cantidad))
                    repuestos_cargados += 1
                else:
                    cursor.execute("""
                        UPDATE matriz_repuestos 
                        SET item = ?, cantidad_actual = ?
                        WHERE codigo_repuesto = ?
                    """, (item, cantidad, codigo))
                    repuestos_actualizados += 1
                
                # 2. Insertar o actualizar en stock_ubicaciones (ubicación DML)
                cursor.execute("""
                    SELECT id FROM stock_ubicaciones 
                    WHERE codigo_repuesto = ? AND ubicacion = 'DML'
                """, (codigo,))
                
                existe_stock = cursor.fetchone()
                
                if not existe_stock:
                    cursor.execute("""
                        INSERT INTO stock_ubicaciones 
                        (codigo_repuesto, ubicacion, cantidad, codigo_ubicacion_fisica)
                        VALUES (?, 'DML', ?, ?)
                    """, (codigo, cantidad, codigo_ubicacion))
                else:
                    cursor.execute("""
                        UPDATE stock_ubicaciones 
                        SET cantidad = ?, codigo_ubicacion_fisica = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE codigo_repuesto = ? AND ubicacion = 'DML'
                    """, (cantidad, codigo_ubicacion, codigo))
                
                if idx % 50 == 0:
                    print(f"✅ Procesadas {idx} filas...")
                    conn.commit()
        
        # Commit final
        conn.commit()
        
        print("=" * 80)
        print(f"✅ ¡Stock cargado exitosamente!")
        print(f"   📦 Repuestos nuevos: {repuestos_cargados}")
        print(f"   🔄 Repuestos actualizados: {repuestos_actualizados}")
        print(f"   📊 Total procesado: {repuestos_cargados + repuestos_actualizados}")
        
        if errores:
            print(f"\n⚠️  Errores encontrados: {len(errores)}")
            for error in errores[:10]:  # Mostrar solo los primeros 10
                print(f"   - {error}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ ERROR al cargar stock: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Cargador de Stock DML")
    print("📄 Archivo: Copia de NUEVO STOCK DE REPUESTOS COMPLETO.csv")
    print()
    
    respuesta = input("¿Desea continuar con la carga? (s/n): ")
    
    if respuesta.lower() in ['s', 'si', 'y', 'yes']:
        print("\n⏳ Cargando stock...\n")
        if cargar_stock_desde_csv():
            print("\n✅ ¡Proceso completado!")
        else:
            print("\n❌ Proceso finalizado con errores")
            sys.exit(1)
    else:
        print("❌ Operación cancelada")
        sys.exit(0)
