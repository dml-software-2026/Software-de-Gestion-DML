# Plan de ordenamiento del repositorio DML: Sprint 2026-07-06

**Autor:** Matias Coca (mentor del proyecto)
**Fecha de emisión:** 2026-07-05
**Sprint objetivo:** 2026-07-06 → 2026-07-20
**Estado:** Living doc: se actualiza durante el sprint

---

## 0. Nota del mentor

Chicos, este documento es una guía de trabajo para el sprint que arranca el lunes 06/07. La idea:

- Es un **doc vivo**: van a marcar checkboxes con commits al archivo a medida que avancen.
- Yo lo actualizo desde la mentoría, ustedes lo ejecutan.
- Todas las tareas tienen su "por qué": no seguir instrucciones a ciegas.
- Si algo no cierra o encuentran algo mejor, se debate en el daily o en el issue correspondiente y se actualiza el doc.

Objetivo del ejercicio: dejar el repo en estado limpio y con roles claros para que puedan seguir avanzando sin pisarse. No es un ejercicio de "hacer lo que dice el mentor", es un ejercicio de **entender por qué el orden importa** y ejecutarlo con criterio propio.

---

## 1. Objetivo del sprint

Al cierre del sprint (20/07) el repo debería estar así:

- [ ] `dev` nivelada con `main` (una sola fuente de verdad para los devs)
- [ ] Kanban prolijo: sin duplicados, sin épicas vacías, con sizings realistas
- [ ] Raíz del repo limpia: solo lo indispensable, el resto en `scripts/` o borrado
- [ ] Branches muertas eliminadas
- [ ] Cada dev con su track claro y estimado

**Restricción importante:** durante este sprint **NO se toca `CODIGO_FUENTE/*.py`**. Facu está terminando el refactor #75 ahí, y cualquier cambio en paralelo genera conflictos de merge feos justo en el archivo más grande del repo.

---

## 2. Diagnóstico actual (relevado el 2026-07-05)

### 2.1 Branches remotas

| Branch | Última actividad | Estado |
|---|---|---|
| `main` | 2026-07-02 | Producción |
| `dev` | 2026-07-01 | Desarrollo: **atrasada respecto a main** (le falta el commit del `app_backup.py` borrado) |
| `refactor/modularizar-app-py` | 2026-07-02 | Facu, refactor en curso (issue #75) |
| `fix/remove-hardcoded-credentials` | 2026-06-29 | Ivo, **PR #72 cerrado sin merge** |
| `chore/eliminar-app-backup-obsoleto` | ya mergeada | Zombie: se puede eliminar |

### 2.2 PRs abiertos

- **#82 "Actualizacion de Dev"**: abierto por Seba, mergea `main` → `dev` para nivelar. Estado: **BLOQUEADO** por branch protection (necesita 1 aprobación).

### 2.3 Discrepancias en el kanban

- **Issues #60 y #61 duplicados**: ambos son "migrar SQLite → PostgreSQL". #61 es el canónico (la versión oficial de referencia: tiene checklist, está en In Progress). #60 no aporta nada.
- **Issue #33 (DML.exe desactualizado)**: no está en el kanban. El .exe se depuró en #74, hoy es obsoleto.
- **PR #72 de Ivo (credenciales)** cerrado sin merge por un diff gigante (4221 líneas). El propio Ivo lo notó en el review. Explicación abajo (sección 6.3).
- **Issues épica #22, #23, #24, #26**: están en Backlog sin descripción. Son categorías (equivalen al field `Épica` que ya existe en el kanban), no tareas ejecutables.

### 2.4 Hallazgos técnicos del refactor de Facu (issue #75)

Facu anotó tres cosas mientras refactorizaba, que merecen tickets propios:

1. Dos generadores de PDF distintos (`generar_ficha_pdf` y `generate_ficha_pdf`) usados en endpoints distintos → unificar o clarificar diferencia.
2. Bloque de hashes hardcodeados en `migrate_db()` que sobrescribe passwords en cada arranque → esto es la **causa raíz** del issue #65.
3. Endpoint `cargar-stock-csv` sin `@login_required` ni `@role_required("ADMIN")` → hueco de seguridad.

---

## 3. Convención de sizing (calibrada al equipo)

Con la carga real que pueden dedicar (8-10 hs por semana cada uno) y sprint de 2 semanas:

| Tamaño | Horas | Duración | Ejemplo |
|---|---|---|---|
| XS | ~2 h | 1 día | Cerrar un issue, marcar sección de un doc |
| S | 4-5 h | Media semana | Bug fix acotado, doc corto |
| M | 8-10 h | 1 semana | Feature chica end-to-end |
| L | 10-15 h | 1-2 semanas | Feature mediana o refactor localizado |
| XL | 16-20 h | 1 sprint completo | Refactor de módulo grande o migración |

**Regla del oficio:** si un ticket L va creciendo y arriba de 15h, se parte en sub-tickets. Si un XL se hace más largo que un sprint, es señal de que hay que subdividir en la retrospectiva.

---

## 4. División de trabajo propuesta (a validar en la planning)

**Nota:** esta sección es una propuesta del mentor para arrancar la discusión. Se cierra en la planning del lunes con lo que resuelva el equipo.

### Facu: Refactor de app.py + seguridad backend
- Prioridad 1: terminar **#75 refactor**, que es la piedra angular sobre la que descansa todo lo demás.
- Prioridad 2: **#62 endpoints sin autenticación** (continuación natural del refactor).
- Prioridad 3: **#54 RAYPAC ingreso máquinas** (mitad backend / mitad UI: coordinar con Ivo cuando llegue).

### Seba: Base de datos, data, infra
- Prioridad 1: continuar **#61 migración SQLite → PostgreSQL**.
- Prioridad 2: **#76 historial de 800 máquinas**, que se propone **reasignar desde Ivo hacia Seba**. Razón: es ETL puro (leer Excel y cargar a PostgreSQL), encaja con su track de BD, y necesita que la migración esté lista para tener las tablas destino.

### Ivo: Ordenamiento del repo + terminar #64
- Sprint completo dedicado a **ejecutar los puntos 5, 6 y 7 de este documento**.
- Al cierre del sprint, en retrospectiva, el equipo define la próxima épica de Ivo. Candidatos: frontend + UX, seguridad continuación, backups.

**Por qué esta división:**
- Balancea la carga (aprox. 8-10h/semana cada uno).
- Evita que dos personas toquen los mismos archivos.
- Le da a Ivo un track finito pero completo, con muchos entregables visibles.
- Deja a Facu concentrado en el refactor sin interrupciones.

---

## 5. Track 1: Higiene del kanban (owner: Ivo)

### 5.1 Cerrar issue #60 como duplicado: XS

**Contexto:** #60 y #61 son ambos "migrar SQLite → PostgreSQL". #61 es el que tiene checklist y está en In Progress.

**Pasos:**
1. Ir al issue: https://github.com/dml-software-2026/Software-de-Gestion-DML/issues/60
2. Comentar:
   ```
   Cerrado como duplicado del #61, que es el canónico con checklist completo y está en seguimiento en el kanban.
   ```
3. Cerrar el issue con reason "not planned".

**Chequeo de completitud:** el issue #60 aparece con estado "Closed" y linkea a #61.

- [ ] Ivo: hecho

### 5.2 Decidir sobre issue #33 (DML.exe desactualizado): XS

**Contexto:** el .exe se depuró en #74 (Seba). El issue #33 pide "actualizar DML.exe", hoy es obsoleto.

**Decisión propuesta:** cerrar como obsoleto.

**Pasos:**
1. Comentar en #33:
   ```
   Cerrado como obsoleto. El ejecutable se depuró en #74 y el sistema pasó a modo web-only. Ya no hay DML.exe que actualizar.
   ```
2. Cerrar con reason "not planned".

- [ ] Ivo: hecho

### 5.3 Crear 3 issues nuevos por hallazgos del refactor: XS cada uno

Facu detectó 3 items nuevos mientras refactorizaba. Los abrimos como issues propios para que el kanban los capture.

**Issue A: Unificar los dos generadores de PDF**

```
Título: Unificar generadores de PDF: generar_ficha_pdf vs generate_ficha_pdf

Descripción:
Durante el refactor de app.py (issue #75) se detectó que existen dos generadores de PDF de fichas con nombres muy similares (`generar_ficha_pdf` y `generate_ficha_pdf`), usados en endpoints distintos. Evaluar si conviene unificar o si son deliberadamente distintos.

Checklist:
- [ ] Ubicar los dos generadores en el código refactorizado (`services/pdf.py`)
- [ ] Documentar qué hace cada uno y desde qué endpoint se llama
- [ ] Decidir: unificar en uno solo, o mantener separados con nombres claros
- [ ] Ejecutar el cambio y probar generación de PDF en ambos flujos

Épica sugerida: Seguridad y deuda técnica
Size sugerido: S
```

**Issue B: Proteger endpoint `cargar-stock-csv` con auth**

```
Título: Proteger endpoint cargar-stock-csv con @login_required y @role_required("ADMIN")

Descripción:
Durante el refactor de app.py (issue #75) se detectó que el endpoint `cargar-stock-csv` no tiene decorador de autenticación. Cualquiera con la URL puede cargar stock. Es un hueco de seguridad.

Checklist:
- [ ] Agregar `@login_required` al endpoint
- [ ] Agregar `@role_required("ADMIN")` (o el rol que corresponda)
- [ ] Probar que un usuario no-admin no puede cargar stock
- [ ] Probar que un admin sí puede

Épica sugerida: Seguridad y deuda técnica
Size sugerido: XS
Relacionado con: #62 (identificar TODOS los endpoints sin auth)
```

**Issue C: Eliminar hashes hardcodeados en `migrate_db()` (cierra #65)**

```
Título: Eliminar bloque de hashes hardcodeados en migrate_db(): causa raíz de #65

Descripción:
Facu identificó que en `migrate_db()` hay un bloque que reescribe passwords hardcodeadas en cada arranque del servidor. Esto explica el issue #65 (las passwords se auto-revierten). Este ticket es la ubicación concreta de la solución: al mergearse cierra #65.

Checklist:
- [ ] Localizar el bloque de hashes en `migrate_db()` (post-refactor: probablemente en `services/seed.py`)
- [ ] Eliminar la lógica que sobrescribe passwords existentes
- [ ] Mantener creación inicial solo si el usuario no existe (idempotente)
- [ ] Probar: crear usuario → cambiar password → reiniciar server → verificar que persiste

Épica sugerida: Seguridad y deuda técnica
Size sugerido: M
Cierra: #65
```

**Pasos:**
1. Crear los 3 issues con los textos de arriba desde la UI de GitHub o con `gh issue create`.
2. Dejarlos sin asignar por ahora. La asignación (probablemente a Facu, por conocimiento del refactor) se decide en la planning del siguiente sprint, cuando se calendaricen para ejecución.
3. Agregarlos al Project (kanban) con épica "Seguridad y deuda técnica" y estado "Backlog".

- [ ] Ivo: issue A creado
- [ ] Ivo: issue B creado
- [ ] Ivo: issue C creado (y linkeado a #65)

### 5.4 Reordenar issues épica #22 #23 #24 #26: XS

**Contexto:** estos issues están en Backlog sin descripción y son categorías, no tareas. Confunden el kanban porque parecen tickets ejecutables cuando en realidad son etiquetas.

**Decisión propuesta:** cerrarlos. Ya existe el field `Épica` en el Project con las 5 épicas correctas (Gest. Proyecto, Seguridad y deuda técnica, Gest. reparaciones, Gest. stock, Infraestructura y deploy). Los tickets concretos ya se etiquetan por ese field.

**Pasos:**
1. Cerrar los 4 issues (#22, #23, #24, #26) con comentario:
   ```
   Cerrado. Este issue representaba una categoría/épica, no una tarea. Las épicas ya están capturadas en el field `Épica` del Project. Los tickets concretos de cada épica se etiquetan con el field, no como cards separadas.
   ```

- [ ] Ivo: #22 cerrado
- [ ] Ivo: #23 cerrado
- [ ] Ivo: #24 cerrado
- [ ] Ivo: #26 cerrado

### 5.5 Revisar sizing en la planning: S

En la planning revisar los tamaños actuales y calibrar con el criterio de la sección 3. Casos concretos a discutir:

| Issue | Tamaño actual | Propuesta mentor | Razón |
|---|---|---|---|
| #75 refactor app.py | L | **XL** | En el issue #75 quedan 7 blueprints sin implementar (`dml`, `tickets`, `envios`, `stock`, `admin`, `estadisticas`, `api`), más armar el `app.py` nuevo chico, más tests manuales, más el PR final. Estimado supera las 15h. |
| #64 credenciales | M | **S** | Revisando `app.py` se ven varios hardcodes ya reemplazados por lecturas de `.env` en el trabajo previo de Ivo. Rehacerlo limpio sobre `dev` actualizado es medio sprint. |
| #65 password revert | M | **S** | Bug fix acotado: eliminar el bloque de hashes hardcodeados en `migrate_db()` (se ve en un solo lugar de `app.py`). |
| #46 impresión | S | **M** | Impresión web (CSS `@media print`, márgenes, page-breaks) es notoriamente delicada. Casi seguro pasa medio sprint. |
| Resto | - | mantener | - |

**Regla para validar avance:** el tamaño y el "porcentaje hecho" se miran en el código y en los commits/PRs, no en los checkboxes tildados del issue. Los checkboxes se pueden marcar sin haber hecho el trabajo; los diffs no mienten. Aplica a todos los issues del kanban.

- [ ] Equipo: sizing revisado y actualizado en planning

---

## 6. Track 2: Higiene de git (owner: Ivo)

### 6.1 Nivelar dev con main mergeando PR #82: XS

**Contexto:** PR #82 está OPEN y mergeable pero BLOQUEADO por la regla de branch protection (necesita 1 aprobación de alguien que no sea el autor).

**Pasos:**
1. Alguien del equipo (Facu o Ivo, no Seba que es el autor) revisa PR #82: https://github.com/dml-software-2026/Software-de-Gestion-DML/pull/82
2. Aprueba el PR desde la UI.
3. Seba mergea con **squash** (según la convención del equipo: un merge, un commit).
4. Verificar que dev quedó al día. Como #82 se mergea con squash, los commits originales de main no aparecen literalmente en la history de dev (llegan como un solo commit nuevo), así que la verificación se hace por contenido y no por comparación de commits:
   ```
   git fetch origin
   # Actualiza las referencias locales al remoto (origin/main, origin/dev) para
   # que reflejen el estado actual de GitHub. NO modifica los archivos de tu
   # working tree (la carpeta del proyecto en tu disco): solo actualiza los
   # "punteros" que git guarda en .git/. Contraste: git pull sí modificaría
   # los archivos porque hace fetch + merge sobre tu branch activa.

   git ls-tree origin/dev | grep app_backup
   # Lista los archivos trackeados en la punta de la branch dev remota y
   # filtra los que contengan "app_backup" en el nombre. Después de mergear
   # #82 este comando debería NO devolver nada: si aparece app_backup.py,
   # dev todavía no tiene el borrado que traía main y el merge falló o
   # quedó incompleto.

   git diff --stat origin/main origin/dev
   # Muestra los archivos con diferencias entre main y dev, con el conteo
   # de líneas modificadas por archivo. Después de mergear #82 las diferencias
   # que queden solo deberían corresponder a trabajo en curso propio de dev
   # (features que dev tiene y main aún no): NO debería aparecer ningún
   # archivo que exista en main pero falte en dev.
   ```

- [ ] Facu o Ivo: PR #82 aprobado
- [ ] Seba: PR #82 mergeado
- [ ] Ivo: verificación de que dev está al día

### 6.2 Eliminar branches muertas: XS

**Contexto:** hay branches remotas que ya cumplieron su función y solo agregan ruido.

**Branches a borrar:**
- `chore/eliminar-app-backup-obsoleto`: mergeada como PR #81, ya cumplió.
- `fix/remove-hardcoded-credentials`: la del PR #72 cerrado. Ivo la retoma en una branch nueva (ver 6.3), no reutiliza esta.

**Pasos (desde tu terminal, Ivo):**
```
git fetch --prune
# --prune limpia las referencias locales a branches remotas que ya no existen.

git push origin --delete chore/eliminar-app-backup-obsoleto
git push origin --delete fix/remove-hardcoded-credentials
# Cada push --delete borra la branch en el remoto.
```

Si GitHub protesta porque no tenés permisos para borrar branches, pedile a Facu que las borre él desde Settings → Branches.

- [ ] Ivo: `chore/eliminar-app-backup-obsoleto` borrada
- [ ] Ivo: `fix/remove-hardcoded-credentials` borrada

### 6.3 Retomar #64 credenciales: S (branch nueva)

**Por qué se cerró PR #72:**

Ivo: el PR #72 se cerró porque el diff mostraba 4221 líneas agregadas al app.py, lo que no era real. Vos mismo lo notaste en el comentario del PR. Casi seguro pasó esto:

> Cuando armaste la branch `fix/remove-hardcoded-credentials`, la basaste en un commit viejo de main. Después main avanzó (Facu mergeó cambios grandes: refactors, borrado de app_backup, etc.), pero tu branch no. Al momento del PR, GitHub compara tu branch contra el main actual y muestra como "agregado por vos" TODO lo que main avanzó desde tu base: de ahí las 4221 líneas.

**Lección git útil (para todo el equipo):**
- Las branches de features cortas se hacen desde un `dev`/`main` **actualizado justo antes de arrancar**.
- Si una branch de "corregir 1 archivo" muestra 4000 líneas de diff, algo pasó con la base. Antes de abrir PR, chequear `git log dev..HEAD --oneline`: deberían aparecer solo tus commits.
- Si tu branch se atrasa mucho respecto de `dev`, rebasar antes de abrir el PR: `git rebase dev`. `rebase` reaplica tus commits sobre la punta actual de `dev`, dejando el historial lineal y el diff limpio (solo tus cambios).

**Pasos:**
1. Actualizar `dev` local:
   ```
   git checkout dev
   # Cambia tu working tree a la branch dev (te "parás" sobre dev).

   git pull origin dev
   # Trae los últimos commits de la branch dev del remoto (origin) y los integra
   # en tu dev local. Es git fetch + git merge en un solo paso.
   ```
2. Crear una branch nueva desde `dev`:
   ```
   git checkout -b fix/credenciales-env-v2
   # -b crea una branch nueva llamada "fix/credenciales-env-v2" a partir del HEAD
   # actual (dev recién actualizado) y te cambia a ella. Todos tus siguientes
   # commits se van a apilar en esta branch, no en dev.
   ```
3. Reaplicar los cambios que ya tenías (mover hardcodes a `.env`). Si tenés el diff guardado, aplicarlo. Si no, rehacer manualmente: es rápido.
4. **Verificar que el diff es solo lo tuyo antes de pushear:**
   ```
   git log dev..HEAD --oneline
   # Lista los commits que existen en tu branch actual (HEAD) y NO en dev.
   # Deben aparecer SOLO los tuyos. Si aparecen commits ajenos, algo salió mal
   # con la base (te habrías olvidado de actualizar dev antes de branchar).

   git diff dev --stat
   # Muestra un resumen del diff contra dev: qué archivos cambiaron y cuántas
   # líneas por archivo. Debería ser corto (pocos archivos, pocas líneas).
   ```
5. Push + abrir PR **contra `dev`** (no contra main directo: el flujo acordado es siempre dev primero, después dev → main):
   ```
   git push -u origin fix/credenciales-env-v2
   # Sube tu branch al remoto (origin). -u (upstream) hace que futuros
   # `git push` y `git pull` sin argumentos ya sepan a qué branch remota apuntar.

   gh pr create --base dev --title "fix: mover credenciales hardcodeadas a .env (cierra #64)"
   # Crea un Pull Request en GitHub desde la CLI. --base define la branch
   # destino (dev). La frase "cierra #64" en el título o el body hace que
   # GitHub auto-cierre el issue #64 cuando el PR se mergee.
   ```
6. Cerrar el issue #64 cuando se mergee.

- [ ] Ivo: dev local actualizado
- [ ] Ivo: branch nueva creada
- [ ] Ivo: cambios reaplicados
- [ ] Ivo: diff verificado (solo lo suyo)
- [ ] Ivo: PR abierto contra dev
- [ ] Facu o Seba: revisar y aprobar
- [ ] Ivo: PR mergeado + issue #64 cerrado

---

## 7. Track 3: Reestructura de la raíz del repo (owner: Ivo)

### 7.1 Auditoría de los ~14 archivos .py sueltos en la raíz: S

**Contexto:** hay 14 archivos .py en la raíz (fuera de `CODIGO_FUENTE/`). Nadie sabe cuáles se usan en producción, cuáles son scripts one-shot, y cuáles son basura de la era del .exe.

**Criterio de decisión para cada archivo:**

1. **¿Lo importa `CODIGO_FUENTE/app.py` o lo referencia el `Procfile`?**
   - Sí → es dependencia productiva, **NO mover ni borrar**.
   - No → paso 2.
2. **¿Es un script one-shot ya ejecutado en el pasado (migración vieja de datos, generación de hashes que ya se aplicaron)?**
   - Sí → **borrar**. Ya cumplió; si se necesita otra migración se hace desde cero.
3. **¿Es un script útil de mantenimiento o setup (seed, run_migrations, test_*, verificar_*)?**
   - Sí → **mover a nueva carpeta `scripts/`**.
4. **¿Es basura de la era del .exe** (referencias a launcher del ejecutable, PyInstaller, etc.)?
   - Sí → **borrar**. El .exe se eliminó en #74.

**Hipótesis del mentor: a validar en la auditoría antes de ejecutar:**

| Archivo | Hipótesis | Acción sugerida |
|---|---|---|
| `cargar_stock_nuevo.py` | Script mantenimiento (carga CSV a BD) | mover a `scripts/` |
| `check_tables.py` | Debug SQLite one-shot | **borrar** (obsoleto con PostgreSQL de #61) |
| `generar_hashes.py` | Helper para generar hashes de `schema.sql` | **borrar** (con .env de #64 los hashes ya no viven en schema) |
| `launcher.py` (raíz) | Wrapper del launcher del .exe | **borrar** (era del ejecutable eliminado) |
| `limpiar_bd.py` | Debug SQLite one-shot | **borrar** (obsoleto con PostgreSQL) |
| `migrate_envios.py` | Migración one-shot ya ejecutada en producción | **borrar** |
| `migrate_tickets.py` | Migración one-shot ya ejecutada en producción | **borrar** |
| `run_migrations.py` | Migraciones para producción: **verificar si el flujo de deploy en Render lo llama** | investigar; si no se usa, mover a `scripts/`; si se usa, dejar y documentar |
| `seed_data.py` | Seed general de datos | mover a `scripts/` |
| `seed_data_minimal.py` | Seed mínimo de datos | mover a `scripts/` (evaluar consolidar con seed_data.py) |
| `smoke_test.py` | Test humo del sistema (hace `sys.path.insert(0, 'CODIGO_FUENTE')`) | mover a `scripts/`: cuidado con el path si se ejecuta desde otro lado |
| `test_email.py` | Test SMTP | mover a `scripts/` |
| `test_login.py` | Test credenciales de login | mover a `scripts/` |
| `verificar_emails.py` | Verificación post-deploy SMTP | mover a `scripts/` |

**Comandos útiles para verificar imports antes de mover/borrar:**
```
# ¿algún .py de la raíz se importa desde app.py?
grep -rn "cargar_stock_nuevo\|check_tables\|generar_hashes\|launcher\|limpiar_bd\|migrate_envios\|migrate_tickets\|run_migrations\|seed_data\|smoke_test\|test_email\|test_login\|verificar_emails" CODIGO_FUENTE/

# ¿algún archivo lo llama el Procfile?
cat Procfile

# ¿algún script one-shot ya se ejecuto? (preguntar en el daily a Facu/Seba)
```

- [ ] Ivo: auditoría completada
- [ ] Ivo: tabla de decisiones actualizada en un comentario del PR (7.2)

### 7.2 Ejecutar la reestructura: M

**Pasos:**

1. Actualizar dev local (imprescindible después de 6.1):
   ```
   git checkout dev && git pull origin dev
   # Encadena dos comandos con &&: primero cambia a la branch dev, y solo si
   # ese comando salió bien (exit code 0), ejecuta git pull para traer los
   # últimos cambios del remoto. Si el checkout falla, el pull no se ejecuta.
   ```
2. Crear branch nueva:
   ```
   git checkout -b chore/reestructura-raiz
   # -b crea la branch "chore/reestructura-raiz" desde el HEAD actual (dev)
   # y te cambia a ella.
   ```
3. Crear la carpeta:
   ```
   mkdir -p scripts
   # mkdir crea el directorio. -p ("parents") evita error si ya existe
   # y crea directorios intermedios si hicieran falta.
   ```
4. Mover los archivos "keep" a `scripts/` con `git mv` (preserva el historial):
   ```
   # git mv es equivalente a mv + git rm del archivo viejo + git add del archivo nuevo.
   # Registra el cambio como "rename" en el commit, así git blame y git log --follow
   # pueden seguir el linaje del archivo a través de la mudanza.
   git mv seed_data.py scripts/
   git mv seed_data_minimal.py scripts/
   git mv verificar_emails.py scripts/
   git mv test_email.py scripts/
   git mv test_login.py scripts/
   git mv smoke_test.py scripts/
   git mv cargar_stock_nuevo.py scripts/
   # + run_migrations.py según decisión de la auditoría
   ```
5. Borrar los archivos obsoletos:
   ```
   # git rm borra el archivo del working tree Y marca el borrado en el índice
   # (staging). Es distinto de "rm" a secas: aquel solo borra del disco, no
   # deja el borrado listo para commitear.
   git rm check_tables.py limpiar_bd.py migrate_envios.py migrate_tickets.py launcher.py generar_hashes.py
   ```
6. **Verificar que ningún script movido rompe por imports/paths:**
   - Correr cada script movido desde la raíz del repo (`python scripts/smoke_test.py`) para verificar que sigue funcionando.
   - Si algún script usa paths relativos que asumen estar en la raíz, ajustar o dejar una nota en el propio script.
7. Crear el commit:
   ```
   git commit -m "chore: reestructurar raiz del repo: scripts/ + limpieza de obsoletos

   - Mueve scripts de mantenimiento/testing a scripts/
   - Elimina scripts one-shot ya ejecutados y basura del ex-.exe
   - No toca CODIGO_FUENTE/ (refactor #75 en curso)"
   # git commit -m arma el commit con lo que esté en el índice (staging).
   # El mensaje entre comillas puede tener saltos de línea: la primera línea
   # es el título (convención: max 72 caracteres, imperativo) y el resto es
   # el cuerpo con contexto adicional.
   ```
8. Push y abrir PR contra `dev`:
   ```
   git push -u origin chore/reestructura-raiz
   # Sube tu branch al remoto y configura el tracking (-u), igual que en 6.3.

   gh pr create --base dev --title "chore: reestructurar raiz del repo" \
     --body "Ejecuta la seccion 7 del plan de ordenamiento (MENTORIA/plan-ordenamiento-2026-07-06.md).

   Auditoria realizada segun el criterio del plan. Ver tabla en el comentario a continuacion."
   # gh pr create arma el PR desde la línea de comandos. --base es la branch
   # destino (dev), y --body permite pasar el cuerpo del PR. La barra invertida
   # al final de la línea 1 le dice al shell que el comando sigue en la línea
   # siguiente (para no tener una sola línea muy larga).
   ```
9. Como primer comentario del PR, pegar la tabla de decisiones final (7.1) con lo que Ivo efectivamente resolvió.

**Alcance del PR:** SOLO la raíz. NO tocar `CODIGO_FUENTE/*` (Facu está ahí).

- [ ] Ivo: branch creada
- [ ] Ivo: archivos movidos con `git mv`
- [ ] Ivo: archivos borrados con `git rm`
- [ ] Ivo: cada script movido verificado (corre desde su nueva ubicación)
- [ ] Ivo: commit hecho
- [ ] Ivo: PR abierto contra dev + tabla de decisiones en comentario
- [ ] Facu o Seba: revisar y aprobar
- [ ] Ivo: PR mergeado

### 7.3 Nota sobre `CODIGO_FUENTE/`: para el próximo sprint

Dentro de `CODIGO_FUENTE/` también hay archivos que revisar (`DML.spec`, `hash_password.py`, `launcher.py`, `load_stock.py`, `pdf_generator_new.py`, `show_stats.py`). **No se tocan en este sprint** porque Facu está terminando el refactor #75 ahí.

Cuando su refactor se mergee, planificar un segundo pase de limpieza dentro de esa carpeta como track del sprint siguiente.

---

## 8. Trabajo en paralelo (Facu, Seba)

### Facu: continúa con #75 refactor
- Terminar los blueprints faltantes: `dml`, `tickets`, `envios`, `stock`, `admin`, `estadisticas`, `api`.
- Armar el `app.py` nuevo (chico), reemplazar el monolito.
- Probar los flujos principales manualmente (login, crear ficha, generar PDF, movimientos de stock).
- Abrir PR a `main` con tag `pre-refactor-monolito` sobre el último commit del monolito.
- **Disponibilidad para reviews:** cuando Ivo abra los PRs de las secciones 6.3 y 7.2, revisar rápido para no bloquearlo.

### Seba: continúa #61 migración + toma #76 historial
- Terminar la migración SQLite → PostgreSQL siguiendo el checklist del propio issue #61.
- Una vez lista la BD en Supabase, arrancar #76 (historial de 800 máquinas): es ETL directo Excel → PostgreSQL, encaja con el track de BD.
- Documentar la conexión Render ↔ Supabase para que el resto del equipo pueda configurarse local sin adivinar.

---

## 9. Checklist consolidado

### En la planning del lunes 06/07
- [ ] Discutir y aprobar (o ajustar) la propuesta de división de trabajo: sección 4
- [ ] Revisar y actualizar sizing de issues activos: sección 5.5
- [ ] Confirmar tamaños objetivo para el sprint por dev
- [ ] Asignar owners a los 3 issues nuevos por hallazgos del refactor: sección 5.3
- [ ] Confirmar reasignación de #76 (Ivo → Seba)

### Durante el sprint
- Sección 5 completa (Ivo)
- Sección 6 completa (Ivo con reviews de Facu/Seba)
- Sección 7 completa (Ivo con reviews de Facu/Seba)
- Sección 8 en marcha (Facu, Seba)

### Retrospectiva al cierre del sprint (20/07)
- ¿Se cumplieron los objetivos de la sección 1?
- ¿El sizing calibró bien vs realidad?
- ¿Cuál es la próxima épica para Ivo?
- ¿Qué del proceso funcionó bien y qué hay que ajustar?

---

## 10. Cómo mantener este documento

- Cada checkbox tildado se acompaña de un commit al archivo con mensaje tipo:
  ```
  docs(plan): 5.1 hecho: issue #60 cerrado como duplicado
  ```
- Si aparece una tarea nueva no prevista: agregarla en la sección que corresponda con un commit.
- Si algo del plan resulta inviable: comentarlo en el daily, ajustar el doc, seguir.
- El mentor va a revisar el estado en cada daily y actualizar la parte estratégica si hace falta.

---

**Vamos.**

Matias
