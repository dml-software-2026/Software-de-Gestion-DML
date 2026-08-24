#!/usr/bin/env python3
"""
Script para limpiar la base de datos y dejarla lista para pruebas.
Mantiene: usuarios y stock de repuestos.
Elimina: fichas, envíos, tickets, RAYPAC entries, logs, etc.
"""

import sqlite3
import sys


def limpiar_base_datos():
    """Limpia todos los datos excepto usuarios y stock"""
    
    conn = sqlite3.connect('dml.db')
    cursor = conn.cursor()
    
    print("=" * 60)
    print("LIMPIEZA DE BASE DE DATOS")
    print("=" * 60)
    print("\n🔒 MANTENIENDO:")
    print("   - Usuarios (users)")
    print("   - Stock de repuestos (matriz_repuestos, stock_ubicaciones)")
    
    print("\n🗑️  ELIMINANDO:")
    
    # Tablas a limpiar (en orden para respetar foreign keys)
    tablas_limpiar = [
        "ticket_historial",
        "audit_log", 
        "mail_log",
        "stock_alertas",
        "estadisticas_repuestos",
        "tickets",
        "dml_repuestos",
        "dml_partes",
        "dml_fichas",
        "envios_repuestos_detalles",
        "envios_repuestos",
        "freezing_log",
        "raypac_entries",
        "stock_dml"  # Legacy table
    ]
    
    total_eliminados = 0
    
    for tabla in tablas_limpiar:
        try:
            # Contar registros antes de eliminar
            count = cursor.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            
            if count > 0:
                cursor.execute(f"DELETE FROM {tabla}")
                print(f"   ✅ {tabla}: {count} registros eliminados")
                total_eliminados += count
            else:
                print(f"   ⚪ {tabla}: ya estaba vacía")
                
        except Exception as e:
            print(f"   ⚠️  {tabla}: {e}")
    
    conn.commit()
    
    print(f"\n📊 TOTAL ELIMINADO: {total_eliminados} registros")
    
    # Verificar lo que queda
    print("\n✅ MANTENIDO:")
    usuarios = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    repuestos = cursor.execute("SELECT COUNT(*) FROM matriz_repuestos").fetchone()[0]
    stock = cursor.execute("SELECT COUNT(*) FROM stock_ubicaciones").fetchone()[0]
    
    print(f"   - Usuarios: {usuarios}")
    print(f"   - Repuestos en matriz: {repuestos}")
    print(f"   - Stock ubicaciones: {stock}")
    
    print("\n" + "=" * 60)
    print("✅ BASE DE DATOS LIMPIA Y LISTA PARA PRUEBAS")
    print("=" * 60)
    
    conn.close()

if __name__ == "__main__":
    respuesta = input("\n⚠️  ¿Confirmas que deseas limpiar TODOS los datos de prueba? (s/n): ")
    
    if respuesta.lower() in ['s', 'si', 'y', 'yes']:
        print("\n⏳ Limpiando base de datos...\n")
        limpiar_base_datos()
        print("\n✅ ¡Listo! Ahora puedes hacer pruebas de flujo completo.")
    else:
        print("❌ Operación cancelada")
        sys.exit(0)
