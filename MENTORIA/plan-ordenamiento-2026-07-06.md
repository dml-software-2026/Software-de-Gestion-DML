# Plan de ordenamiento — Sprint 2026-07-06

**Autor:** Matias Coca (mentor)
**Sprint:** 2026-07-06 → 2026-07-20

## Objetivo

Al cierre del sprint:
- [ ] `dev` nivelada con `main`
- [ ] Refactor #75 mergeado a `main`
- [ ] Proyecto Supabase creado con schema PostgreSQL corriendo
- [ ] `DATABASE_URL` configurada en Render
- [ ] Issues #64 y #65 cerrados
- [ ] Kanban ordenado (sin duplicados, sin épicas vacías)

Restricción: **nadie toca `CODIGO_FUENTE/app.py` excepto Facu.**

---

## Facu — Refactor #75 (XL, ~15-18h)

### Blueprints faltantes
Un blueprint es un módulo de Flask que agrupa rutas por dominio (ver `blueprints/auth.py` y `blueprints/raypac.py` como referencia).

- [x] `blueprints/dml.py` — `/dml/*` (fichas, partes, repuestos)
- [x] `blueprints/tickets.py` — `/tickets`, `/ticket/*`
- [x] `blueprints/envios.py` — `/envios/*`
- [x] `blueprints/stock.py` — `/stock/*`
- [x] `blueprints/admin.py` — `/admin` (ABM usuarios, carga stock)
- [x] `blueprints/estadisticas.py` — dashboard + exports
- [x] `blueprints/api.py` — `/api/*`

### Cierre del refactor
- [x] `app.py` nuevo chico: crea Flask app, registra los 9 blueprints, hook `apply_migrations`
- [x] Reemplazar el monolito por el nuevo `app.py`
- [x] Tag `pre-refactor-monolito` antes del PR (red de seguridad)
- [x] PR contra `main` + merge con squash

### Flujo integral a probar (5 veces seguidas sin HTTP 500)

#### Prerequisitos (scripts que este sprint se mueven a `scripts/`)

Facu necesita estos scripts para el testing. **Seba los mueve a `scripts/` como parte de su reestructura DB** (ver sección de Seba). Confirmar que existen antes de arrancar:

- `scripts/seed_data_minimal.py` (deja 4 usuarios + 10 repuestos con stock configurado con alertas).
- `scripts/limpiar_bd.py` (por si querés resetear entre sesiones).

Si alguno no está: parar, avisar en el daily, no seguir hasta resolverlo.

**Cuándo testear:** después de rebasear tu rama contra `dev` actualizado. Así tu working tree ya tiene la carpeta `scripts/` mergeada del PR de Seba.

#### Setup una vez (antes de las 5 corridas)

1. Levantar el server local:
   ```
   python CODIGO_FUENTE/app.py
   ```
2. Cargar seed inicial:
   ```
   python scripts/seed_data_minimal.py
   ```
3. Abrir el navegador en `http://127.0.0.1:5000`.
4. Abrir **DevTools (F12) → tab Network → tildar "Preserve log"**. Es el detector principal de HTTP 500.
5. Mantener a la vista la terminal donde corre `app.py`. Los tracebacks aparecen ahí.
6. Abrir un cliente de SQLite (SQLite Browser, DBeaver, o `sqlite3 dml.db` en terminal) para verificar cambios en la DB.

#### Los 9 pasos del flujo (una corrida)

1. Login como **RAYPAC** → ingreso de equipo con formulario completo → guardar.
2. **Asignar número de remito** → freezar el ingreso → verificar que desaparece de "pendientes RAYPAC" y aparece en "pendientes DML".
3. Login como **DML_ST** → recibir equipo → cargar fecha ingreso y técnico responsable → completar checklist de partes.
4. **Generar ticket** con ID correlativo → consultar el ticket por número + serie desde ventana de incógnito.
5. **Editar ficha:** observaciones, diagnóstico de reparación, mecanizado, horas adicionales, ciclos, remito de salida.
6. **Agregar 2-3 repuestos** a la ficha → verificar en la UI que el stock DML se descuenta automáticamente.
7. **Cambiar estado a "Lista para entregar"** → botón finalizar → verificar que la ficha queda freezada.
8. **Descargar el PDF** de la ficha.
9. Verificar que **llegó email** al comercial responsable (con el `test_email.py` verificás el SMTP aparte si hace falta).

#### Datos distintos por corrida (para no colisionar con constraints UNIQUE)

| Corrida | Cliente | Número de serie | Comercial | Remito (últimos 4 dígitos) |
|---|---|---|---|---|
| 1 | Test Alpha | TEST-001 | María González | 1001 |
| 2 | Test Beta | TEST-002 | Pedro Martínez | 1002 |
| 3 | Test Gamma | TEST-003 | Ana Rodríguez | 1003 |
| 4 | Test Delta | TEST-004 | Luis Fernández | 1004 |
| 5 | Test Epsilon | TEST-005 | Sofía López | 1005 |

Sin necesidad de resetear la BD entre corridas: los IDs son únicos por corrida. Si querés limpiar para arrancar de cero, corré `python scripts/limpiar_bd.py` (preserva usuarios y matriz de stock).

#### Verificación en la DB por cada paso

Cliqueé el botón ≠ funcionó. Verificá contra la DB cada paso:

| Paso | Qué debería aparecer en la DB |
|---|---|
| 1. Ingreso RAYPAC | 1 fila nueva en `raypac_entries` con `is_frozen=0` |
| 2. Freeze con remito | Esa fila ahora con `is_frozen=1` y `numero_remito` cargado |
| 3. Recepción DML + partes | 1 fila nueva en `dml_fichas` + 12 filas nuevas en `dml_partes` |
| 4. Generar ticket | 1 fila nueva en `tickets` con `estado='ACTIVO'` |
| 5. Editar ficha | Campos `diagnostico_reparacion`, `n_ciclos`, `horas_adic`, `numero_remito_salida` actualizados |
| 6. Agregar repuestos | Filas nuevas en `dml_repuestos` + `cantidad` decreció en `stock_ubicaciones` para ubicación DML |
| 7. Cerrar ficha | Esa fila de `dml_fichas` ahora con `is_closed=1` y `closed_at` con timestamp |
| 8. PDF descargado | Archivo `.pdf` en tu carpeta de Downloads |
| 9. Email enviado | 1 fila nueva en `mail_log` con `status='sent'` |

#### Detección de HTTP 500 (los 3 lugares donde aparece)

1. **DevTools Network tab:** cualquier request en rojo con status 500. El más visible.
2. **Terminal de `app.py`:** `Traceback (most recent call last):` seguido del stack trace.
3. **UI:** página gris de error de Flask (si `FLASK_DEBUG=True`) o página blanca genérica (si `FLASK_DEBUG=False`).

Cualquiera de los tres cuenta como corrida fallida. Anotar en qué paso.

#### Registro sugerido

Una planilla simple (papel o Google Sheet) tipo:

| Corrida | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | Notas |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | OK |
| 2 | ✓ | ✓ | ✗ | | | | | | | HTTP 500 en `/dml/recepcion` — ver log |

Si aparece HTTP 500 en cualquier corrida, se detiene la sesión, se debuggea, y se recorren las 5 corridas de nuevo desde cero. El criterio del cliente es "5 seguidas sin errores", no "5 con algún error corregido en el medio".

#### Tiempo estimado

Si todo va bien: **~30 minutos** las 5 corridas (~6 min por corrida). Si hay que debuggear: variable.

### No hacer este sprint
- No absorber #64 ni #65 (los hace Ivo).
- No unificar los 3 generadores de PDF (queda como issue separado para el sprint siguiente).

---

## Seba — Fase 1 migración + reestructura de scripts DB (L, ~14-18h)

**Puede arrancar hoy en paralelo con Facu.** Fase 1 no toca `app.py`. Facu no toca `schema.sql`.

### Setup Supabase
- [ ] Crear proyecto en supabase.com (plan gratuito — el Alcance define 500MB como suficiente)
- [ ] Guardar credenciales en gestor de passwords (no en el repo): Project URL, DB password, connection string PostgreSQL

### Traducir `schema.sql` → `db/schema-postgres.sql`

Conversiones necesarias:

| SQLite | PostgreSQL |
|---|---|
| `PRAGMA foreign_keys = ON;` | (borrar — PG lo hace por default) |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `INTEGER NOT NULL DEFAULT 0/1` (booleanos) | `BOOLEAN NOT NULL DEFAULT FALSE/TRUE` |
| `TEXT DEFAULT CURRENT_TIMESTAMP` | `TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP` |
| `TEXT` para fechas puras | `DATE` |
| FKs con `REFERENCES ... ON DELETE CASCADE` | Igual sintaxis |

Renombrar `audit_log` → `logs_auditoria` con:
- `id_log UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `fecha_hora TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `id_usuario INTEGER NOT NULL REFERENCES users(id)`
- `tipo_accion TEXT NOT NULL CHECK (tipo_accion IN ('INSERT','UPDATE','DELETE'))`
- `tabla_afectada TEXT NOT NULL`

(Requerido por RNF07 del Acta.)

- [ ] `db/schema-postgres.sql` creado con las 16 tablas convertidas + `logs_auditoria`
- [ ] Correr el schema en Supabase (SQL Editor) y verificar las 16 tablas
- [ ] Verificar foreign keys en Table Editor
- [ ] NO copiar los hashes hardcodeados de usuarios (líneas 280-284 del schema viejo). Los usuarios se crean en Fase 2 vía seed.

### Configuración Render
- [ ] `DATABASE_URL` como env var en Render (formato `postgresql://postgres:PASS@HOST:5432/postgres`)
- [ ] Probar conexión con `psql "$DATABASE_URL"` desde local

### Documentación
- [ ] Crear `MENTORIA/setup-supabase-render.md` con: cómo se creó el proyecto, dónde viven las credenciales, cómo obtener la connection string, cómo probar la conexión, troubleshooting.

### Reestructura de scripts DB en la raíz

Crear la carpeta `scripts/` y ordenar los archivos `.py` de la raíz que tocan SQLite. **Por qué ahora:** la reestructura ya estaba decidida, solo era timing. Hacerla junto con Fase 1 evita dejar la raíz sucia por 2 semanas y le da a Facu un entorno limpio para testear.

**Mover a `scripts/` (7 sobrevivientes + 1 condicional):**

Usar `git mv` para preservar historia:

- [ ] `git mv seed_data.py scripts/`
- [ ] `git mv seed_data_minimal.py scripts/`
- [ ] `git mv cargar_stock_nuevo.py scripts/`
- [ ] `git mv limpiar_bd.py scripts/`
- [ ] `git mv smoke_test.py scripts/`
- [ ] `git mv test_login.py scripts/`
- [ ] `git mv verificar_emails.py scripts/`
- [ ] `git mv run_migrations.py scripts/` (condicional — su destino final se decide en Fase 2)

**Ajustar el `sys.path.insert(...)` de cada uno.** Los scripts hoy tienen líneas como:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'CODIGO_FUENTE'))
```

Después del move a `scripts/`, la ruta relativa cambia. Actualizarlas a:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'CODIGO_FUENTE'))
```

Los que tienen `sys.path.insert(0, 'CODIGO_FUENTE')` (relativo a CWD, ej. `smoke_test.py`) también hay que actualizar para que funcionen desde la nueva ubicación.

Verificar que cada uno corre sin errores post-movida:
```
python scripts/seed_data_minimal.py
python scripts/smoke_test.py
# etc.
```

**Borrar (4 sqlite3 obsoletos):**

- [ ] `git rm check_tables.py` (19 líneas, usa `sqlite_master`, se reescribe si hace falta)
- [ ] `git rm generar_hashes.py` (los hashes ya no viven en el schema con .env)
- [ ] `git rm migrate_envios.py` (duplicado exacto de una función en `run_migrations.py`)
- [ ] `git rm migrate_tickets.py` (idem)

### PR
- [ ] PR contra `dev` con: `schema-postgres.sql` + carpeta `scripts/` con 8 archivos movidos + 4 archivos borrados + `MENTORIA/setup-supabase-render.md`
- [ ] Merge squash

### No hacer este sprint
- No tocar `CODIGO_FUENTE/app.py`.
- No borrar `schema.sql` viejo (sigue siendo la fuente hasta la Fase 2).
- No convertir los scripts movidos a `psycopg` — siguen usando `sqlite3` hasta la Fase 2. La movida es solo estructural.
- No tocar archivos que no usan `import sqlite3` (esos los mueve Ivo).

---

## Ivo — Git + kanban + rebase de #64 + reestructura no-DB (M+, ~11-14h)

### 1. Higiene de git (bloqueante — primero de todo)
**Por qué primero:** hasta que dev esté nivelada con main, cualquier branch nueva arrastra basura en el diff.

- [ ] Aprobar y mergear PR #82 (squash). Verificar después:
  ```
  git fetch origin
  git ls-tree origin/dev | grep app_backup  # NO debe devolver nada
  ```
- [ ] Borrar branch `chore/eliminar-app-backup-obsoleto` (ya mergeada como #81):
  ```
  git push origin --delete chore/eliminar-app-backup-obsoleto
  ```

### 2. Higiene de kanban (XS cada uno)
- [ ] Cerrar #60 con comentario "Duplicado de #61" (reason: not planned)
- [ ] Cerrar #33 con comentario "Obsoleto post-#74, RNF01 del Acta excluye .exe" (reason: not planned)
- [ ] Cerrar #22, #23, #24, #26 con comentario "Es categoría, no tarea. Ya está el field Épica en el Project"

### 3. Crear 3 issues nuevos para el sprint siguiente (backlog, sin asignar)

**Issue A — Unificar los 3 generadores de PDF (M)**
> El análisis detectó 3 implementaciones: `generar_ficha_pdf` en app.py:1043, `generate_ficha_pdf` en app.py:3337, y `generate_ficha_pdf_new` en `pdf_generator_new.py` (no integrado). Post-refactor #75, decidir cuál queda como canónico en `services/pdf.py` y borrar los otros dos. Depende de: merge de #75.

**Issue B — Proteger `cargar-stock-csv` con auth (XS)**
> Endpoint sin `@login_required` ni `@role_required("ADMIN")`. Hueco de seguridad. Depende de: merge de #75. Relacionado con #62.

**Issue C — Actualizar código para escribir en `logs_auditoria` (M)**
> Seba creó `logs_auditoria` en el schema-postgres (Fase 1). Este ticket es para adaptar el código Python que escribe en auditoría al nuevo formato (UUID, timestamptz, id_usuario NOT NULL). Depende de: merge de #75 y de Fase 1.

### 4. Retomar #64 con rebase (cierra #64 y #65)

**Por qué rebase y no branch nueva:** ya tenés 4 commits reales en `fix/remove-hardcoded-credentials`. Rebranchar es tirarlos. Rebase los reaplica sobre el `dev` actualizado y el diff queda limpio (sin las 4221 líneas ajenas que hundieron el PR #72).

- [ ] Rebase:
  ```
  git fetch origin
  git checkout fix/remove-hardcoded-credentials
  git rebase origin/dev
  # Resolver conflictos si aparecen (git add + git rebase --continue).
  # Cancelar todo: git rebase --abort.

  git log origin/dev..HEAD --oneline
  # Debe listar SOLO tus 4 commits.
  ```
- [ ] Eliminar el bloque `CORRECT_HASHES` de `CODIGO_FUENTE/app.py` líneas 449-465 aprox (es lo que se te había pasado — causa raíz de #65)
- [ ] Verificar:
  ```
  git diff origin/dev --stat
  # Debe mostrar SOLO tus cambios: .env.example, app.py con hardcodes reemplazados + CORRECT_HASHES eliminado.
  ```
- [ ] Push forzado (obligatorio tras rebase):
  ```
  git push --force-with-lease origin fix/remove-hardcoded-credentials
  # --force-with-lease es seguro: falla si alguien pusheó mientras rebaseabas.
  ```
- [ ] PR contra `dev`:
  ```
  gh pr create --base dev \
    --title "fix: mover credenciales a .env + eliminar CORRECT_HASHES (cierra #64 y #65)"
  ```
- [ ] Merge squash → #64 y #65 se auto-cierran.

### 5. Reestructura no-DB de la raíz

Ordenar los archivos de la raíz que no usan `import sqlite3` (los sqlite3 los mueve Seba). Regla simple: si tiene `import sqlite3`, no lo tocás. Si no, es tuyo.

**Mover a `scripts/` (Seba crea la carpeta en su PR, vos aprovechás):**

- [ ] `git mv test_email.py scripts/` (test SMTP puro, sin BD)

**Borrar (obsoletos de la era del ejecutable y huérfanos):**

- [ ] `git rm launcher.py` (raíz — wrapper del ex-.exe, RNF01 del Acta excluye ejecutable local)
- [ ] `git rm reset_db.html` (endpoint eliminado en #77, quedó huérfano el HTML)

**Actualizar (sin mover):**

- [ ] `.env.production`: eliminar la línea `DATABASE_URL=sqlite:////var/data/dml.db`. Es residuo de la era SQLite y confunde. La var se define recién en Fase 2.

**Ordenamiento del PR:** hacer estos cambios en tu misma rama del rebase de #64 (o sea, el PR del rebase incluye también esta reestructura no-DB). Si preferís separar en dos PRs porque temés que se choquen, dale.

- [ ] Ivo: `test_email.py` movido a `scripts/`
- [ ] Ivo: `launcher.py` (raíz) borrado
- [ ] Ivo: `reset_db.html` borrado
- [ ] Ivo: `.env.production` actualizado

---

## Orden de mergeo

1. **PR #82** (dev ← main) — bloquea a todos.
2. **PR de Ivo** (#64 + #65).
3. **PR de Seba** (Fase 1).
4. **PR de Facu** (#75, el más grande, último). Antes del PR, rebase su rama contra `dev` actualizado:
   ```
   git checkout refactor/modularizar-app-py
   git rebase origin/dev
   git push --force-with-lease origin refactor/modularizar-app-py
   ```

Convención de merge del equipo: **squash** siempre.

## Rebase vs merge

| Situación | Elección |
|---|---|
| Tu rama se atrasó respecto de dev | `git rebase origin/dev` |
| Rama compartida entre 2+ devs | `git merge origin/dev` (rebase reescribe SHAs, rompe copias ajenas) |
| PR aprobado listo para integrar | **Squash merge** desde la UI |

---

## Diferido al sprint siguiente

- Fase 2 migración (`sqlite3` → `psycopg`, 327 placeholders `?` → `%s` en app.py refactorizado)
- Convertir los scripts movidos a `scripts/` de `sqlite3` a `psycopg`
- Actualizar README (sacar referencias al .exe y al repo viejo `Tosabe033`)
- Unificar los 3 PDF (issue A)
- Proteger `cargar-stock-csv` (issue B)
- Actualizar código para `logs_auditoria` (issue C)
- #76 historial 800 máquinas (Seba, ETL Excel → PG)
- Frontend track para Ivo (#46, #47, #55)

---

## Cómo usar este doc

Cada checkbox tildado se acompaña de un commit al archivo:
```
docs(mentoria): 6.1 hecho — blueprint dml completado
```

Si algo del plan resulta inviable: comentarlo en el daily, ajustar el doc, seguir.

---

Matias
