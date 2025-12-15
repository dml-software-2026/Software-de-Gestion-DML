# 📧 PRUEBAS DE ALERTAS POR EMAIL - SISTEMA DML

## ✅ Estado Actual: SMTP Configurado y Funcionando

- **Email configurado:** sistemadegestiondml@gmail.com
- **Servidor SMTP:** Gmail (smtp.gmail.com:587)
- **Estado:** ✅ Email de prueba enviado correctamente

---

## 📋 ALERTAS IMPLEMENTADAS (Según Documento David)

### 1. 🎫 **Ticket de Seguimiento** → Al Comercial RAYPAC
**Cuándo se dispara:**
- Al crear un ticket desde un ingreso RAYPAC
- O al crear una ficha DML con ticket asociado

**A quién se envía:**
- Al campo `mail_comercial` del ingreso RAYPAC

**Cómo probarlo con un solo email:**
1. Crear ingreso RAYPAC con `sistemadegestiondml@gmail.com` en el campo de email comercial
2. Freezar el ingreso con un remito
3. DML recibe el equipo y crea el ticket
4. ✅ Deberías recibir email con el número de ticket

**Código:** Líneas 1841-1844 y 2408-2411 en app.py

---

### 2. 📦 **Máquina Lista para Retirar** → Al Comercial RAYPAC
**Cuándo se dispara:**
- Al cerrar una ficha DML (poner estado "MÁQUINA ENTREGADA")
- O al generar el PDF de la ficha final

**A quién se envía:**
- Al campo `mail_comercial` del ingreso RAYPAC asociado

**Cómo probarlo con un solo email:**
1. Usar la misma ficha del punto anterior
2. Cambiar estado a "MÁQUINA ENTREGADA"
3. Cerrar la ficha
4. ✅ Deberías recibir email "Máquina Lista: Ficha #XXXXXX"

**Código:** Líneas 2534-2537 y 3547-3550 en app.py

---

### 3. ✅ **Confirmación de Recepción de Repuestos** → A RAYPAC
**Cuándo se dispara:**
- Cuando DML confirma recepción de un envío de repuestos

**A quién se envía:**
- **PROBLEMA DETECTADO:** Actualmente envía a `raypac@dml.local` (email hardcodeado)
- **Solución necesaria:** Cambiar a email configurable

**Cómo probarlo con un solo email:**
1. ⚠️ REQUIERE CORRECCIÓN primero (ver sección "Correcciones Necesarias")
2. RAYPAC crea envío de repuestos con remito
3. DML recibe y confirma el envío
4. ✅ Deberías recibir confirmación con detalle de repuestos

**Código:** Línea 2943 en app.py

---

### 4. 🔔 **Alertas de Stock Bajo** → A Responsable de Repuestos
**Niveles de alerta:**
- 🟠 NARANJA: 2 repuestos disponibles
- 🟡 AMARILLO: 1 repuesto disponible (último)
- 🔴 ROJO: 0 repuestos (agotado)

**Cuándo se disparan:**
- Cuando se usa un repuesto en una ficha y el stock llega a 2, 1 o 0

**A quién se envía:**
- **PROBLEMA DETECTADO:** Actualmente envía a `repuestos@dml.local` (email hardcodeado)
- **Solución necesaria:** Cambiar a email configurable

**Cómo probarlo con un solo email:**
1. ⚠️ REQUIERE CORRECCIÓN primero (ver sección "Correcciones Necesarias")
2. Crear un repuesto con cantidad inicial = 2
3. Usar ese repuesto en una ficha (quedará en 1)
4. ✅ Deberías recibir alerta AMARILLO
5. Usar nuevamente (quedará en 0)
6. ✅ Deberías recibir alerta ROJO

**Código:** Líneas 955-974 en app.py

---

## ⚠️ CORRECCIONES NECESARIAS

### Problema 1: Emails Hardcodeados
Actualmente hay 2 emails que no se pueden configurar:
- `raypac@dml.local` → Para confirmación de recepción de repuestos
- `repuestos@dml.local` → Para alertas de stock

### Solución: Agregar Emails a Usuarios del Sistema
Necesitamos:
1. Agregar campo `email` a la tabla `users`
2. Cambiar los destinatarios hardcodeados por emails de usuarios con roles específicos:
   - Alertas de stock → A usuarios con rol `DML_REPUESTOS`
   - Confirmación repuestos → A usuarios con rol `RAYPAC`

---

## 🧪 PLAN DE PRUEBAS COMPLETO

### Preparación (Hacer esto en Render después de configurar SMTP):

**Paso 1:** Configurar usuarios con email
- Ir a "Gestión de Usuarios"
- Editar usuario RAYPAC → Agregar email `sistemadegestiondml@gmail.com`
- Editar usuario DML_REPUESTOS → Agregar email `sistemadegestiondml@gmail.com`

**Paso 2:** Crear datos de prueba
1. Ingreso RAYPAC con email comercial: `sistemadegestiondml@gmail.com`
2. Repuesto con cantidad = 2 en stock

### Ejecución de Pruebas:

**✅ Prueba 1: Ticket de Seguimiento**
1. Freezar ingreso RAYPAC con remito
2. DML recibe y crea ticket
3. Verificar email recibido con número de ticket

**✅ Prueba 2: Máquina Lista**
1. Completar reparación de la ficha anterior
2. Poner estado "MÁQUINA ENTREGADA"
3. Cerrar ficha
4. Verificar email "Máquina Lista"

**⚠️ Prueba 3: Recepción Repuestos** (requiere corrección primero)
1. RAYPAC crea envío de repuestos
2. Freezar con remito
3. DML confirma recepción
4. Verificar email de confirmación

**⚠️ Prueba 4: Alertas Stock** (requiere corrección primero)
1. Usar repuesto en ficha (stock pasa de 2 a 1)
2. Verificar alerta AMARILLO
3. Usar mismo repuesto otra vez (stock pasa de 1 a 0)
4. Verificar alerta ROJO

---

## 🔧 SIGUIENTES PASOS RECOMENDADOS

1. **Ahora mismo:** Configurar variables SMTP en Render con datos de Gmail
2. **Probar:** Alertas 1 y 2 (ya funcionan 100%)
3. **Corregir código:** Emails hardcodeados (alertas 3 y 4)
4. **Probar:** Alertas 3 y 4 después de corrección
5. **Opcional:** Agregar campo email a usuarios para mejor control

---

## 📝 RESUMEN DE COMPATIBILIDAD CON DOCUMENTO DAVID

| Requisito David | Estado | Observaciones |
|----------------|--------|---------------|
| Ticket de seguimiento → Comercial | ✅ Implementado | Listo para probar |
| Máquina lista → Comercial | ✅ Implementado | Listo para probar |
| Confirmación recepción repuestos | ⚠️ Parcial | Email hardcodeado, requiere corrección |
| Alertas stock (NARANJA/AMARILLO/ROJO) | ⚠️ Parcial | Email hardcodeado, requiere corrección |

**Estado general:** 2 de 4 alertas listas (50%), 2 requieren pequeña corrección
