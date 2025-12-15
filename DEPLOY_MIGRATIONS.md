# 🚀 INSTRUCCIONES DE DEPLOY - CORRECCIONES CRÍTICAS

## ⚠️ IMPORTANTE: Migraciones de Base de Datos Requeridas

Este deploy incluye cambios en el esquema de base de datos que **DEBEN** ejecutarse en producción.

---

## 📋 Errores Corregidos en Este Deploy

1. **Error agregar repuesto RAYPAC**: `NOT NULL constraint failed: matriz_repuestos.cantidad_inicial`
   - ✅ Corregido: INSERT ahora incluye todos los campos obligatorios

2. **Internal Server Error en dashboard técnico**: Después de crear ticket
   - ✅ Corregido: Query usa columnas correctas (`estado_envio` agregado a tabla)

3. **Técnico no puede recepcionar envíos**: Solo podía ver pero no confirmar
   - ✅ Corregido: Permisos ya estaban bien, faltaban columnas en BD

4. **Error crear ficha aunque complete campos**: Validación fallaba siempre
   - ✅ Corregido: Tabla `tickets` recreada con columna `tecnico_responsable`

---

## 🔧 PASOS PARA DEPLOY EN RENDER

### 1. Push de Código (Ya Hecho)
```bash
git add .
git commit -m "Fix: 4 errores críticos"
git push origin main
```

### 2. Esperar Redespliegue Automático
- Render detectará el push y empezará a redesplegar
- Esperar 2-3 minutos hasta que termine

### 3. ⚠️ EJECUTAR MIGRACIONES (CRÍTICO)

**Opción A: Desde Shell de Render (Recomendado)**
```bash
# 1. En Render Dashboard, ir a tu servicio
# 2. Click en "Shell" en el menú lateral
# 3. Ejecutar:
python run_migrations.py
```

**Opción B: Conectarse por SSH (Si está habilitado)**
```bash
ssh <tu-servicio>.onrender.com
cd /app
python run_migrations.py
```

**Salida Esperada:**
```
======================================================================
MIGRACIONES DE BASE DE DATOS - SISTEMA DML
======================================================================

[1/2] Migrando envios_repuestos...
  ✅ Columna estado_envio agregada
  ✅ Columna is_frozen agregada
  ✅ Columna tipo_entrega agregada

[2/2] Migrando tickets...
  ⚠️  Recreando tabla con todas las columnas...
  ✅ Tabla tickets recreada con todas las columnas

======================================================================
✅ MIGRACIONES COMPLETADAS: envios_repuestos, tickets
======================================================================
```

### 4. Verificar Funcionamiento

**Prueba 1: Agregar Repuesto RAYPAC**
- Login como RAYPAC
- Ir a Stock → Agregar Repuesto
- Completar código e item
- ✅ Debería crearse sin error

**Prueba 2: Dashboard Técnico**
- Login como DML_ST
- Ir a Inicio (después de tener al menos 1 ticket creado)
- ✅ NO debería dar Internal Server Error

**Prueba 3: Recepcionar Envíos**
- Login como RAYPAC → Crear envío de repuestos → Freezar con remito
- Login como DML_ST → Ir a Envíos
- ✅ Debería ver botón "Dar Ingreso en DML"
- Click en botón → ✅ Debería recepcionar correctamente

**Prueba 4: Crear Ficha**
- Login como RAYPAC → Crear ingreso → Freezar
- Login como DML_ST → Crear ticket
- Crear ficha desde ticket
- ✅ Debería crearse sin pedir completar campos faltantes

---

## 📧 CONFIGURACIÓN SMTP (Si No Está Hecha)

En Render → Environment Variables, agregar:

```
MAIL_SERVER = smtp.gmail.com
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = sistemadegestiondml@gmail.com
MAIL_PASSWORD = owpslkppjowoqlme
MAIL_DEFAULT_SENDER = Sistema DML <sistemadegestiondml@gmail.com>
```

Después de agregar, Render redesplegará automáticamente.

---

## 🔍 Verificación de Migraciones Ejecutadas

Para verificar que las migraciones se ejecutaron correctamente en producción:

```bash
python -c "import sqlite3; db = sqlite3.connect('dml.db'); print('Columnas envios_repuestos:'); print([c[1] for c in db.execute('PRAGMA table_info(envios_repuestos)').fetchall()]); print('\nColumnas tickets:'); print([c[1] for c in db.execute('PRAGMA table_info(tickets)').fetchall()])"
```

**Resultado esperado:**
- `envios_repuestos` debe tener: `estado_envio`, `is_frozen`, `tipo_entrega`
- `tickets` debe tener: `tecnico_responsable`, `fecha_ingreso`, `observaciones`, etc. (25 columnas total)

---

## ⚠️ IMPORTANTE

**NO SALTAR EL PASO 3 (Migraciones)**

Si el sistema se despliega sin ejecutar las migraciones, los errores seguirán ocurriendo porque la base de datos no tiene las columnas necesarias.

---

## 📝 Archivos de Migración Incluidos

- `run_migrations.py` - Script consolidado con todas las migraciones
- `migrate_envios.py` - Migración específica para envios_repuestos (referencia)
- `migrate_tickets.py` - Migración específica para tickets (referencia)

---

## ✅ Checklist de Deploy

- [x] Código pusheado a GitHub
- [ ] Redespliegue automático completado en Render
- [ ] Migraciones ejecutadas (`run_migrations.py`)
- [ ] Prueba 1 (Agregar repuesto) ✅
- [ ] Prueba 2 (Dashboard técnico) ✅
- [ ] Prueba 3 (Recepcionar envíos) ✅
- [ ] Prueba 4 (Crear ficha) ✅
- [ ] Variables SMTP configuradas (si no estaban)
- [ ] Enviar email de prueba

---

**Última actualización:** 15/12/2025
**Commits incluidos:** 69d36ad
