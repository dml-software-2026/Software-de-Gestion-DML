# Migración SQLite → PostgreSQL (Supabase)

**Proyecto:** CodigoA / Software-de-Gestion-DML
**Rama:** `feat/95-modificar-postgresql`
**Fecha:** Agosto 2026

Este documento registra los cambios realizados para migrar el backend de
SQLite a PostgreSQL (Supabase), los bugs encontrados en producción durante
las pruebas, y las causas raíz. Sirve como referencia para el equipo y para
detectar patrones repetidos si aparecen errores similares en archivos
todavía no migrados.

---

## 1. Alcance de la migración

Se migraron de sintaxis SQLite (`sqlite3`) a PostgreSQL (`psycopg2`) los
siguientes archivos:

- `CODIGO_FUENTE/extensions.py` — conexión (`get_db`, `close_db`,
  `migrate_db`, `init_db`)
- `CODIGO_FUENTE/decorators.py`
- `CODIGO_FUENTE/blueprints/raypac.py`
- `CODIGO_FUENTE/blueprints/stock.py`
- `CODIGO_FUENTE/blueprints/tickets.py`
- `CODIGO_FUENTE/blueprints/auth.py`
- `CODIGO_FUENTE/blueprints/dml.py`
- `CODIGO_FUENTE/blueprints/envios.py`
- `CODIGO_FUENTE/blueprints/admin.py`
- `CODIGO_FUENTE/blueprints/api.py`
- `CODIGO_FUENTE/blueprints/estadisticas.py`
- `CODIGO_FUENTE/services/seed.py`
- `CODIGO_FUENTE/services/stock.py`

El schema vive en `db/schema-postgres.sql` y ya fue aplicado manualmente en
el SQL Editor de Supabase. El `schema.sql` viejo (SQLite) sigue en el repo
como referencia histórica muerta, pero **nada en el código lo ejecuta**.

---

## 2. Patrones de bug encontrados (para reconocer en archivos pendientes)

### 2.1 Placeholders `?` → `%s`
SQLite usa `?`, psycopg2 usa `%s`. Aparece en prácticamente todos los
`db.execute(...)` del código heredado.

### 2.2 `last_insert_rowid()` → `INSERT ... RETURNING id`
SQLite devuelve el último id insertado con una función global. En Postgres
no existe: hay que pedirlo con `RETURNING id` en el mismo `INSERT`.

### 2.3 `INSERT OR IGNORE` → `INSERT ... ON CONFLICT (...) DO NOTHING`
Requiere que la columna tenga `UNIQUE` para que el `ON CONFLICT` funcione.

### 2.4 Booleans: `1`/`0` → `TRUE`/`FALSE`
Columnas que en SQLite eran `INTEGER 0/1` (ej. `is_frozen`, `is_closed`,
`is_active`) ahora son `BOOLEAN` real en Postgres. Comparaciones/asignaciones
con `1`/`0` fallan o, en el caso de aritmética (`1 - valor`), tiran
`TypeError`. Se reemplaza por `TRUE`/`FALSE` o, para toggles, por `not valor`.

Ojo: no todas las columnas que "suenan" booleanas lo son — `en_stock`,
`en_falta`, `ficha_generada`, `ticket_enviado` siguen siendo `INTEGER` en el
schema, así que ahí se mantiene `1`/`0`.

### 2.5 `PRAGMA table_info(tabla)` → `information_schema.columns`
No existe `PRAGMA` en Postgres. Se reemplaza por una consulta a
`information_schema.columns WHERE table_name = %s`.

### 2.6 Transacciones abortadas sin `rollback()`
El más insidioso. En Postgres, si una query falla dentro de una
transacción, la conexión completa queda bloqueada
(`current transaction is aborted, commands ignored until end of
transaction block`) hasta que se haga `db.rollback()`. El código heredado
tiene muchos `except Exception as e: flash(...)` que **no** hacen
`rollback()`, lo que provoca que la *siguiente* query en esa misma request
(a veces algo tan inocente como levantar el usuario logueado para el menú)
también falle, aunque no tenga nada que ver con el error original.

**Regla general aplicada:** todo `except` que atrape un error de
`db.execute(...)` debe empezar con `db.rollback()`.

### 2.7 El wrapper `db.execute()` y el `%` literal en `LIKE`
Bug de fondo en `extensions.py`. El wrapper `PgConnection.execute()` hacía:
```python
cur.execute(query, params or ())
```
Si no se pasaban parámetros, `None or ()` daba `()` (tupla vacía), lo cual
activa el modo de sustitución de placeholders de psycopg2 igual. Cualquier
query con un `%` literal sin intención de placeholder (ej. `LIKE
'%ENTREGAD%'`) rompía con `IndexError: tuple index out of range`.

**Fix (impacto en todo el sistema, una sola línea):**
```python
cur.execute(query, params)  # None se pasa tal cual, sin forzar sustitución
```

### 2.8 Tipos numéricos estrictos
SQLite es de tipado débil: aceptaba texto como `"NO APLICA"` en una columna
declarada `INTEGER`/`REAL` sin quejarse. Postgres es estricto: tira
`invalid input syntax for type real/integer`. Se agregó conversión
defensiva antes de cada `UPDATE`/`INSERT` en campos como `n_ciclos` y
`horas_adic`:
```python
try:
    horas = float(horas_raw) if horas_raw else None
except ValueError:
    horas = None
```

### 2.9 Fechas: `TEXT` → tipos reales (`DATE`/`TIMESTAMPTZ`)
En SQLite las fechas se guardaban como texto, así que templates hacían
`fecha[:10]` para cortar el string. En Postgres son objetos `datetime`/
`date` reales — no son "recortables" con `[:10]`. Se reemplaza en los
templates por `fecha.strftime('%Y-%m-%d')`.

También aparece al **combinar en Python** listas que mezclan `datetime`
(de columnas `TIMESTAMPTZ`) con `date` (de columnas `DATE`), y comparar
tz-aware con tz-naive — ambos casos tiran `TypeError` al hacer `.sort()`.
Requiere una función de normalización (`_sort_key`) que homogeneice todo a
un mismo tipo con timezone antes de ordenar.

### 2.10 Nombres de tabla/columna que cambiaron en el schema nuevo
`audit_log` (SQLite) → `logs_auditoria` (Postgres), con columnas renombradas
(`user_id`→`id_usuario`, `table_name`→`tabla_afectada`, etc.) y un `CHECK`
que solo permite `tipo_accion IN ('INSERT','UPDATE','DELETE')`. El código
llamaba a `log_action()` con valores como `"CREATE"`, `"FREEZE"`,
`"TOGGLE"` — se mapean a uno de los 3 valores permitidos, conservando la
acción real dentro de `new_value` para no perder el detalle.

### 2.11 Columnas faltantes en el schema nuevo
`raypac_entries.numero_correlativo` se usaba en el código pero no estaba en
`schema-postgres.sql` ni se agregaba vía `migrate_db()`. Se agregó a mano
en Supabase:
```sql
ALTER TABLE raypac_entries ADD COLUMN numero_correlativo INTEGER;
```

### 2.12 Performance: inserts en loop vs. batch
`services/seed.py` cargaba ~247 repuestos del CSV con 2 `INSERT`
individuales por fila (~494 round-trips a Supabase), lo que superaba el
timeout de 30s de Gunicorn y tumbaba el arranque del server. Se reemplazó
por `psycopg2.extras.execute_values`, agrupando todo en 2 inserts masivos.

---

## 3. Estado del `schema.sql` viejo (SQLite)

- `init_db()` ya **no** lee ni ejecuta `CODIGO_FUENTE/schema.sql`.
- El schema real vive en `db/schema-postgres.sql` y ya está aplicado en
  Supabase.
- `migrate_db()` ya no crea tablas (se sacaron los `CREATE TABLE IF NOT
  EXISTS` redundantes) — solo aplica `ALTER TABLE ADD COLUMN IF NOT
  EXISTS` para columnas incrementales que todavía no están en el schema
  base.
- **Pendiente de decisión del equipo:** borrar `CODIGO_FUENTE/schema.sql`
  del repo o dejarlo como referencia histórica muerta. Cualquiera de las
  dos opciones es válida; lo importante es que sea una decisión consciente.

---

## 4. Checklist de verificación funcional (ya completado ✅)

- [x] Login con los 4 roles (ADMIN, RAYPAC, DML_ST, DML_REPUESTOS)
- [x] Dashboard carga sin error para cada rol
- [x] Flujo completo: RAYPAC → freeze → ticket → ficha DML → cierre
- [x] Stock: listado, alta, edición, baja
- [x] Envíos: creación y recepción
- [x] Admin: alta/edición/activación de usuarios
- [x] Estadísticas y exportaciones CSV

---

## 5. Deuda técnica NO tocada en esta migración (a propósito)

Estos bugs/deficiencias ya existían antes de tocar nada de Postgres y se
dejaron igual para no mezclar cambios de comportamiento con la migración:

- Contraseñas de administración hardcodeadas (`"ADMIN2024"`) repetidas en
  5 lugares distintos del código.
- `/admin/cargar-stock-csv` sin decorador de autenticación.
- `blueprints/api.py::verificar_stock_api` — variable `db` sin definir,
  consulta una tabla `stock_repuestos` inexistente. Parece no usarse en
  producción; queda pendiente confirmar y eliminar o reescribir.
- Código de desbloqueo hardcodeado para descongelar registros.

---

## 6. Próximos pasos sugeridos

- Revisar `services/numeracion.py` y `services/pdf.py`, todavía no
  auditados por si tienen los mismos patrones de esta lista.
- Revisar los scripts de `scripts/*.py` (no bloquean el uso normal de la
  app, pero fallarán si se ejecutan manualmente sin la conversión).
- Decidir sobre el `schema.sql` viejo (ver sección 3).
- Centralizar las contraseñas hardcodeadas en variables de entorno
  (Épica 2, ya trackeada en el Kanban).