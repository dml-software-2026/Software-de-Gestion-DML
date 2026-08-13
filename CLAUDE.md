# Contexto — Software de Gestión DML

Este documento es para que Claude Code tenga contexto completo del proyecto sin que
haya que reexplicarlo. Actualizarlo cuando cambie algo importante.

## Instrucciones de flujo de trabajo para Claude Code

**PRs chicos, siempre.** No armar un PR gigante con toda una tarea/issue resuelta de
punta a punta. Cortar el trabajo en sub-tareas pequeñas y autocontenidas, cada una en
su propia rama y su propio PR. Si una tarea tiene un checklist (issue de GitHub con
varios ítems), cada ítem — o grupo chico de ítems relacionados — es candidato a PR
separado, no todo junto.

**Commits y push: los hace Claude Code.** Una vez que un cambio chico está terminado
y probado (o listo para revisar), Claude Code se encarga de:
- `git add` de los archivos que correspondan (nunca `git add .` a ciegas — revisar
  qué se está agregando)
- `git commit` con un mensaje claro y descriptivo: qué se hizo y por qué, no solo
  "fix" o "update". Si el commit resuelve o avanza un issue de GitHub, mencionarlo
  en el cuerpo del mensaje (ej. `Refs #54` si es parcial, `Closes #54` solo si cierra
  la issue completa — la mayoría de las veces va a ser `Refs`, porque el trabajo está
  partido en varios PRs chicos)
- `git push` de la rama correspondiente

**Probar localmente con Facu antes de pushear, siempre que sea viable.** Levantar
el server local, avisar explícitamente "listo para probar" y decir qué probar y
cómo (pasos concretos, no solo "fijate que funcione"). Recién después de que Facu
confirma que anduvo, pushear. Si un PR ya está pusheado y aparece un problema al
probarlo, el fix va como commit nuevo en la misma rama (no hace falta rama nueva).

**Un PR abierto en GitHub no se mergea solo.** Mergear es una acción manual que
hace Facu desde GitHub — dejar PRs abiertos mientras se sigue probando no tiene
ningún riesgo, no hace falta cancelarlos ni cerrarlos "por las dudas".

**Los Pull Requests los abre Facu manualmente desde GitHub** (no desde la terminal).
Cuando un cambio esté commiteado y pusheado y listo para convertirse en PR, Claude
Code tiene que **avisarle explícitamente a Facu** — algo como: "Ya pusheé la rama
`nombre-rama`, andá a GitHub y abrí el PR contra `dev`. Título sugerido: '...'.
Descripción sugerida: '...' (con el `Closes #N` o `Refs #N` que corresponda)."
No dar por hecho que el PR se abre solo ni asumir que ya está abierto.

**Antes de tocar cualquier rama:** seguir la rutina de sincronización de siempre —
`git status` (si hay cambios sin commitear, resolverlos primero: `git diff` para ver
qué son, y decidir si se descartan, se guardan con `stash`, o se commitean),
`git checkout dev` + `git pull origin dev`, y recién ahí crear la rama nueva o
cambiarse a la que corresponda. No hacer `git pull` ni `git checkout` con cambios
sin resolver de por medio.

**Nombres de rama:** `tipo/descripcion-corta-con-guiones` (ej. `fix/proteger-endpoint`,
`feature/54-desplegable-tipo-maquina`). El tipo (`fix`, `feature`, `docs`, `chore`)
según corresponda al cambio.

## Proyecto

- **Nombre:** Software de Gestión DML (Práctica Profesionalizante, 6° año Computación)
- **Autor:** Facu, junto a Ivo y Sebastián (equipo de 3)
- **Mentor Scrum:** Matías (padre de Facu) — escribe el plan de cada sprint
- **Cliente:** David (owner) y Richard (co-owner) de DML Electricidad Industrial
- **Profesor:** Hugo Rodríguez
- **Repo:** https://github.com/dml-software-2026/Software-de-Gestion-DML
- **Deploy:** Render (con UptimeRobot para evitar cold-start)
- **Tablero:** GitHub Projects (Kanban)

## Stack

- Python + Flask, HTML/CSS/JS con Jinja2
- **Base de datos: PostgreSQL** (migración desde SQLite ya en curso/completa en `dev`,
  dos fases — Fase 2 se mergea esta sprint)
- Sin fallback a SQLite: `extensions.py` requiere `DATABASE_URL` en `.env`, si no
  existe tira error de conexión a `localhost:5432`

## Estructura del código (post-refactor)

```
CODIGO_FUENTE/
├── app.py                  # arma la app, registra 9 blueprints
├── config.py
├── extensions.py            # get_db, close_db, migrate_db, init_db
├── decorators.py             # login_required, permission_required, role_required
├── services/
│   ├── mail.py
│   ├── stock.py             # incluye check_stock_alert
│   ├── numeracion.py
│   ├── seed.py
│   └── pdf.py
└── blueprints/
    ├── auth.py
    ├── raypac.py
    ├── dml.py
    ├── tickets.py
    ├── envios.py
    ├── stock.py
    ├── admin.py
    ├── estadisticas.py
    └── api.py
```

El monolito original de 4163 líneas ya fue dividido en esto. Ya no hay rutas en `app.py`.

## Branches y flujo de PRs

- `main` = producción. Nadie mergea directo, todo pasa por `dev`.
- `dev` = entorno de desarrollo del equipo. Ahí van todos los PRs.
- **Convención de nombres:** `tipo/descripcion-corta` (ej. `fix/proteger-cargar-stock-csv`,
  `feature/54-ingreso-raypac`, `docs/hallazgos-refactor`, `chore/...`)
- **IMPORTANTE — PRs chicos:** el equipo pidió explícitamente hacer PRs pequeños, uno por
  sub-tarea, no un PR gigante al terminar toda una issue completa.
- Todo PR necesita review de al menos 1 integrante antes de mergear (Definition of Done).
- Al abrir un PR, usar `Closes #N` en la descripción para que el issue se cierre solo al
  mergear (probar con más de un `Closes #N` si el PR resuelve varios issues duplicados).

## Setup de entorno local

- **Requiere Python 3.11** — Flask 2.3.0 no es compatible con 3.12+ (tira
  `AttributeError: module 'pkgutil' has no attribute 'get_loader'`). Si la máquina
  tiene Python más nuevo: `py install 3.11` y `py -3.11 -m venv venv`
- El venv no se sube al repo, se recrea por máquina:
  ```bash
  python -m venv venv
  source venv/Scripts/activate
  pip install -r requirements.txt
  ```
- **`.env` local:** copiar `.env.example` a `.env` (NO usar `.env.production`, que
  existe en el repo y apunta a la base real). Completar `DATABASE_URL` con los datos
  de Postgres local, ej:
  ```
  DATABASE_URL=postgresql://postgres:TU_PASSWORD@localhost:5432/NOMBRE_BASE
  ```
- **Requiere PostgreSQL + pgAdmin 4 instalados localmente** desde postgresql.org
  (el instalador de EDB trae ambos juntos).
- **Bug conocido de orden de imports en `app.py`:** `load_dotenv()` se llama DESPUÉS
  de `from config import Config, BASE_DIR`, así que `config.py` lee `DATABASE_URL`
  antes de que el `.env` esté cargado — queda en `None` aunque el `.env` esté bien
  armado. Workaround hasta que se arregle en el código:
  ```bash
  export DATABASE_URL="postgresql://postgres:PASSWORD@localhost:5432/NOMBRE_BASE"
  python -m CODIGO_FUENTE.app
  ```
  (Nota: reportar este bug al equipo — la solución de fondo es mover `load_dotenv()`
  arriba del import de `config` en `app.py`.)
- **Correr la app:** `python -m CODIGO_FUENTE.app` desde la raíz del repo (NO
  `python CODIGO_FUENTE/app.py` directo, porque los imports internos son relativos
  al paquete `CODIGO_FUENTE`).
- Usuarios semilla: `admin@dml.local`/`admin`, `raypac@dml.local`/`raypac`,
  `tecnico@dml.local`/`tecnico`, `repuestos@dml.local`/`repuestos`
- **Lección aprendida:** confirmar siempre `git status` → "nothing to commit" antes
  de dar una tarea por cerrada (un cambio sin commitear se pierde si se formatea
  la máquina o se trabaja desde otra compu).

## Decoradores de auth — firmas exactas (`decorators.py`)

No inventar variantes de estos, usar tal cual:

```python
@login_required
def vista(...):
    ...

@role_required("ADMIN", "DML_ST")   # acepta *roles, cualquiera de estos pasa
def vista(...):
    ...

@permission_required(read_roles=["DML_ST"], write_roles=["DML_REPUESTOS"])
# ADMIN siempre tiene acceso completo (hardcodeado en el decorador).
# write_roles → acceso completo. read_roles → acceso de solo lectura,
# inyecta kwargs['readonly'] = True a la vista (la vista debe aceptar
# un parámetro readonly=False).
def vista(readonly=False, ...):
    ...
```

Orden de decoradores siempre: `@blueprint.route(...)` → `@login_required` →
`@role_required(...)` o `@permission_required(...)` → `def`.

`get_current_user()` (de `decorators.py`) devuelve el usuario logueado desde la
sesión, o `None`. Ya usado en casi todas las vistas para obtener `user['role']`,
`user['id']`, etc.

## Discrepancia conocida: DoD del #62 vs. comportamiento real

El issue #62 dice en su definition of done que un rol no autorizado debe recibir
**HTTP 403**. El comportamiento real de `role_required` y `permission_required` es
hacer **redirect** (302) a `auth.index` con un mensaje flash, no un 403. No "corregir"
esto sin consultarlo antes — es el comportamiento de todo el sistema, cambiarlo
rompería la UX en 40+ rutas. Si hace falta que algún endpoint puntual devuelva 403
en vez de redirect (por ejemplo si se agrega una API consumida por JS/fetch), evaluarlo
caso por caso, no tocar los decoradores compartidos.

## CI en desarrollo (puede cambiar el flujo de PRs pronto)

Sebastián está armando CI esta sprint (tarea propia, para que quede activo bloqueando
merges rotos en todos los PRs futuros). Cuando esté activo, los PRs van a tener checks
automáticos obligatorios antes de poder mergear. Si un PR queda bloqueado por un check
en rojo, no es necesariamente un error del cambio en sí — puede ser el CI recién
configurado con falsos positivos; avisarle a Facu en vez de intentar "arreglar" el
pipeline de CI sin que lo sepa.

## Roles del sistema

4 roles: `ADMIN`, `RAYPAC`, `DML_ST`, `DML_REPUESTOS`. (Confirmado como definitivo
en `SCOPE_v3.0.md` — un documento viejo, AS IS, proponía 2 roles, descartado.)

## Sprint actual — E2 (2026-08-10 → 2026-08-29)

- **Entregable:** módulo RAYPAC (ingreso y gestión de máquinas). Demo a David viernes 29/08.
- **Tareas de Facu (~20h):**
  1. **#62 — Endpoints sin auth** (en curso, casi cerrado): único endpoint desprotegido
     encontrado fue `/admin/cargar-stock-csv` en `blueprints/admin.py` (le faltaban
     `@login_required` y `@role_required("ADMIN")`, ya agregados). Issue duplicado #86
     cerrado en el mismo PR con `Closes #62` + `Closes #86`.
  2. **#54 — Corregir ingreso RAYPAC** (16h, core de la sprint) — ver detalle abajo.
- **Dailies:** lunes/miércoles/jueves, Matías participa.
- **Riesgo anotado:** si para el miércoles 20/08 el #54 no lleva 60% de avance, se corta
  el alcance.
- **Freeze de `dev`:** jueves 28/08 EOD.

## Issue #54 — Corregir ingreso de máquinas en RAYPAC (tarea activa)

**Objetivo:** un usuario RAYPAC puede loguearse, completar el formulario de nuevo
ingreso con todos los campos del scope, asignar remito, freezar, y que la máquina
aparezca del lado DML como "pendiente de recepción".

**Archivos clave:**
- `CODIGO_FUENTE/blueprints/raypac.py`
- `CODIGO_FUENTE/templates/raypac/new.html` (o similar — verificar nombre exacto,
  puede estar en `INTERFAZ/templates/`)
- `CODIGO_FUENTE/db/schema-postgres.sql`

**Checklist (8 ítems) — estado al 2026-08-13, todos cubiertos por código:**
- [x] Campo "Contacto del cliente" (visible solo RAYPAC y ADMIN) — PR #109
- [x] Campo "Mail del cliente" (visible solo RAYPAC y ADMIN) — PR #109
- [x] Desplegable de clientes con lista completa + autoaprendizaje (si escriben un
      cliente nuevo, preguntar si guardarlo) — rama `feature/54-desplegable-clientes`
      (pusheada, PR todavía sin abrir)
- [x] Desplegable de modelos de máquina (13 modelos: 7 ITA + 3 CT + 3 CTT) — ya estaba
      hecho de antes del refactor, confirmado exacto contra el Excel de David
- [x] Desplegable de tipo de máquina (A batería, manual, neumática, otro) — ídem, ya
      estaba hecho
- [x] Desplegable de comercial responsable con mail autocompletado — ya estaba hecho.
      **Ojo:** el issue original decía "5 comerciales, Leonardo Bastagel + 1 a
      confirmar con David" — eso estaba desactualizado. El Excel "CAMPOS DE INGRESO
      DML" que compartió David confirma que son **9 comerciales** y coinciden
      exactos (nombre y mail) con lo que ya había en el código: Ezequiel Pacheco,
      Leonardo Gastager, Luciana Gregorio, Luciana Paradiso, Daniela Sofio, Hernán
      Rivero, Matias Chaubell, Paola Isanelli (mail `paola.isabelli@`, sic), Romina
      Gamarra. No hace falta tocar nada acá.
- [x] Validar que no se pueda freezar sin número de remito — ya implementado en
      `raypac_freeze()`
- [x] Permitir ingresar solo los últimos 4 dígitos del remito con autocompletado de
      formato `00001-04222` — ya implementado en `raypac_freeze()`

**PRs abiertos contra `dev`** (todos `Refs #54`, ninguno cierra el issue solo):
- **#108** `docs/agregar-claude-md` — este archivo
- **#109** `feature/54-campos-contacto-mail-cliente` — oculta contacto/mail para
  roles DML en `dml_entregadas.html` + documenta las columnas en `schema-postgres.sql`
- **#110** `fix/54-numero-correlativo-postgres` — bug encontrado en el camino (ver
  Hallazgos abajo), no estaba en el plan original
- **`feature/54-desplegable-clientes`** (pusheada, PR sin abrir todavía) — tabla
  `clientes` con autoaprendizaje, sembrada con los 39 clientes del Excel de David

**Conflicto de merge esperable:** #110 y `feature/54-desplegable-clientes` agregan
cada uno un bloque de migración en el mismo punto de `migrate_db()` (`extensions.py`).
El que se mergee segundo va a pedir resolver un conflicto chico a mano — solo hay que
dejar los dos bloques `try/except`, ninguno pisa al otro.

**Técnica usada para probar los 3 juntos sin romper el esquema de PRs chicos:**
rama local `test/54-integracion-local` (cortada de `dev`, con los 3 branches
mergeados adentro) **nunca pusheada a GitHub** — sirve solo para levantar un único
server local y probar el flujo completo de una sentada. Se borra al terminar de
probar. Los PRs reales en GitHub siguen intactos y se revisan/mergean por separado,
esto no los reemplaza ni los toca.

**Definition of done del issue:**
1. Login RAYPAC → `/raypac/new` → completar form → guardar → remito 4 dígitos → freezar
2. Registro visible como "pendiente" del lado DML
3. RAYPAC no puede editar después de freezar (solo ADMIN con código de desbloqueo)
4. 5 flujos consecutivos sin HTTP 500 ni bloqueos
5. Un usuario DML no ve los campos de contacto/mail cliente

### Checklist manual de pruebas — estado al cierre de la sesión del 2026-08-13

Probado en la rama de integración local `test/54-integracion-local` (no pusheada,
ver más arriba). Facu la retoma en la próxima sesión: falta el punto 6, y un par de
sub-chequeos del resto quedaron sin confirmar explícitamente (marcados abajo).

Usuarios: `raypac@dml.local`/`raypac` · `tecnico@dml.local`/`tecnico` (DML_ST) ·
`admin@dml.local`/`admin`

1. ✅ **Alta de ingreso (PR #110):** confirmado, guarda sin error 500 (antes del fix
   tiraba "no existe la columna numero_correlativo").
2. ✅ **Desplegable de clientes — funcional:** confirmado (sugiere existentes,
   `confirm()` al escribir uno nuevo, autoaprendizaje guarda/no guarda según la
   respuesta). ⚠️ **Falta reconfirmar el estilo:** el desplegable nativo
   (`<datalist>`) salía negro y distinto al resto — se reemplazó por uno con
   clases de Bootstrap (`dropdown-menu`/`dropdown-item`) pusheado a
   `feature/54-desplegable-clientes`, pero Facu no llegó a volver a mirarlo
   después del fix. Retomar: refrescar `/raypac/new`, escribir en Cliente y
   confirmar que ahora es blanco y aparece debajo del campo.
3. ⚠️ **Contacto/mail (PR #109) — parcial:** confirmado que los campos se ven
   (con el texto "Visible solo para RAYPAC y ADMIN") logueado como `raypac`.
   **Falta confirmar el lado que realmente importa del fix:** loguearse como
   `tecnico` (DML_ST) y abrir `/raypac/<id>` de un ingreso freezado → esos dos
   campos NO deberían aparecer.
4. ⚠️ **Freeze — parcial:** confirmado que freeza y guarda remito. **Falta
   probar el sub-caso de edición bloqueada:** como `raypac` intentar editar un
   ingreso freezado sin código → debe bloquear. Como `admin` con `ADMIN2024` →
   debe permitir.
5. ✅ **Lado DML — recepcionar:** confirmado, el botón "Dar de Alta en DML" está
   en la sección "Estado de Envío del Equipo" de `/raypac/<id>` (no confundir
   con la tarjeta separada más abajo "Crear Ficha de Servicio Técnico", que es
   un flujo posterior y no forma parte de este checklist).
6. ❌ **`/dml/entregadas` oculta contacto/mail a DML_ST — sin probar todavía.**
   Requiere un registro en estado "entregado". Facu decidió recorrer el flujo
   completo por la UI en vez de que se lo prepare directo en la base. Pasos
   para retomar (logueado como `admin`, cubre todos los roles necesarios):
   1. `/raypac` → sobre el ingreso recepcionado → **"Crear Ticket"** (pide
      Técnico Responsable, obligatorio; el resto opcional).
   2. Desde `/raypac/<id>` (ahora con ticket) → **"Crear Ficha DML"** → completar
      y guardar → te deja en la edición de la ficha.
   3. En la edición: completar **Técnico Responsable**, **Diagnóstico**
      (mín. 10 caracteres), **N° Remito de Salida** — son obligatorios para
      poder cerrarla. El grid de "Estado del Equipo" se puede dejar con los
      valores por defecto. Guardar.
   4. En `/dml/<id>` → **"🔒 Cerrar Ficha"** (confirmar popup) → queda
      ENTREGADA. Si falta algo, el sistema lista exactamente qué campo falta.
   5. `/dml/entregadas`: como `admin`/`raypac` deben verse Contacto/Email; como
      `tecnico` no.

## Hallazgos pendientes (no resueltos, documentados en HALLAZGOS_REFACTOR.md)

**Seguridad (Épica 2):**
- Hashes de contraseñas hardcodeados en `migrate_db()` (tarea de Ivo, #64/#65)
- Código `"ADMIN2024"` hardcodeado y repetido 5 veces (`raypac_edit`, `dml_edit`,
  `stock_new`, `stock_edit`, `stock_delete`) — pendiente centralizar en variable de entorno

**Bugs confirmados:**
- `verificar_stock_api` en `blueprints/api.py` está roto (usa `db` sin definir y una
  tabla `stock_repuestos` que no existe) — genera falsos avisos de "sin stock" en el
  form de agregar repuestos, aunque el guardado real funciona bien. Documentado en el
  propio código con docstring explicando el problema, no arreglar sin confirmar antes
  si algo lo usa.
- Botón "Generar Ficha" nunca conectado al frontend (la ruta existe, ningún template la llama)
- Botón "Acuse" en `/dml/entregadas` usa sintaxis Bootstrap 4 en proyecto Bootstrap 5
  (`data-toggle` → debería ser `data-bs-toggle`)
- `raypac_new()` en `blueprints/raypac.py` inserta y lee la columna `numero_correlativo`
  de `raypac_entries`, pero esa columna no existe en `schema-postgres.sql` ni tenía
  migración en `extensions.py` (a diferencia de `contacto_cliente`/`email_cliente`, que
  sí la tienen). Reproducido en la práctica contra Postgres real (tira
  `no existe la columna «numero_correlativo»` al guardar un ingreso nuevo) — **fix en
  PR #110** (`fix/54-numero-correlativo-postgres`), pendiente de mergear a `dev`.
- `raypac_unfreeze()` no revierte `estado_envio_equipos` a `PENDIENTE` al desfreezar
  — un registro desfreezado puede quedar con `is_frozen=FALSE` pero
  `estado_envio_equipos='ENVIADO'`, mostrando el badge "Enviado desde RAYPAC" (y el
  botón "Dar de Alta en DML") como si siguiera en tránsito aunque ya no esté
  freezado. Encontrado probando el #54 (registro de prueba "Santi" en la base
  local), no confirmado todavía si pasa igual en producción ni si alguien lo
  reportó. Sin PR abierto, pendiente de decidir si se arregla en este sprint o
  se documenta como hallazgo para después.

**No urgente:**
- Dos generadores de PDF sin unificar (`generar_ficha_pdf` y `generate_ficha_pdf`) más
  un tercero sin integrar (`generate_ficha_pdf_new`) — tarea de Ivo (#85) esta sprint,
  puede no completarse y pasar a E3
- Archivos backup viejos candidatos a borrar: `dml_view_OLD.html`, `dml_edit_FIXED.html`,
  `dml_edit_BACKUP.html`

## Rutas sin `@login_required` a propósito (no son bugs)

- `tickets.py` → `ticket_view` (`/ticket/<numero_ticket>`) y `ticket_print` — vista
  pública de seguimiento para que el cliente final consulte su equipo sin cuenta

## Documentación / proceso académico

- Bitácora: pedir resumen de sesión al final de cada una para pegar en `BITACORA_DML_2026.xlsx`
- Log de uso de IA: generar entrada para `Log_Uso_IA_DML.docx` (Google Drive) al
  cierre de cada sesión de trabajo con Claude
- `CHANGELOG.md` en la raíz del repo: sigue pendiente
