#!/usr/bin/env python3
"""Script para verificar credenciales de login"""

import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

conn = sqlite3.connect('dml.db')
cursor = conn.cursor()

print("=" * 60)
print("VERIFICACIÓN DE USUARIOS Y CONTRASEÑAS")
print("=" * 60)

usuarios_test = [
    ('admin@dml.local', 'admin'),
    ('raypac@dml.local', 'raypac'),
    ('st@dml.local', 'tecnico'),
    ('repuestos@dml.local', 'repuestos'),
]

for email, password in usuarios_test:
    user = cursor.execute('SELECT id, email, password_hash, role FROM users WHERE email = ?', (email,)).fetchone()
    
    if user:
        user_id, user_email, hash_db, role = user
        es_valido = check_password_hash(hash_db, password)
        
        print(f"\n📧 {email}")
        print(f"   ID: {user_id} | Role: {role}")
        print(f"   Password '{password}': {'✅ CORRECTO' if es_valido else '❌ INCORRECTO'}")
        print(f"   Hash (primeros 50): {hash_db[:50]}...")
    else:
        print(f"\n❌ Usuario {email} NO EXISTE en BD")

print("\n" + "=" * 60)
print("REGENERANDO HASHES CORRECTOS")
print("=" * 60)

for email, password in usuarios_test:
    nuevo_hash = generate_password_hash(password)
    print(f"\n{email} -> {password}")
    print(f"Hash: {nuevo_hash[:80]}...")

conn.close()
