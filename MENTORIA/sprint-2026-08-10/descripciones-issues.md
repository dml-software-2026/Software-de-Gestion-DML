# Descripciones detalladas de los issues del board

**Autor:** Matias Coca (mentor)
**Fecha:** 2026-08-10
**Estado:** para copiar y pegar como body de cada issue en GitHub

---

## Cómo usar este documento

**Problema que resuelve:** los issues del board tienen títulos claros pero descripciones flojas o inexistentes. En las dailies no saben explicar sus tareas y arrancan sin plan. Esto los frena.

**Cómo lo usan:**
1. Un integrante (sugerencia: **Ivo**, ya tiene la tarea de "cleanup del board" asignada — puede aprovechar el pasaje) toma este doc.
2. Por cada issue listado abajo, abre el issue en GitHub, y **pega el bloque DESCRIPCIÓN completo** en el body del issue (reemplaza lo que estaba antes o lo complementa).
3. Los checkboxes del alcance quedan como task list de GitHub para trackear progreso.
4. Duración estimada de la tarea: 45-60 min mecánicos.

**Formato de cada bloque:**

Cada issue tiene primero unas líneas de **metadata** (para vos, no van al issue), y después el **DESCRIPCIÓN** propiamente dicho que es lo que se copia. La línea `---` separa un issue del siguiente.

**Referencias que usan las descripciones:**
- Scope v2.0 (Sebastián López, 2026-07-01) — 29 features F01-F29
- SRS v2.0 (Ivo Albacete, 2026-07-01) — 31 RF + 11 RNF
- TO BE v2.1 (Facundo Coca, 2026-07-01) — visión objetivo
- AS IS v2.0 (Facundo Coca, 2026-07-01) — estado heredado
- Plan v1.1 (2026-07-01) — E1-E6 entregables
- Transcripciones de reuniones con David (2026-07-02)

---

# 🔴 IN PROGRESS

---

## Issue #62 — Identificar endpoints sin autenticación y protegerlos

*Meta: Facu · size M · Épica Seguridad y deuda técnica · En progreso 2/4 checkpoints*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Feature F03 del scope. El sistema heredado tiene múltiples rutas accesibles sin login o sin verificación de rol. Es una vulnerabilidad crítica identificada en el AS IS (sección 6). Complementa el hallazgo del refactor #75 sobre `cargar-stock-csv` sin auth (issue #86).

**Objetivo funcional:**
Al terminar, ningún endpoint de la app debe responder a un usuario no autenticado (salvo `/login` y `/logout`). Ningún endpoint de admin debe responder a usuarios sin rol `ADMIN`.

**Alcance:**
- [x] Revisar todas las rutas en `CODIGO_FUENTE/app.py` (post-refactor: revisar cada blueprint en `CODIGO_FUENTE/blueprints/`)
- [x] Identificar cuáles no tienen el decorador `@login_required` o similar
- [ ] Agregar protección a cada ruta desprotegida
- [ ] Probar que al intentar acceder sin login redirige al login

**Cómo abordarlo:**
- **Archivos clave:** todos los `CODIGO_FUENTE/blueprints/*.py`, `CODIGO_FUENTE/decorators.py` (ver decoradores disponibles: `login_required`, `permission_required`, `role_required`).
- **Patrón:** cada `@bp.route(...)` debe tener inmediatamente debajo `@login_required`. Las rutas de admin (ABM usuarios, cargar-stock-csv) deben tener `@role_required("ADMIN")`.
- **Sugerencia:** correr `grep -n "@.*_bp\.route" CODIGO_FUENTE/blueprints/*.py` para listar todas las rutas y verificar visual.

**Cómo validar (definition of done):**
1. Sin sesión, cualquier URL protegida devuelve redirect a `/login`.
2. Con sesión de rol no autorizado, la URL de admin devuelve HTTP 403.
3. La suite de rutas de auth (`/login`, `/logout`, `/`) sigue funcionando sin sesión.
4. Manualmente: cerrar sesión → intentar entrar a `/dml/`, `/stock/`, `/admin/`, `/api/verificar-stock/...` → todas deben redirigir.

**Referencias:** F03 del scope, RNF06 del SRS, sección 6 del AS IS.

---

## Issue #99 — Actualizar versiones de requerimientos

*Meta: Seba · size M · Épica Seguridad y deuda técnica · **MOVIDO A BACKLOG en sprint 2026-08-10 — Se retoma al arranque de E3 (2026-09-01)**·  0/3 checkpoints*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Deuda técnica. Flask 2.3.0 y Werkzeug 2.3.0 tienen CVEs conocidos. Python 3.7+ como mínimo declarado en el README es muy viejo (hoy la industria está en 3.11+). Actualizar deps mejora seguridad y compatibilidad futura, pero es riesgoso hacerlo mid-sprint porque puede romper el refactor recién hecho (#75).

**Diferido a E3** por decisión de mentor (10/08/2026): mid-sprint upgrade de Flask 2→3 en semana de entrega de E2 = riesgo de romper la demo. Con CI probado + E2 cerrado, se arranca E3 con red de seguridad y sin presión de fecha.

**Objetivo funcional:**
Al terminar, el sistema corre en Flask 3.x + Werkzeug 3.x + Python 3.11, sin regresiones en el flujo end-to-end.

**Alcance:**
- [ ] Actualizar Flask (2.3.0 → 3.x más reciente estable)
- [ ] Actualizar Werkzeug (2.3.0 → 3.x compatible con Flask elegido)
- [ ] Actualizar `runtime.txt` con Python 3.11.9 si no está
- [ ] Correr `pip install -r requirements.txt` local y verificar que no rompe
- [ ] Correr smoke test manual del flujo login → crear ficha → PDF → mail
- [ ] Evaluar testeo (armar 2-3 pytest básicos para no volver a estar sin red)

**Cómo abordarlo:**
- **Antes de empezar:** leer el changelog de Flask 3.x (https://flask.palletsprojects.com/en/3.0.x/changes/) para saber qué APIs deprecadas eliminaron.
- **Orden:** 1) branch propia; 2) actualizar `requirements.txt`; 3) `pip install`; 4) intentar levantar la app localmente; 5) fixear errores uno por uno con Claude Code + docs oficiales; 6) probar flujo end-to-end.
- **Riesgos conocidos:** `request.form.get()` cambió comportamiento, algunos `app.before_first_request` removidos, cambios en cookies handling.

**Cómo validar:**
1. `pip install -r requirements.txt` corre sin errores en Python 3.11.
2. `python -c "from app import app"` importa sin errores.
3. Login, creación de ficha, generación de PDF, envío de mail siguen funcionando.
4. CI en verde con las nuevas versiones (issue depende de CI activo, ver `MENTORIA/ci-setup.md`).

**Bloqueado por:** merge de CI (`chore/setup-ci`), cierre de E2.

---

# 🟡 IN REVIEW

---

## Issue #46 — Corregir impresión de ticket y ficha

*Meta: Ivo · size S · Épica Gestión de reparaciones · In review 3/3 checkpoints*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Bug identificado en el AS IS (sección 5.2). El botón de imprimir del ticket/ficha capturaba toda la pantalla en vez de imprimir solo la información relevante. Impacta feature F16 del scope (generación de PDF) y F12 (ticket).

**Objetivo funcional:**
Al hacer click en "Imprimir" desde un ticket o una ficha, se abre solo el contenido imprimible (sin menús, sin sidebar, sin sección de administración), formateado para papel.

**Alcance:**
- [x] Evaluar la impresión de "Vista completa"
- [x] Aplicar cambios según lo evaluado de "Vista completa"
- [x] Verificar que la impresión de solapa/etiqueta funciona correctamente

**Estado actual:**
Todos los checkpoints marcados. PR mergeable (commit `e6e6643` del 2026-08-07). Falta review de un segundo integrante para aprobar y mergear.

**Cómo validar:**
1. Abrir un ticket existente → click en imprimir → preview del navegador muestra solo la info del ticket.
2. Idem con una ficha.
3. El botón "Vista completa" ya no aparece (fue eliminado en el fix).

**Acción para cerrar:**
Facu o Seba revisa el PR asociado y approves. Mergea a `dev`. Cierra el issue.

---

## Issue #76 — Implementación del historial de 800 máquinas

*Meta: Seba · size L · Épica Seguridad y deuda técnica · In review 4/4 checkpoints*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Requerimiento surgido en reunión con David (2026-07-02). Existe un Excel histórico con >800 fichas de reparaciones anteriores al sistema. David confirmó que quiere migrarlas al DML para tener el historial completo consultable. Cubre parte del nuevo requerimiento "consultar historial de una máquina por N° de serie" que también surgió en esa reunión.

**Objetivo funcional:**
Existe un script Python reejecutable que toma como input uno o más CSVs (el de máquinas + la matriz de repuestos para validación cruzada), valida cada registro, inserta los válidos en la BD Postgres/Supabase, y genera reportes de qué se cargó y qué falló.

**Alcance:**
- [x] Analizar Excel, entender columnas y mapeo a las tablas de Postgres
- [x] Utilizar pandas y openpyxl para leer el xlsx desde Python
- [x] Entender la tabla destino en Supabase
- [x] Escribir script de carga limpio antes de ejecutarlo en producción

**Refinamiento acordado con mentor (2026-08-10) — NO ES un checklist para marcar sino la spec real del script:**

El primer intento fue manual (leer CSV con IA + generar N `INSERT INTO`). Eso NO es un script de carga inicial. La spec real:

1. **Script Python reejecutable:** `python cargar_historico.py maquinas.csv matriz.csv`
2. **Toma múltiples CSVs de input:** al menos el de máquinas (con N° ficha, cliente, serie, modelo, etc.) y una matriz de repuestos contra la cual validar códigos.
3. **Validación por fila:**
   - Carga la matriz en un dict de lookup en memoria.
   - Recorre el CSV de máquinas fila por fila.
   - Valida cada campo (formato, referencias cruzadas contra matriz, reglas de negocio).
   - Arma dos listas: `to_insert` (válidos) y `errors` (inválidos con detalle `{fila, columna, tipo_error}`).
4. **Inserción idempotente:**
   - Usa `INSERT ... ON CONFLICT (n_ficha) DO NOTHING` (Postgres). Requiere que la tabla `dml_fichas` (o equivalente) tenga UNIQUE constraint en `n_ficha`.
   - Correr el script 5 veces con el mismo CSV = el mismo resultado en la BD. No hay duplicados.
5. **Reportes de salida:**
   - Consola: `X registros procesados, Y insertados, Z skipped (ya existían), W errores`.
   - Archivo: `errores_YYYY-MM-DD-HHMM.csv` con los registros inválidos + descripción del error. Este archivo es lo que Seba le manda al cliente para que corrija.
6. **Política de conflictos:** DO NOTHING (skip). Si el cliente quiere corregir un registro ya cargado, se borra manualmente de la BD antes de re-correr. Es más simple que UPDATE y evita sobreescribir accidental.
7. **Uso:** Seba lo corre primero en Supabase-dev con datos de prueba. Después de validar comportamiento, lo corre en Supabase-prod con el CSV real (una única vez inicial, y iteraciones subsiguientes si el cliente corrige errores).

**Cómo abordarlo:**
- **Archivos:** `CODIGO_FUENTE/scripts/cargar_historico.py` (nuevo).
- **Libs:** `pandas` (ya está), `psycopg2-binary` (ya está).
- **Estructura:** función `validar_fila(row, matriz) -> (valid: bool, errors: list)`. Función `main()` que orquesta lectura, loop, inserción bulk, reportes.
- **Testing:** Seba genera un CSV de prueba con 5 registros (3 válidos, 2 inválidos), corre el script contra Supabase-dev, verifica que quedan 3 insertados y 2 en el archivo de errores.

**Cómo validar (definition of done):**
1. El script corre en local sin errores contra un CSV de prueba.
2. Es idempotente: corriéndolo 2 veces seguidas con el mismo CSV, la segunda vez reporta "X skipped" y no duplica.
3. Los registros marcados como error salen en el CSV de errores con descripción legible.
4. Documentado en `CODIGO_FUENTE/scripts/README.md` cómo usarlo.

**Referencias:** Reunión David 2026-07-02, mapeo de columnas ya trabajado en la etapa de análisis.

---

## Issue #95 — Migrar desde SQLite a PostgreSQL ~ Fase 2

*Meta: Seba · size S · Épica Seguridad y deuda técnica · In review 2/2 checkpoints · PR abierto*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Feature F01 del scope. Fase 2 de la migración SQLite → PostgreSQL sobre Supabase. La Fase 1 (issue #61) migró el schema; la Fase 2 modifica los scripts Python que hablan con la BD para que usen sintaxis y drivers de Postgres.

**Objetivo funcional:**
Todo el código Python que hace queries usa `psycopg2` y sintaxis de PostgreSQL (`%s` para placeholders, no `?`; timestamps con timezone; etc.). El sistema arranca conectado a Supabase-dev y todas las operaciones (CRUD de fichas, tickets, stock, usuarios) funcionan.

**Alcance:**
- [x] Modificar los scripts SQLite3 conectados al `app.py`
- [x] Verificar funcionamiento en Supabase

**Estado:**
PR abierto contra `dev`. Requiere review + merge. Bloquea:
- Setup completo de CI (el `import check` del CI necesita esta Fase 2 mergeada para no fallar).
- Release a `main` (el sprint E2 termina con `dev` → `main`).

**Cómo validar (definition of done):**
1. PR aprobado por otro integrante.
2. Mergeado a `dev`.
3. Verificado: arrancar la app localmente con `DATABASE_URL` apuntando a Supabase-dev, hacer login, crear una ficha, verificar que persiste tras reiniciar el server.
4. Al cierre del sprint (28/08 EOD), incluido en el PR `dev` → `main` que ejecuta Seba como release manager.

**Referencias:** F01 del scope, RNF03 del SRS.

---

# 🟢 READY

---

## Issue #54 — Corregir ingreso de máquinas en RAYPAC

*Meta: Facu · size L · Épica Gestión de reparaciones · Ready 0/8 checkpoints · **Core técnico de E2***

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Cubre las features F05, F06, F07, F08, F09 del scope y RF01-RF14 del SRS. Es el core técnico del entregable E2 del Plan v1.1 — sin esto, no hay demo para David el 29/08. El sistema heredado tiene el formulario básico pero faltan campos, validaciones y el flujo de freezing correcto.

**Objetivo funcional:**
Un usuario con rol RAYPAC puede loguearse, abrir el formulario de nuevo ingreso, completarlo con todos los campos requeridos por el scope, asignar número de remito, freezar el registro, y ver que la máquina aparece del lado DML como "pendiente de recepción".

**Alcance:**
- [ ] Agregar campo "Contacto del cliente" (solo visible para RAYPAC y ADMIN — ver RF04)
- [ ] Agregar campo "Mail del cliente" (solo visible para RAYPAC y ADMIN — ver RF04)
- [ ] Implementar desplegable de clientes con lista completa + autoaprendizaje (guarda clientes nuevos — RF03)
- [ ] Implementar desplegable de modelos de máquina (ITA25, ITA24, CT20, etc. — 7 modelos ITA + 3 CT + 3 CTT según AS IS)
- [ ] Implementar desplegable de tipo de máquina (A batería, manual, neumática, otro — RF05)
- [ ] Implementar desplegable de comercial responsable con mail asociado automático (5 comerciales según David: Leonardo Bastagel, Luciana, Ezequiel Pacheco, Daniela Sofio, +1 a confirmar — RF08)
- [ ] Validar que no se pueda freezar sin ingresar número de remito (RF10)
- [ ] Permitir ingresar solo los últimos 4 dígitos del remito y que el sistema complete formato `00001-00004222` (RF09)

**Cómo abordarlo:**
- **Archivos clave:**
  - `CODIGO_FUENTE/blueprints/raypac.py` — rutas `/raypac/*`
  - `CODIGO_FUENTE/templates/raypac/new.html` — form de ingreso (verificar el nombre exacto)
  - `CODIGO_FUENTE/templates/raypac/1.html` o similar — paso de remito
  - `CODIGO_FUENTE/db/schema-postgres.sql` — si hay campos nuevos en la tabla `raypac_entries`
- **Orden sugerido:**
  1. Revisar el schema actual y ver qué campos ya existen y cuáles hay que agregar.
  2. Si hay campos nuevos → migration SQL + actualizar tabla en Supabase-dev.
  3. Agregar los campos al template + al handler del form en el blueprint.
  4. Implementar los desplegables (clientes, modelos, tipo máquina, comercial).
  5. Implementar validación de remito con formateo automático (parte cliente en JS + validación server).
  6. Verificar que el freezing funciona: guardar registro, asignar remito, click "confirmar envío" → registro bloqueado, aparece del lado DML.
- **Consideraciones:**
  - El desplegable de clientes con autoaprendizaje necesita: al escribir un cliente nuevo, sistema pregunta "¿guardar este cliente?" y lo persiste para próximas veces.
  - El mail del comercial se autocompleta cuando eligen el comercial del desplegable (mapping estático o tabla `comerciales`).
  - Los campos de contacto/mail cliente deben tener control de visibilidad por rol (server-side + hidden en HTML según rol).

**Cómo validar (definition of done):**
1. Login como RAYPAC → abrir `/raypac/new` → llenar el form → guardar → asignar remito con 4 dígitos → confirmar freezing.
2. El registro queda visible como "pendiente" del lado DML.
3. El registro NO puede editarse por RAYPAC después del freezing (solo por ADMIN con desbloqueo por 4 dígitos remito — issue relacionado).
4. Los 5 flujos consecutivos completos deben pasar sin HTTP 500 ni bloqueos (criterio 10.1 del scope).
5. Un usuario con rol DML no ve los campos de contacto/mail cliente (RF04).

**Referencias:** F05-F09 del scope, RF01-RF14 del SRS, sección 5.1 del AS IS.

---

## Issue #59 — Configurar alertas de stock bajo

*Meta: Ivo · size S · Épica Gestión de stock · Ready 0/3 checkpoints*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Feature F20 del scope. En la reunión con David (2026-07-02) él pidió explícitamente que además del indicador visual por color, cuando el stock esté crítico se dispare un mail automático al encargado de gestión de repuestos: *"que el sistema sea intuitivo y diga: mirá que queda uno, mirá que no queda ninguno"*. Es una extensión de F20 documentada por David en la reunión.

**Objetivo funcional:**
Cuando el stock de un repuesto cae a nivel crítico (según umbrales del scope F20: rojo=0, naranja=1, amarillo=2, verde ≥3), el sistema envía automáticamente un email al usuario responsable de repuestos informando qué repuesto está bajo y en qué cantidad quedó.

**Alcance:**
- [ ] Verificar que las alertas de stock crítico (≤2 unidades según F20) funcionan correctamente en la UI (colores)
- [ ] Implementar envío de mail automático al bajar el stock a niveles críticos
- [ ] Verificar que RAYPAC / el encargado de repuestos recibe la notificación con los repuestos faltantes

**Cómo abordarlo:**
- **Archivos clave:**
  - `CODIGO_FUENTE/services/stock.py` — ya tiene `check_stock_alert` (verificar qué hace hoy)
  - `CODIGO_FUENTE/services/mail.py` — para el envío
  - `CODIGO_FUENTE/blueprints/dml.py` o donde se descuente stock al agregar repuesto a ficha
- **Orden:**
  1. Leer `services/stock.py::check_stock_alert` y entender qué evalúa hoy.
  2. Ubicar los puntos del código donde se descuenta stock (agregar repuesto a ficha, envío desde RAYPAC).
  3. Después del descuento, llamar `check_stock_alert(codigo_repuesto)`. Si retorna crítico, disparar mail.
  4. Definir a quién va el mail — hoy no está claro. Ver con Matías en la daily si crear una tabla `usuarios_notificaciones` o si va a un mail fijo tipo `repuestos@dml.com.ar` (consultar a David si es que existe).
  5. Usar la plantilla de mail existente en `services/mail.py` como base.
- **Consideraciones:**
  - No mandar mail en cada carga si ya se mandó recientemente por el mismo repuesto (evitar spam). Considerar cooldown de 24 hs.
  - El body del mail debe incluir: código, descripción, cantidad remanente, ubicación física.

**Cómo validar (definition of done):**
1. Cargar un repuesto a una ficha que deja el stock en 0 → el encargado recibe mail.
2. Cargar de nuevo el mismo repuesto en menos de 24 hs → no llega otro mail (cooldown).
3. Volver a subir el stock (envío desde RAYPAC) → el próximo descenso a crítico dispara mail nuevo.

**Referencias:** F20 del scope, transcripción reunión David 2026-07-02 (sección Stock).

---

## Issue #85 — Unificar los 3 generadores de PDF

*Meta: Ivo · size M · Épica Seguridad y deuda técnica · Ready · Deuda técnica del refactor #75*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Hallazgo del refactor #75. El análisis detectó 3 implementaciones distintas de generación de PDF de ficha:
- `generar_ficha_pdf` en el viejo `app.py:1043`
- `generate_ficha_pdf` en el viejo `app.py:3337`
- `generate_ficha_pdf_new` en `CODIGO_FUENTE/pdf_generator_new.py` (nunca integrado)

Post-refactor, la lógica quedó parcialmente en `services/pdf.py`. Hay que decidir cuál queda como canónica, borrar las otras dos, dejar todo llamando a una sola función. Es deuda técnica bloqueante para E3 (Módulo DML Tickets incluye la generación de PDF — feature F16 del scope). Si no se unifica ahora, en E3 hay que hacerlo igual pero bajo presión de fecha.

**Objetivo funcional:**
Existe una única función de generación de PDF de ficha en `services/pdf.py`. Todos los endpoints que generan PDF la llaman a ella. Los archivos `pdf_generator_new.py` y las funciones duplicadas dejan de existir.

**Alcance:**
- [ ] Leer las 3 implementaciones y comparar diferencias (features, calidad de output, dependencias)
- [ ] Decidir cuál queda como canónica (probablemente la de `services/pdf.py` post-refactor, verificar)
- [ ] Mover la implementación canónica a `services/pdf.py` si no está ahí ya, con la firma limpia
- [ ] Actualizar todos los endpoints que generan PDF para llamar a esta única función (buscar `grep -rn "generar_ficha_pdf\|generate_ficha_pdf" CODIGO_FUENTE/`)
- [ ] Borrar `CODIGO_FUENTE/pdf_generator_new.py` completo
- [ ] Borrar las funciones duplicadas remanentes (si las hay)
- [ ] Actualizar la config de ruff en `pyproject.toml` para sacar la exclusión de `pdf_generator_new.py`
- [ ] Probar generación de PDF end-to-end desde el flujo real (crear ficha → finalizar → PDF)

**Cómo abordarlo:**
- **Archivos clave:**
  - `CODIGO_FUENTE/services/pdf.py` — donde debería quedar la implementación canónica
  - `CODIGO_FUENTE/pdf_generator_new.py` — a borrar
  - `CODIGO_FUENTE/blueprints/dml.py`, `blueprints/admin.py`, `blueprints/tickets.py` — buscar llamados
- **Orden sugerido:**
  1. `grep -rn "def.*pdf\|from.*pdf" CODIGO_FUENTE/` para mapear todo lo relacionado.
  2. Leer las 3 implementaciones lado a lado. Ver cuál genera el output más limpio (probar cada una).
  3. Consolidar en `services/pdf.py` con la firma `generar_pdf_ficha(ficha_id: int) -> bytes`.
  4. Actualizar cada callsite para usar la nueva función.
  5. Borrar archivos y funciones obsoletas.
  6. Probar el flujo real de generación de PDF (login → crear ficha → finalizar → descargar PDF).
- **Consideraciones:**
  - Ojo con `pycairo` que trae reportlab — verificar que después de borrar `pdf_generator_new.py` el CI sigue en verde con la config actual.
  - Si Ivo se atrasa con las otras tareas del sprint, este issue es el más deferrable a E3 (deuda técnica no bloqueante para E2).

**Cómo validar (definition of done):**
1. `grep -rn "generar_ficha_pdf\|generate_ficha_pdf\|pdf_generator_new" CODIGO_FUENTE/` devuelve **solo** líneas dentro de `services/pdf.py`.
2. El archivo `pdf_generator_new.py` no existe.
3. Login → crear ficha → finalizar → generar PDF → abrir PDF → visualmente correcto.
4. CI en verde.

**Referencias:** Issue #75 (refactor origen), hallazgo documentado en `MENTORIA/plan-ordenamiento-2026-07-06.md`.

---

# ⚪ BACKLOG

---

## Issue #44 — Corregir estados de reparación

*Meta: sin asignar · size M · Épica Gestión de reparaciones · Backlog 0/4 · Candidato E3*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Feature F14 del scope y RF20 del SRS. Los estados de reparación existen en el sistema heredado pero están incompletos (falta "A la espera de revisión") y los colores no matchean lo definido en el Excel de David.

**Objetivo funcional:**
Al ver la lista de fichas de reparación, cada una muestra su estado con el color exacto acordado, y el técnico puede transicionar entre estados. El estado "pendientes RAYPAC" se resalta visualmente cuando llega una máquina nueva.

**Alcance:**
- [ ] Agregar estado "A la espera de revisión" (blanco)
- [ ] Verificar que todos los estados están: En reparación (celeste), A la espera de repuestos (naranja), Lista para retirar (amarillo), Entregada (verde)
- [ ] Implementar colores por estado como en el Excel de David
- [ ] Resaltar casillero de pendientes cuando RAYPAC envía una máquina (usuario técnico)

**Cómo abordarlo (para cuando arranque en E3):**
- **Archivos:** `CODIGO_FUENTE/blueprints/dml.py`, `CODIGO_FUENTE/templates/dml/fichas.html` (verificar nombre), CSS relacionado.
- Definir los estados como constantes en algún módulo compartido (`CODIGO_FUENTE/constants.py` si no existe, crearlo).
- Estilos CSS por clase de estado, no inline.

**Referencias:** F14 del scope, RF20 del SRS, reunión David 2026-07-02.

---

## Issue #45 — Gestionar devolución de máquinas

*Meta: sin asignar · size L · Épica Gestión de reparaciones · Backlog 0/4 · Candidato E3-E4*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Feature relacionada con F09 del scope. En la reunión con David (2026-07-02) se acordó que RAYPAC debe poder registrar el acuse de recibo de máquinas ya reparadas que reingresan físicamente a su empresa. Es el cierre del flujo del ciclo de vida.

**Objetivo funcional:**
RAYPAC ve una sección "Máquinas entregadas por DML" con cada una marcada con un botón "OK" y un campo de fecha de reingreso. Al hacer click, la máquina pasa a estado final y queda registrado el acuse de recibo.

**Alcance:**
- [ ] Implementar sección de "Máquinas entregadas" en vista RAYPAC
- [ ] Agregar formulario simple de acuse de recibo (fecha de reingreso + botón OK)
- [ ] Verificar que DML puede registrar la entrega de la máquina
- [ ] Verificar que RAYPAC puede ver el estado de la máquina en todo momento

**Cómo abordarlo (para E3-E4):**
- Nueva vista en `blueprints/raypac.py` (`/raypac/entregadas` o similar).
- Nueva columna `fecha_reingreso_raypac` en la tabla de fichas.
- Filtro: mostrar solo fichas con estado "Entregada" que RAYPAC aún no acusó recibo.

**Referencias:** F09 del scope, RF13 del SRS.

---

## Issue #47 — Mejorar visibilidad entre roles

*Meta: sin asignar · size XL · Épica Gestión de reparaciones · Backlog 0/5 · Candidato E3-E4*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Features F09, F10 del scope y RF12, RF14 del SRS. Actualmente los roles RAYPAC y DML tienen visibilidad muy limitada de lo que hace el otro. David pidió mejor comunicación entre lados: RAYPAC ver el estado real de reparación en tiempo real; DML resaltar cuando RAYPAC envió algo nuevo; separar envíos de máquinas vs envíos de repuestos en cada solapa.

**Objetivo funcional:**
Cada rol tiene una vista clara de lo que hace el otro dentro de su alcance, con separación clara entre "máquinas" y "repuestos" en las solapas de envíos.

**Alcance:**
- [ ] RAYPAC: puede ver en tiempo real el estado de sus fichas en DML
- [ ] RAYPAC: puede ver ticket generado por DML e imprimirlo o recibirlo por mail
- [ ] Técnico DML: casillero de pendientes se resalta cuando RAYPAC envía una máquina
- [ ] RAYPAC: en solapa Envíos discriminar entre máquinas enviadas y repuestos enviados
- [ ] Técnico DML: en pendientes RAYPAC discriminar entre máquinas y repuestos

**Cómo abordarlo (para E3-E4):**
- XL porque toca templates de ambos lados + JS + queries.
- Recomendable partir en 2-3 sub-issues cuando se planifique.
- **Archivos:** blueprints `raypac.py` y `dml.py`, templates de ambos, servicios de notificaciones (si hace falta polling).

**Referencias:** F09, F10 del scope, RF12, RF14 del SRS.

---

## Issue #51 — Definir hosting y persistencia de datos

*Meta: sin asignar · sin size · Épica Infraestructura y deploy · **CERRAR COMO DONE — decisión ya tomada***

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Este issue se creó cuando aún no estaba definido dónde iba a correr el sistema. La decisión ya se tomó en el sprint anterior (documentada en `MENTORIA/plan-ordenamiento-2026-07-06.md` y en la conversación de infraestructura 2026-07-02):

- **Hosting:** Render (plan gratuito, 2 servicios: `raypac-dev` y `raypac-prod`).
- **Base de datos:** PostgreSQL en Supabase (plan gratuito, 2 proyectos separados dev/prod).
- **Dominio:** subdominios sobre `dmlelectricidadind.com.ar` del cliente (`raypac-dev.dmlelectricidadind.com.ar` y `raypac-prod.dmlelectricidadind.com.ar`).
- **Persistencia:** Postgres/Supabase (migración cubierta por issues #61 y #95).

**Acción para cerrar este issue:**
Cerrarlo con comment: *"Decisión tomada: Render + Supabase (planes gratuitos). Ver MENTORIA/plan-ordenamiento-2026-07-06.md y issue #53 para el detalle del dominio."*

---

## Issue #52 — Implementar sistema de backups

*Meta: sin asignar · size L · Épica Infraestructura y deploy · Backlog 0/4 · Candidato E5-E6*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Requerimiento explícito de David en la reunión 2026-07-02: *"a mí no me gusta que esté todo en el mismo servicio. Se te cae el original y se te cae la copia."* Supabase provee backup diario automático dentro de su plataforma, pero David quiere una **segunda copia fuera de Supabase** (local en la empresa, disco externo o NAS).

**Objetivo funcional:**
Existe un mecanismo (manual o semi-automático) para exportar el estado completo de la BD Postgres a un archivo que se pueda descargar y guardar fuera de Supabase. Idealmente hay también un mecanismo para importar/restaurar.

**Alcance:**
- [ ] Implementar botón "Exportar backup" en la UI (solo ADMIN)
- [ ] Implementar botón "Importar backup" en la UI (solo ADMIN)
- [ ] Documentar procedimiento de backup manual (cuándo hacerlo, dónde guardarlo)
- [ ] Considerar automatización: un cron diario que exporte y suba a un lugar externo (Google Drive del cliente, S3, o similar)

**Cómo abordarlo (para E5-E6):**
- La opción más simple: usar `pg_dump` con connection string de Supabase-prod, generar un `.sql`, disponibilizar como descarga.
- La restauración es más delicada — considerar si es realmente necesario o solo se documenta el procedimiento manual con `pg_restore`.
- Endpoint `/admin/backup/export` y `/admin/backup/import` en blueprint admin.
- **Consultar con David** si prefiere que el backup se descargue on-demand desde la UI, o que se genere automático y llegue por mail cada día.

**Referencias:** Requerimiento David reunión 2026-07-02.

---

## Issue #55 — Corregir flujo de ticket y ficha DML

*Meta: sin asignar · size XL · Épica Gestión de reparaciones · Backlog 0/7 · Core técnico de E3*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Cubre features F10, F11, F12, F13 del scope y RF15-RF19 del SRS. Es el core técnico de E3 (Módulo DML — Tickets y flujo de reparación, entregable 2026-09-19). El sistema heredado tiene el flujo básico pero con nombres inconsistentes ("Crear Ficha" en vez de "Crear Ticket"), formato de ticket incorrecto, y campos duplicados.

**Objetivo funcional:**
Un técnico DML puede recibir una máquina freezada por RAYPAC, completar la inspección visual, generar un ticket con el formato correcto (`TK-{n_serie}`), armar la ficha de reparación, y avanzar los estados hasta "Lista para entregar".

**Alcance:**
- [ ] Renombrar "Crear Ficha" por "Crear Ticket" en toda la UI
- [ ] Ajustar número de ticket al formato `TK-{numero_de_serie}` (ej: `TK-256487899`)
- [ ] Asegurar que el ticket se genera antes de la ficha
- [ ] Ajustar campos del ticket según planilla DML (fecha ingreso, técnico, observaciones, estado del equipo)
- [ ] Verificar que al generar ticket se envía mail automático al comercial de RAYPAC
- [ ] Verificar que RAYPAC puede ver el ticket generado
- [ ] Asegurar que la ficha solo se puede crear después del ticket

**Cómo abordarlo (para E3):**
- **XL** — se recomienda cortarlo en 2-3 sub-issues antes de arrancar.
- Empezar con el renombrado (rápido y desbloquea confusión).
- Después el flujo lógico: ticket → ficha → mail.
- Después la inspección visual con los componentes desplegables (RF17 tiene la lista exacta).

**Referencias:** F10-F13 del scope, RF15-RF19 del SRS.

---

## Issue #56 — Gestión de stock

*Meta: sin asignar · sin size · Épica Gestión de stock · **CERRAR COMO DUPLICADO***

**DESCRIPCIÓN (copy-paste al issue):**

Este issue es un placeholder vacío. La gestión de stock ya está desglosada en issues concretos:

- **#57** — Corregir envío de repuestos desde RAYPAC (flujo de envíos)
- **#58** — Gestionar stock de repuestos en DML (verificación y ABM)
- **#59** — Configurar alertas de stock bajo (notificación)

**Acción para cerrar:**
Cerrarlo con comment: *"Duplicado. Trabajo desglosado en #57, #58, #59."*

---

## Issue #57 — Corregir envío de repuestos desde RAYPAC

*Meta: sin asignar · size XL · Épica Gestión de stock · Backlog 0/6 · Candidato E4*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Feature F24 del scope y RF30 del SRS. Flujo completo de envío de repuestos desde RAYPAC hacia DML. Es parte del core de E4 (Módulo Stock, entregable 2026-10-10).

**Objetivo funcional:**
Un usuario RAYPAC arma un envío de repuestos con número de remito, lo despacha. DML recibe físicamente, verifica contra el remito, confirma recepción en el sistema, y el stock se actualiza automáticamente.

**Alcance:**
- [ ] RAYPAC ve lista completa de repuestos y puede tildar los que envía con cantidad
- [ ] RAYPAC puede agregar código manualmente si el repuesto no está en la lista
- [ ] RAYPAC debe ingresar número de remito al enviar repuestos
- [ ] RAYPAC puede editar el envío (desfreezar) para corregir errores
- [ ] DML ve el envío y confirma recepción chequeando que los repuestos coincidan con el remito
- [ ] Al confirmar recepción el stock se actualiza automáticamente

**Cómo abordarlo (para E4):**
- **XL** — cortar en sub-issues cuando se planifique.
- Estructura análoga al ingreso de máquinas: form + freezing + acuse por el otro lado.
- **Archivos:** `blueprints/envios.py`, `blueprints/stock.py`, templates relacionados.

**Referencias:** F24 del scope, RF30 del SRS.

---

## Issue #58 — Gestionar stock de repuestos en DML

*Meta: sin asignar · size L · Épica Gestión de stock · Backlog 0/5 · Candidato E4*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Cubre features F18, F19, F20, F22 del scope y RF24-RF29 del SRS. Verificación y ABM del stock desde el lado DML. Parte de E4.

**Objetivo funcional:**
DML puede verificar el stock actual, agregar/editar repuestos con contraseña de admin, exportar el listado a CSV, y ver estadísticas de uso.

**Alcance:**
- [ ] Verificar que el stock se descuenta automáticamente al cargar repuestos en una ficha
- [ ] Verificar que se pueden agregar nuevos repuestos con contraseña
- [ ] Verificar que se pueden editar repuestos existentes con contraseña
- [ ] Verificar exportación a CSV funciona correctamente
- [ ] Verificar estadísticas de uso de repuestos

**Cómo abordarlo (para E4):**
- Es mayormente **verificación** del código heredado + refactor. Empezar leyendo `blueprints/stock.py` y `services/stock.py`.
- Los que fallen o falten, agregar checkbox de "implementar".

**Referencias:** F18-F22 del scope, RF24-RF29 del SRS.

---

## Issue #86 — Proteger cargar-stock-csv con auth

*Meta: sin asignar · size XS · Épica Seguridad y deuda técnica · Backlog · Post-#62*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Hallazgo puntual del refactor #75. El endpoint `/admin/cargar-stock-csv` no tiene los decoradores `@login_required` ni `@role_required("ADMIN")`. Es un hueco de seguridad. Está relacionado con el trabajo de #62 (que resuelve el mismo tipo de problema en otros endpoints).

**Objetivo funcional:**
El endpoint `/admin/cargar-stock-csv` solo es accesible por usuarios con rol ADMIN autenticados.

**Alcance:**
- [ ] Localizar el endpoint en `CODIGO_FUENTE/blueprints/admin.py`
- [ ] Agregar `@login_required` y `@role_required("ADMIN")` sobre la ruta
- [ ] Probar que un usuario no admin recibe 403 al forzar la URL

**Cómo abordarlo:**
- Muy chico (XS = 2h max).
- Puede resolverse como parte de #62 o como un PR aparte.
- Si se resuelve en el mismo PR de #62, cerrar este issue con comment "resuelto en #62".

**Referencias:** F03 del scope, hallazgo del refactor #75.

---

## Issue #87 — Actualizar código para escribir en logs_auditoria

*Meta: sin asignar · size M · Épica Seguridad y deuda técnica · Backlog · Candidato E5*

**DESCRIPCIÓN (copy-paste al issue):**

**Contexto:**
Feature F28 del scope y RNF07 del SRS. Durante la Fase 1 de Postgres (#61) Seba creó la tabla `logs_auditoria` con el schema nuevo (UUID, timestamptz, id_usuario NOT NULL, tipo_accion). Pero el código Python que escribe en esa tabla sigue con el formato viejo. Hay que adaptar el código para escribir en el schema nuevo.

**Objetivo funcional:**
Cada operación de escritura (INSERT/UPDATE/DELETE) en tablas de negocio deja un registro en `logs_auditoria` con el formato: `id_log` UUID, `fecha_hora` timestamptz, `id_usuario` NOT NULL, `tipo_accion`, `tabla_afectada`. No se permiten registros anónimos.

**Alcance:**
- [ ] Localizar dónde el código actual escribe en auditoría (grep en blueprints y services)
- [ ] Actualizar la firma de la función de auditoría al schema nuevo
- [ ] Asegurar que TODAS las operaciones de escritura pasan por esta función
- [ ] Test: crear una ficha, verificar que aparece 1 registro en `logs_auditoria` con los campos correctos

**Cómo abordarlo (para E5):**
- **Archivos:** `CODIGO_FUENTE/services/` (buscar servicio de auditoría o crearlo), blueprints varios.
- Considerar un decorador `@audit_log(accion, tabla)` para aplicar en cada endpoint de mutación — más limpio que llamar manualmente en cada handler.
- **Bloqueado por:** merge de #75 (que está Done, así que en realidad ya no está bloqueado).

**Referencias:** F28 del scope, RNF07 del SRS.

---

# 📋 Resumen para el que actualiza los issues

Total: **17 issues** a actualizar con estas descripciones:

| Estado | Cantidad | Issues |
|---|---|---|
| In progress | 2 | #62, #99 (con nota de diferido) |
| In review | 3 | #46, #76, #95 |
| Ready | 3 | #54, #59, #85 |
| Backlog | 9 | #44, #45, #47, #52, #55, #57, #58, #86, #87 |
| **Cerrar** | 2 | #51 (Done con comment), #56 (Duplicado con comment) |

**Orden sugerido de actualización:**
1. **Cerrar primero** #51 y #56 (rápido, saca ruido del board).
2. **Actualizar Ready y In Progress** (impacta trabajo del sprint actual).
3. **Actualizar In Review** (Seba/Ivo ya los conocen, es cosmética pero deja el histórico limpio).
4. **Actualizar Backlog** al final (impacta trabajo futuro, no urge esta semana).

Tiempo total estimado: 45-60 minutos mecánicos.
