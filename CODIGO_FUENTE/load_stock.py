#!/usr/bin/env python3
"""
Script para cargar stock desde Excel a la base de datos
"""
import os
import sqlite3

import openpyxl

DB_PATH = 'dml.db'
EXCEL_PATH = 'STOCK 26-05-25.xlsx'

def load_stock():
    print("=" * 70)
    print("CARGANDO STOCK DESDE EXCEL")
    print("=" * 70)
    
    # Read Excel
    if not os.path.exists(EXCEL_PATH):
        print(f"ERROR: {EXCEL_PATH} no encontrado")
        return
    
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb["Stock"]
    
    print(f"\nArchivo: {EXCEL_PATH}")
    print("Hoja: Stock")
    
    # Connect to DB
    conn = sqlite3.connect(DB_PATH)
    db = conn.cursor()
    
    # Insert data from Excel (starting at row 9)
    # Structure: Col B=CODIGO, Col C=ITEM, Col D=TOTAL (cantidad), Col F=UBICACION
    inserted = 0
    errors = 0
    
    for idx, row in enumerate(ws.iter_rows(min_row=9, values_only=True), 1):
        if not row or all(v is None for v in row):
            continue
        
        try:
            codigo = row[1]  # Column B
            item = row[2]    # Column C
            cantidad = row[3] # Column D (TOTAL)
            
            if not codigo or not item:
                continue
            
            # Clean cantidad
            if cantidad is None or cantidad == '':
                cantidad = 0
            elif isinstance(cantidad, str):
                cantidad_str = cantidad.strip().split()[0] if cantidad else '0'
                try:
                    cantidad = int(cantidad_str)
                except Exception:
                    cantidad = 0
            else:
                cantidad = int(cantidad)
            
            # Insert into stock_dml
            db.execute("""
                INSERT OR IGNORE INTO stock_dml 
                (codigo_repuesto, item, cantidad)
                VALUES (?, ?, ?)
            """, (str(codigo), str(item), cantidad))
            
            inserted += 1
            if idx % 25 == 0:
                print(f"  Procesando: {idx} registros...")
        
        except Exception as e:
            errors += 1
            print(f"  ERROR fila {idx}: {e}")
    
    conn.commit()
    
    # Verify
    result = db.execute("SELECT COUNT(*) FROM stock_dml").fetchone()[0]
    total_stock = result
    
    print("\n\nRESULTADO:")
    print(f"  Insertados exitosamente: {inserted}")
    print(f"  Errores: {errors}")
    print(f"  Total en BD: {total_stock}")
    
    conn.close()
    print("\nStock cargado correctamente!")

if __name__ == "__main__":
    load_stock()
