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

**Checklist (8 ítems, 2 ya resueltos):**
- [ ] Campo "Contacto del cliente" (visible solo RAYPAC y ADMIN)
- [ ] Campo "Mail del cliente" (visible solo RAYPAC y ADMIN)
- [ ] Desplegable de clientes con lista completa + autoaprendizaje (si escriben un
      cliente nuevo, preguntar si guardarlo)
- [ ] Desplegable de modelos de máquina (13 modelos: 7 ITA + 3 CT + 3 CTT)
- [ ] Desplegable de tipo de máquina (A batería, manual, neumática, otro)
- [ ] Desplegable de comercial responsable con mail autocompletado (5 comerciales:
      Leonardo Bastagel, Luciana, Ezequiel Pacheco, Daniela Sofio, + 1 a confirmar
      con David)
- [x] Validar que no se pueda freezar sin número de remito — **ya implementado**
      en `raypac_freeze()`
- [x] Permitir ingresar solo los últimos 4 dígitos del remito con autocompletado de
      formato `00001-00004222` — **ya implementado** en `raypac_freeze()`

**Plan de PRs chicos acordado** (uno por sub-ítem, no un PR gigante):
0. Research: revisar `schema-postgres.sql` para ver si `raypac_entries` ya tiene
   `contacto_cliente` y `email_cliente` (el backend en `raypac.py` ya los maneja
   en las queries, puede que solo falte el HTML)
1. `feature/54-campos-contacto-mail-cliente` — los dos campos con visibilidad por rol
2. `feature/54-desplegable-tipo-maquina` — el más simple, 4 opciones estáticas
3. `feature/54-desplegable-modelos` — 13 opciones estáticas
4. `feature/54-desplegable-comercial` — mapping nombre→mail, dejar para el final
   porque falta confirmar el 5° comercial
5. `feature/54-desplegable-clientes` — el más complejo, necesita persistencia
   (autoaprendizaje de clientes nuevos)

**Definition of done del issue:**
1. Login RAYPAC → `/raypac/new` → completar form → guardar → remito 4 dígitos → freezar
2. Registro visible como "pendiente" del lado DML
3. RAYPAC no puede editar después de freezar (solo ADMIN con código de desbloqueo)
4. 5 flujos consecutivos sin HTTP 500 ni bloqueos
5. Un usuario DML no ve los campos de contacto/mail cliente

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
  de `raypac_entries`, pero esa columna no existe en `schema-postgres.sql` ni tiene
  migración en `extensions.py` (a diferencia de `contacto_cliente`/`email_cliente`, que
  sí la tienen). Si corre tal cual contra Supabase, el guardado de un ingreso nuevo se
  rompe — hallazgo encontrado trabajando el #54, pendiente de confirmar y arreglar.

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
