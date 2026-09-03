# Contexto — Software de Gestión DML

Este documento es para que Claude Code tenga contexto completo del proyecto sin que
haya que reexplicarlo. Actualizarlo cuando cambie algo importante.

## 🔖 Checkpoint (leer primero, mantener actualizado)

**Por qué existe:** Facu trabaja desde dos máquinas distintas, y la memoria local de
Claude Code (`~/.claude/.../memory/`) vive en el home de cada máquina — no viaja de
una a otra. Lo único que sí viaja es lo que está versionado en este repo. Esta
sección es la fuente de verdad de "qué estábamos haciendo y por dónde quedamos": se
actualiza al cierre de cada sesión (o al cambiar de tarea en curso) y sigue el mismo
flujo que cualquier otro cambio — rama chica `docs/checkpoint-...`, commit, push, y
avisarle a Facu para que abra y mergee el PR contra `dev`. Hasta que ese PR no esté
mergeado, el checkpoint actualizado vive solo en esa rama, no en `dev` — no dar la
tarea de "guardar contexto" por terminada hasta la confirmación del merge.

**Regla para Claude Code:** al arrancar cualquier sesión, leer esta sección antes de
asumir contexto de nada más.

- **Última actualización:** 2026-09-03, sesión en curso.
- **Los 4 PRs de la sesión del 2026-08-31 que en el checkpoint anterior
  figuraban "sin mergear" ya están mergeados a `dev`** (confirmado al
  arrancar hoy: `fix/132-reemplazar-confirm-nativos` #163,
  `fix/132-confirm-cliente-nuevo-raypac` #165,
  `fix/161-162-tabla-notificaciones-feedback` #164, más el checkpoint
  mismo #166) — Facu los revisó y mergeó después del cierre de esa sesión.
  De paso se mergeó también `refactor/85-unificar-los-3-generadores-de-pdf`
  de Ivo (#167, issue #85), sin relación con el #132.
- **Hallazgo de proceso (importante, corregido hoy): `Closes #N` nunca
  autocierra un issue en este repo.** El default branch es `main`, todo se
  mergea a `dev`, y GitHub solo dispara el auto-close cuando el merge es a
  la default branch del repo — nunca pasa acá. Confirmado revisando el
  timeline de issues: #127 lo había cerrado Facu a mano (no fue automático,
  aunque el checkpoint de su momento lo diera por hecho), y **#156, #157,
  #161, #162 seguían `OPEN` en GitHub** pese a tener sus PRs (#160, #164)
  ya mergeados a `dev` con `Closes #N` bien escrito en el body. La nota que
  había quedado archivada sobre el #44 ("el PR usó `Refs` en vez de
  `Closes`") atribuía esto a un detalle de wording — es la causa
  equivocada, el problema es estructural y le pasa a **todos** los PRs.
  **Acción tomada:** se cerraron a mano #156, #157, #161 y #162 (los 4 ya
  estaban resueltos y mergeados, solo desactualizados en GitHub), y se
  agregó una nota permanente a la sección "Branches y flujo de PRs" de
  este archivo con la práctica nueva: cerrar el issue a mano
  (`gh issue close N`) como parte del mismo paso de confirmar que un PR
  quedó mergeado, no asumir que Github lo hace solo.
- **Tarea de la sesión: #132, ítem grande (unificar los ~24 `<select>`
  nativos al patrón del desplegable de Cliente) — sub-tanda de 4 PRs
  ✅ COMPLETA, los 4 mergeados a `dev` en el orden correcto (2026-09-03):**
  Componente reutilizable `enhanceSelect()` agregado a `base.html` +
  estilos en `style.css`: cualquier `<select class="js-select-enhance">`
  se pilotea desde un botón + `dropdown-menu` de Bootstrap en vez del
  popup nativo del SO — opt-in por template (rollout gradual), el
  `<select>` real sigue en el DOM (oculto con `opacity:0`, no
  `display:none`, para que `required`/`reportValidity()` lo sigan
  encontrando) y es el que viaja en el submit, sin tocar nada de backend.
  1. `feature/132-unificar-select-usuario_form` (el componente + 1er caso,
     select de Rol en `usuario_form.html`) — **PR #172, mergeado.**
  2. `feature/132-unificar-select-usuario_edit` (mismo select de Rol en
     `usuario_edit.html`, caso con clase `form-control` y opción
     pre-seleccionada) — **PR #173, mergeado.**
  3. `feature/132-unificar-select-envios-tickets` (`envios_form.html` +
     el filtro de Estado en `tickets_list.html`) — **PR #174, mergeado.**
  4. `feature/132-unificar-select-dml_edit` (los 12 selects de "partes del
     equipo" + el de "Estado de la Reparación") — **PR #175, mergeado.**
     Probado en vivo el 2026-09-03 en `/dml/4/edit` (ficha #504 de
     prueba) antes de pushear: el dropdown abre con estilo Bootstrap (no
     el popup nativo), la selección sincroniza el `<select>` oculto
     (confirmado por JS), el submit persiste el valor bien (`CUBRE
     FEEDWHEEL` → `OK`, verificado en la vista de solo lectura después de
     guardar), y "MÁQUINA ENTREGADA" sigue sin aparecer como opción en
     "Estado de la Reparación" (fix del #157 no se rompió). Primer caso
     con selects sin ninguna clase de Bootstrap (el template estila
     `<select>` con CSS propio) - se le agregó una base visual propia a
     `.dml-select-toggle` en `style.css` (calcada de los valores por
     defecto de `.form-select` de Bootstrap 5.3) para que el componente se
     vea bien la tenga o no.
  - **Gotcha del día, para la próxima vez que se apilen ramas así:** los
    PRs #173 y #174 se mergearon a `dev` mientras la rama 4 (#175)
    todavía los tenía apilados encima sin mergear - como el merge a `dev`
    generó commits nuevos (no fast-forward), la rama 4 quedó con historia
    divergente y GitHub marcó el PR #175 en conflicto (`CONFLICTING`),
    sin ni siquiera correr el CI. Se resolvió con `git merge origin/dev`
    en la rama 4 (único conflicto real: unas líneas de CSS de
    `.dml-select-toggle` que las ramas 2/3 no tenían), corriendo los 2
    checks del CI en local antes de pushear (`ruff check CODIGO_FUENTE/` +
    el import-check de la app), y recién ahí pusheando - mismo patrón que
    el gotcha ya documentado del `ruff --fix` del #113 en la sesión del
    #54, pero esta vez con PRs propios en vez de uno de otro integrante.
  - **Los 2 templates grandes que quedaban del #132 ✅ HECHOS, pusheados
    hoy mismo (2026-09-03), probados en vivo end-to-end:**
    - `raypac_form.html` (4 `<select>` reales - el conteo original de "5"
      incluía el desplegable de Cliente, que ya es un patrón armado a
      mano, no un `<select>` nativo, así que no necesita el wrapper):
      Tipo Solicitud, Modelo Máquina, Tipo Máquina, Comercial
      Responsable. Caso con un listener de JS enganchado (el `change` de
      Comercial autocompleta el mail) - confirmado que sigue andando
      porque `enhanceSelect()` dispara un evento `change` sintético al
      elegir una opción. Probado con un alta completa en `/raypac/new`
      (incluido el modal de cliente nuevo). Rama
      `feature/132-unificar-select-raypac_form` → **PR #178, mergeado.**
    - `ticket_nuevo.html` (12 selects idénticos de "Estado del Equipo",
      mismo set de 7 opciones que ya se unificó en `dml_edit.html`) - el
      caso más simple, sin ningún listener de JS. Probado con un alta de
      ticket completa en `/tickets/nuevo/<id>`, confirmado en la base
      (`SELECT estado_equipo FROM tickets`) que el valor elegido persiste
      bien. Rama `feature/132-unificar-select-ticket_nuevo` → **PR #179,
      mergeado.**
    - Con esto, **los 7 templates / 23 selects reales del #132 quedan con
      el componente aplicado** (el 8vo/24to que contaba el issue
      original era `ficha_view.html`, template muerto, ver #168 más
      abajo). El PR de la última rama (usuario_form, la que trae el
      componente en sí) es independiente de este orden - no hace falta
      apilar `raypac_form`/`ticket_nuevo` una sobre otra, las dos parten
      de `dev` ya actualizado con las 4 anteriores mergeadas.
- **Hallazgo en el camino: `ficha_view.html` es un template muerto.**
  Ninguna ruta de `blueprints/dml.py` (ni de ningún otro blueprint) lo
  renderiza - la vista real de una ficha es `dml_view.html`. Se descubrió
  al ir a probar el select "Cambiar estado" de ese archivo (uno de los 8
  templates que el propio #132/`HALLAZGOS_REFACTOR.md` contaban). Se creó
  el **issue #168** documentándolo y se sacó del alcance de esta tanda de
  PRs - el scope real de #132 queda en **7 templates vivos, 23 selects**,
  no 8/24. No se tocó el archivo, decisión pendiente (¿borrar como los
  backups del #135, o reconectar bajo otro flujo?).
- **Hallazgo en el camino, probando la rama 4 en vivo: issue #176.**
  `dml_edit()` (`blueprints/dml.py:249`) rompe con un 500 (error de sintaxis
  SQL) al guardar cualquier ficha abierta que todavía no tiene "Fecha de
  Egreso DML" — que es el estado normal de una ficha en curso, no un caso
  raro. El input HTML no tiene `required` (a propósito, la fecha de egreso
  recién se completa al cerrar la ficha), pero el backend nunca convierte
  el string vacío a `None` antes de pasarlo a un `UPDATE` parametrizado
  contra una columna `date` de Postgres. **Confirmado que no tiene nada
  que ver con el #132** (`git diff dev feature/132-unificar-select-dml_edit
  -- CODIGO_FUENTE/blueprints/dml.py` no devuelve cambios) - es un bug
  preexistente en `dev`. Documentado en el issue #176. Facu decidió
  resolverlo en el momento (Size XS) - **✅ arreglado y probado hoy
  mismo**, rama `fix/176-fecha-egreso-vacia-rompe-guardado` (fix de una
  línea, mismo patrón `... or None` que ya usan `n_ciclos`/`horas_adic`
  en el mismo archivo), reproducido el 500 en local antes del fix y
  confirmado que guarda bien después. Rama
  `fix/176-fecha-egreso-vacia-rompe-guardado` → **PR #177, mergeado.**
- **#132 (Auditoría UX/UI) — ✅ los 3 PRs pendientes confirmados mergeados
  hoy mismo por Facu (#177, #178, #179).** Con esto, los 3 ítems del
  checklist del issue quedan completos en código. **Decisión de Facu:
  no cerrar el issue todavía** - queda abierto por ahora, sin fecha
  concreta para revisarlo (el 4to ítem del checklist, "revisar si
  aparecen más inconsistencias", es abierto por naturaleza).
- **Encargo aparte de Facu: recorrida guiada de diseño para armar un
  issue nuevo de rediseño UX/UI** (la intención original al pedir el
  #132 era más amplia que la lista puntual que terminó siendo - "que la
  app sea más amigable y fácil de usar" en general). Se hizo una
  recorrida completa de la app (server local + navegador): los 4 roles
  (ADMIN, RAYPAC, DML_ST, DML_REPUESTOS), la vista pública del ticket
  (con y sin sesión, confirmado con `curl` sin cookies que no filtra
  nada a un cliente anónimo real), y los formularios principales
  incluidos los del panel Admin que no se habían mirado antes. Resultado:
  **issue #181 creado** (Backlog, Size L, asignado a Facu, mismo
  criterio que el propio #132: alcance a desglosar cuando se retome), 7
  hallazgos confirmados en código o probados en vivo (no opiniones
  sueltas) - entre ellos: la vista de Ficha DML rompe el lenguaje visual
  del resto de la app, 3 formularios de admin sin tarjeta de Bootstrap
  (Nuevo Usuario/Nuevo Repuesto/Notificaciones), botones internos
  visibles sin chequeo de sesión en la vista pública del ticket
  (`ticket_view.html` - un cliente real termina en un login sin
  volver), filtros de búsqueda inconsistentes entre listados parecidos,
  y responsive/mobile sin poder verificar (limitación de la herramienta
  de browser usada, no del código - queda pendiente de revisión
  dedicada). Referencia cruzada con el **#158** (jerarquía de botones,
  se solapa) para no duplicar trabajo cuando se aborden.
- **Hallazgo de seguridad, encontrado en la misma recorrida: comentario
  agregado al #133 (sin tocar código).** Además del problema ya conocido
  (`"ADMIN2024"` hardcodeado y repetido), **el frontend expone la
  contraseña real como `placeholder`** en 3 formularios
  (`stock_new.html`, `stock_edit.html`, `raypac_form.html`) - cualquiera
  con acceso a esas pantallas la ve sin leer el código fuente. **Facu
  pidió no tocarlo todavía:** un compañero ya está cambiando las
  contraseñas del sistema (todavía sin mergear a este repo, confirmado
  con `git fetch` que no hay nada nuevo en `origin/dev` al respecto), y
  se está evaluando que la contraseña de confirmación de ADMIN sea
  directamente la misma que la del login (en vez de un código
  separado) - si se resuelve por ese camino, el problema del
  `placeholder` se soluciona de raíz. Evaluar todo junto cuando se tome
  la tarea del #133, no como fix aislado.
- **Hallazgo de infraestructura, no de código: el Render de "Dev" apunta a
  `main`, no a `dev`.** Facu estaba probando en el Render de `dev` y no
  aparecía el modal de "cliente nuevo" de RAYPAC (#165, mergeado el
  31/08) aunque sí aparecían fixes más viejos (#127, del 26/08).
  Confirmado con una captura del dashboard: el servicio
  `Software-de-Gestion-DML-Dev` tiene configurada la rama `main` (no
  `dev`) como origen del deploy, con el último deploy en vivo del 28/08
  (PR #153). No es un bug de código ni de auto-deploy - simplemente sigue
  otra rama. **Facu avisó que un compañero lo va a corregir**, sin
  necesidad de acción de nuestro lado.
- **Próximo paso concreto:** sin tarea propia en curso ahora mismo -
  candidatos para retomar en la próxima sesión, todos en Backlog:
  - **#181** (rediseño UX/UI, recién creado) - probablemente lo primero
    a desglosar en sub-issues chicos si se retoma, mismo patrón que
    funcionó con el #132.
  - **#133** (ADMIN2024 hardcodeado + el hallazgo nuevo del `placeholder`)
    - depende de que el compañero de Facu termine su cambio de
    contraseñas y se decida el enfoque (código propio vs. misma
    contraseña que el login).
  - **#168** (`ficha_view.html`, template muerto) - decisión pendiente,
    borrar o reconectar.
  - Los 2 templates grandes del #132 (`raypac_form.html`,
    `ticket_nuevo.html`) ya no son candidato - **quedaron resueltos
    hoy**, ver arriba.
- **Ambiente local de esta máquina:** usado activamente hoy (server
  levantado, testeado en el navegador vía Chrome + extensión de Claude in
  Chrome). El server de pruebas se detuvo al cerrar la sesión.
- **Bloqueos:** ninguno.

<details>
<summary>Checkpoint anterior (2026-08-31) — histórico, dejado sin borrar por
referencia</summary>

- **Última actualización:** 2026-08-31, cierre de sesión.
- **Issue #44 (colores de estados de reparación) — ✅ CERRADO manualmente.**
  Facu había arrancado una rama local `fix/44-colores-estados-reparacion`
  para esta tarea, pero al arrancar la sesión se encontró que el fix ya
  estaba mergeado en `dev` desde hacía 4 días (PR #144, 27/08) - el PR usó
  `Refs #44` en vez de `Closes #44`, así que el issue quedó abierto en
  GitHub aunque el checklist de scope ya estaba completo. Se cerró el issue
  a mano y se borró la rama local (ya redundante, sin nada propio para
  aportar). **Nota (corregida el 2026-09-02): la causa real no era el
  wording `Refs` vs. `Closes` — es que `Closes #N` no autocierra nada al
  mergear a `dev` en este repo, le pasa a cualquier PR. Ver el checkpoint
  de arriba.**
- **Tarea de la sesión: #132 (Auditoría UX/UI), en curso.** Se avanzó en 2 de
  los 3 sub-ítems planeados, cada uno en su propio PR chico:
  1. **Bug Bootstrap 4→5 en el modal "Acuse"** (`dml_entregadas.html`) -
     ✅ PR `fix/132-bootstrap5-modal-acuse` **mergeado**.
  2. **7 `confirm()` nativos reemplazados por modal de Bootstrap** (los 6
     que señalaba el issue + `notificaciones.html`, que se había quedado
     afuera del conteo original) - modal genérico reutilizable
     (`confirmarAccion()`) agregado a `base.html`, usado desde
     `dml_view.html`, `envios_view.html`, `raypac_view.html`,
     `stock_list.html`, `usuarios_list.html`, `notificaciones.html`. El de
     `raypac_form.html` (autoaprendizaje de cliente) quedó aparte por tener
     una estructura distinta (no bloquea el submit, decide un valor que
     viaja igual).
  3. **Queda sin arrancar:** unificar los ~24 `<select>` nativos al patrón
     del desplegable de Cliente - la parte más grande del issue, decidido
     dejarla para una próxima sesión.
- **4 bugs nuevos encontrados y arreglados en el camino** (ninguno parte del
  #132, todos siguiendo el flujo de kanban-primero):
  - **#156 + #157** (relacionados, mismo PR) - PR
    `fix/156-157-estado-entregada-huerfano` **mergeado**. #156:
    `dml_registrar_acuse()` rechazaba fichas con estado `'MÁQUINA
    ENTREGADA'` (el valor canónico real, del `<select>` y de
    `estados_orden`) porque validaba contra el string suelto `'ENTREGADA'`
    que hardcodeaba `dml_close()` al cerrar una ficha - dejaba la ficha en
    un estado huérfano (sin color de badge). #157: el `<select>` de
    `dml_edit.html` tenía `MÁQUINA ENTREGADA` como opción elegible
    directamente, sin pasar por "Cerrar Ficha" (que corre el checklist
    obligatorio y recién ahí marca `is_closed=TRUE`) - se sacó la opción
    del select y se agregó la misma validación en el backend.
  - **#161 + #162** (relacionados, mismo PR) - PR
    `fix/161-162-tabla-notificaciones-feedback` **mergeado**.
    #161: la tabla `usuarios_notificaciones` (destinatarios del mail de
    stock crítico del #59, ya cerrado) no existía en ningún lado
    versionado - ni `schema-postgres.sql` ni una migración en
    `extensions.py` - rompía `/admin/notificaciones` con `UndefinedTable`.
    Se agregó la tabla al schema + migración `CREATE TABLE IF NOT EXISTS`,
    mismo patrón que ya tiene `clientes`. Emparentado con el #125
    (sincronizar schema del repo con Supabase) - **sin confirmar si esta
    tabla existe en Supabase prod**, candidato a revisar ahí también.
    #162: las 3 rutas de escritura de `notificaciones.py` no flasheaban
    nada y el panel de la lista volvía a colapsarse después de cada
    guardado (aunque el dato sí se guardaba bien) - se agregaron `flash()`
    y se sacó el toggle colapsado, la lista se muestra siempre.
- **Issue nuevo creado, no relacionado con bugs: #158** (idea de Facu,
  flujo guiado - jerarquía visual de botones importantes + botón al
  siguiente paso cuando una acción habilita el siguiente). Kanban: Ready,
  Size L (mismo criterio que el #132: alcance todavía sin desglosar),
  sin Épica asignada (tampoco la tiene el propio #132), asignado a Facu.
  Candidato para cuando se retome el #132 a fondo o como tarea propia.
- **Ambiente local de esta máquina:** sigue armado de punta a punta, usado
  activamente hoy. El server de pruebas se detuvo al cerrar la sesión.
- **Bloqueos:** ninguno.

</details>

<details>
<summary>Checkpoint anterior (2026-08-26) — histórico, dejado sin borrar por
referencia</summary>

- **Issue #114 (bug de Ivo: `get_alert_badge` + columna `ultima_actualizacion`
  al eliminar repuesto) — ✅ CERRADO, PR #129 mergeado.** Ivo había dicho que
  creía que el bug de la columna no pasaba en Render, solo en su local —
  confirmó después que sí pasaba en los dos, así que no era diferencia de
  entorno: los dos bugs eran 100% de código (función no registrada en Jinja,
  columna que nunca existió en `schema-postgres.sql`). Fix: `get_alert_badge`
  registrada como global de Jinja en `app.py`, y la query usa `updated_at`
  (la columna real) en vez de `ultima_actualizacion`.
- **Issue #126 (`verificar_stock_api` roto, falso aviso de "sin stock") —
  ✅ CERRADO, PR #130 mergeado.** Encontrado probando el #114: la función
  usaba una variable `db` sin definir y una tabla `stock_repuestos`
  inexistente. Reescrita con `get_db()` + `matriz_repuestos`/`stock_ubicaciones`,
  mismo criterio que `check_stock_alert`.
- **Issue #128 (scripts duplicados en `dml_edit.html`) — ✅ CERRADO, PR #131
  mergeado.** Encontrado probando el #126 en el navegador: había DOS bloques
  `<script>` completos enganchados a los mismos elementos (uno viejo con
  `confirm()` nativo, uno nuevo con modal de Bootstrap cuyo chequeo de stock
  nunca se conectó al backend - quedó como stub). Se unificaron en uno solo;
  el submit ahora espera la verificación real antes de decidir.
- **Issue #127 (redirect inconsistente Eliminar vs. Mover a Stock) — ✅
  CERRADO, PR #136 mergeado.** `eliminar_repuesto()` ahora redirige a
  `dml_edit` igual que `mover_repuesto_a_stock()` (antes sacaba a `dml_view`).
  Sumado en el mismo PR (pedido de Facu durante el testing): los `confirm()`
  nativos de los botones "Eliminar" y "Mover a Stock" en `dml_edit.html` se
  reemplazaron por modales de Bootstrap (rojo/amarillo respectivamente),
  mismo patrón que el modal de stock del #128.
- **Gotcha nuevo, importante para la próxima vez que se abra un PR desde
  GitHub:** los PRs de #126 y #128 se abrieron por error contra `main` en
  vez de `dev` (default del repo si no se cambia el dropdown a mano). Contra
  `main` — semanas atrás de `dev` — GitHub mostraba conflictos falsos y el
  CI no llegaba a correr, dando la apariencia de "el CI tira error" sin serlo.
  Diagnóstico: `gh pr view <n> --json mergeable,mergeStateStatus` +
  `gh api repos/.../pulls/<n> -q .base.ref` para confirmar la base real.
  Fix: `gh pr edit <n> --base dev`, y como cambiar la base sola NO dispara
  el evento que activa el CI, hace falta además `gh pr close` + `gh pr reopen`
  para forzar un run nuevo.
- **Auditoría completa de `HALLAZGOS_REFACTOR.md` contra el kanban (pedido
  de Facu, preocupado de que hubiera hallazgos sin trackear).** De los 11
  hallazgos del documento, 8 ya estaban cubiertos por issues existentes
  (algunos cerrados en la sesión de hoy). Se crearon los 3 que faltaban:
  - **#132** — Auditoría UX/UI: `confirm()` nativos restantes (6, en
    `raypac_view.html`, `stock_list.html`, `envios_view.html`,
    `dml_view.html`, `usuarios_list.html`, `raypac_form.html`), el bug ya
    documentado de sintaxis Bootstrap 4 en el modal de "Acuse"
    (`dml_entregadas.html`), y el hallazgo #8 de los ~24 `<select>` sin
    unificar. Backlog, Size L.
  - **#133** — Centralizar `ADMIN2024` hardcodeado (5 ocurrencias) +
    evaluar si el mecanismo de `raypac_edit()` (inalcanzable desde la UI
    real, hallazgo #9) se elimina directamente. Backlog, Size S. Reemplaza
    la nota de "próxima tarea" que quedó pendiente el 2026-08-20.
  - **#134** — Botón "Generar Ficha" nunca conectado al frontend (hallazgo
    #5): decidir si se agrega el botón o se borra la ruta. Backlog, Size S.
  - **#135** — Borrar los 3 templates backup muertos (hallazgo #11:
    `dml_view_OLD.html`, `dml_edit_FIXED.html`, `dml_edit_BACKUP.html`,
    confirmado que siguen presentes). Backlog, Size XS.
  - `app_backup.py` (hallazgo #10) ya estaba resuelto de antes (PR #81), sin
    nada pendiente ahí.
- **Kanban, además:** #55 pasó de XL a M (Facu lo re-scopeó a mano tras
  revisar con Claude Code que la mayoría de los 7 puntos del checklist ya
  estaban implementados). #44 se movió de Backlog a Ready.
- **Aclarado, no es tarea:** la rama `refactor/85-unificar-los-3-generadores-de-pdf`
  es de Ivo (issue #85), sin commits propios todavía (apunta a un commit
  viejo de `dev` del 20/08) - no se toca, no se borra.
- **Práctica de equipo confirmada esta sesión (Facu):** cuando aparece un
  bug o inconsistencia que no generamos nosotros, primero chequear si ya
  tiene tarea en el kanban; si no, crear una (por más que sea XS, para que
  quede documentado) antes de decidir si se arregla en el momento o se deja
  para después. Aplicado repetidas veces hoy (#126, #128, #132-#135) - seguir
  con este flujo de acá en adelante.
- **Ambiente local de esta máquina:** sigue armado de punta a punta, usado
  activamente hoy para probar los 4 issues de arriba. El server de pruebas
  se detuvo al cerrar la sesión.
- **Bloqueos:** ninguno.
- **Próximo paso concreto:** ninguna tarea de Facu en curso ahora mismo.
  Candidatos para la próxima sesión, todos en Backlog: #132, #133, #134,
  #135 (los de arriba), o alguna tarea nueva que salga del daily.

</details>

<details>
<summary>Checkpoint anterior (2026-08-20) — histórico, dejado sin borrar por
las referencias a Issue #54/#62 más abajo</summary>

- **Issue #54 (ingreso RAYPAC) — ✅ CERRADO.** Los 3 PRs (#109, #110, #115)
  están mergeados a `dev`. Checklist manual de 6 puntos y los 5 puntos del
  DoD original confirmados (incluidas 5 altas consecutivas sin error 500).
  Al mergear #115 apareció un conflicto no anticipado en `raypac.py` y
  `extensions.py` — no era lógico, era el `ruff --fix` de la CI de Sebastián
  (#113, mergeada un rato antes) pisando las mismas líneas. Se resolvió
  combinando ambos cambios (no se descartó ninguno), verificado con
  `ruff check` + import-check (los mismos 2 checks de la CI) antes de
  pushear. Detalle completo en la sección "Issue #54" más abajo.
- **Issue #62 (endpoints sin auth) — ✅ CERRADO.** Traía 2/4 checkpoints
  de una sesión anterior (el fix puntual de `/admin/cargar-stock-csv` ya
  mergeado). Los 2 que faltaban se cerraron hoy: auditadas las 26 rutas
  protegidas de los 9 blueprints (ninguna otra desprotegida, solo quedan
  públicas a propósito `/login`, `/logout` y las 2 de `/ticket/...`), y
  probado con un script automatizado que las 26 redirigen a `/login` sin
  sesión. Único punto sin resolver: el DoD original pide HTTP 403 para rol
  no autorizado, pero el comportamiento real es redirect (302) - es una
  discrepancia ya documentada más abajo ("Discrepancia conocida"), no se
  toca sin decisión de equipo. Facu deja pendiente confirmar el review del
  PR #106 y, si quiere, repetir 2-3 pruebas a mano (el testing de hoy fue
  automatizado, no manual como pide el DoD general del sprint).
- **Con #62 y #54 cerrados no quedan tareas propias de Facu asignadas en
  `MENTORIA/sprint-2026-08-10/sprint.md` para este sprint (E2).** El trabajo
  de esta sesión (ver abajo) es autopropuesto a partir de hallazgos del
  testing del #54, no viene del plan de Matías — confirmar en el próximo
  daily si hay algo nuevo antes de asumir que sigue siendo así.
- **Hecho hoy — fix del bug de `raypac_unfreeze()`:** encontrado durante el
  testing del #54 (registro de prueba "Santi"). Al desfreezar un registro,
  `estado_envio_equipos` quedaba trabado en `'ENVIADO'` en vez de volver a
  `'PENDIENTE'`, y el badge de `raypac_view.html` seguía mostrando "Enviado
  desde RAYPAC" aunque el registro ya no estuviera freezado. Fix aplicado
  y probado localmente (pasos 1-5 del testing manual, confirmado por Facu):
  rama `fix/raypac-unfreeze-estado-envio`, commit `8b22dc0`, **pusheada,
  PR todavía sin abrir en GitHub.** El UPDATE revierte a `PENDIENTE` salvo
  que ya esté en `'RECIBIDO'` (no pisa una recepción ya confirmada por DML).
- **Próximo paso concreto:** dos cosas.
  1. Facu abre el PR de `fix/raypac-unfreeze-estado-envio` contra `dev`
     (`Refs #54` o el número de issue si ya la cargó al kanban — la tarea
     no tenía issue propia todavía a esta fecha) y lo mergea cuando esté
     conforme.
  2. Candidato para la próxima tarea, ya identificado pero sin arrancar:
     **limpiar el código muerto de `"ADMIN2024"` en `raypac_edit()`**
     (hallazgo #9 de `HALLAZGOS_REFACTOR.md` — segundo mecanismo de
     desbloqueo hardcodeado, inalcanzable desde la UI real porque el flujo
     que funciona de verdad es "Desfreezar Definitivamente" con los
     últimos 4 dígitos del remito). Mismo patrón que el hallazgo #2 de
     seguridad (código repetido 5 veces en el proyecto) — este sería un
     primer paso hacia esa limpieza más grande. Tamaño XS, Épica
     "Seguridad y deuda técnica" (a diferencia del fix de hoy, que era de
     "Gestión de reparaciones"). Sin issue creada todavía.
- **Ambiente local de esta máquina:** sigue armado de punta a punta
  (Postgres 17 + pgAdmin 4 + Python 3.11, venv, `.env` con `DATABASE_URL`
  a una base local `dml_dev`, schema aplicado) - no hace falta rehacerlo.
  El server de pruebas se detuvo al cerrar la sesión. Detalle de los 3
  bugs de setup conocidos: sección "Setup de entorno local" más abajo.
- **Bloqueos:** ninguno.

</details>

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
No dar por hecho que el PR se abre solo ni asumir que ya está abierto. **Al confirmar
que un PR con `Closes #N` quedó mergeado, cerrar ese issue a mano** (`gh issue close`)
— ver el gotcha en "Branches y flujo de PRs", `Closes #N` no autocierra nada acá.

**Antes de tocar cualquier rama:** seguir la rutina de sincronización de siempre —
`git status` (si hay cambios sin commitear, resolverlos primero: `git diff` para ver
qué son, y decidir si se descartan, se guardan con `stash`, o se commitean),
`git checkout dev` + `git pull origin dev`, y recién ahí crear la rama nueva o
cambiarse a la que corresponda. No hacer `git pull` ni `git checkout` con cambios
sin resolver de por medio.

**Nombres de rama:** `tipo/descripcion-corta-con-guiones` (ej. `fix/proteger-endpoint`,
`feature/54-desplegable-tipo-maquina`). El tipo (`fix`, `feature`, `docs`, `chore`)
según corresponda al cambio.

**Mantener el Checkpoint actualizado.** Al cierre de cada sesión, o cuando cambie
significativamente el estado de la tarea en curso (se prueba algo, se destraba un
bloqueo, se decide el próximo paso), actualizar la sección "🔖 Checkpoint" al
principio de este archivo con el estado real y el próximo paso concreto. Sigue el
mismo flujo que cualquier cambio: rama chica (`docs/checkpoint-...`), commit, push,
avisarle a Facu para que abra y mergee el PR contra `dev`.

**Bug o inconsistencia que no generamos nosotros: primero kanban, después código.**
Cuando aparece algo roto/feo que no es parte de la tarea en curso (encontrado
mientras se prueba otra cosa), chequear primero si ya tiene issue en GitHub
(`gh issue list --search ...` o revisar el board). Si no la tiene, crearla —
por más que sea Size XS, para que quede documentado y no se pierda — y recién
ahí preguntarle a Facu si conviene resolverla en el momento (si es chica) o
dejarla para después. No arreglar directamente sin este paso primero.

**Cuidado al abrir un PR desde GitHub: confirmar la base branch.** El dropdown
de base del PR puede quedar en el default del repo si no se lo cambia a mano
- pasó en esta sesión con dos PRs que se abrieron contra `main` en vez de
`dev` por error, y el síntoma en pantalla (conflictos, CI que no corre) se ve
igual que un problema real. Si un PR recién abierto muestra conflictos raros
o el CI no corre, lo primero a chequear es `gh api repos/.../pulls/<n> -q
.base.ref` antes de asumir que es un bug de código.

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
- Al abrir un PR, usar `Closes #N` en la descripción (más de un `Closes #N` si el PR
  resuelve varios issues) — sirve como documentación de qué resuelve el PR, pero
  **no cierra el issue solo** (ver gotcha abajo). Cerrar el issue a mano después de
  mergear.

**Gotcha importante — `Closes #N` NUNCA autocierra un issue al mergear a `dev`.**
El default branch del repo es `main`, y GitHub solo dispara el auto-close de
`Closes #N`/`Fixes #N` cuando el PR se mergea a la default branch del repo — no
cuando se mergea a `dev`. Como acá **todo** se mergea a `dev`, ningún PR cierra
issues solo, tenga `Closes` o `Refs`, esté bien escrito o no. Confirmado revisando
el timeline de varios issues (2026-09-02): #127 lo había cerrado Facu a mano (no
fue un cierre automático), y #156/#157/#161/#162 seguían `OPEN` en GitHub con sus
PRs ya mergeados a `dev` (con `Closes #N` correcto en el body). La nota que había
quedado en el checkpoint del #44 ("el PR usó `Refs` en vez de `Closes`") atribuía
esto a un problema de wording — es la causa equivocada, el problema es estructural.
**Práctica a partir de ahora:** después de mergear un PR a `dev` que resuelve un
issue, cerrarlo a mano (`gh issue close N --comment "..."`) como parte del mismo
paso — no asumir que GitHub lo hizo. Antes de dar una tarea por "cerrada", chequear
el estado real del issue en GitHub, no solo que el PR esté mergeado.

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
  (el instalador de EDB trae ambos juntos). En Windows con `winget` se puede
  instalar todo en silencioso, sin el instalador gráfico interactivo:
  ```powershell
  winget install --id PostgreSQL.PostgreSQL.17 --silent --accept-package-agreements --accept-source-agreements --override "--mode unattended --unattendedmodeui minimal --superpassword TU_PASSWORD --serverport 5432"
  winget install --id PostgreSQL.pgAdmin --silent --accept-package-agreements --accept-source-agreements
  winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
  ```
- **Base Postgres local nueva (vacía): correr el schema a mano antes de
  arrancar la app.** `init_db()` (`extensions.py`) NO crea tablas, solo
  hace `ALTER TABLE` sobre tablas que asume que ya existen (porque en
  Supabase el schema se cargó una sola vez a mano por el SQL Editor, ver
  `MENTORIA/Migracion PostgreSQL/carga-inicial-supabase.md`). En una base
  local nueva, arrancar la app sin este paso tira `UndefinedTable` en
  cadena. Correr primero:
  ```powershell
  psql -U postgres -h localhost -p 5432 -d NOMBRE_BASE -f CODIGO_FUENTE/db/schema-postgres.sql
  ```
  (el script empieza con `DROP TABLE IF EXISTS ...`, seguro en una base
  nueva/de prueba, destructivo si se corre sobre una base con datos reales
  - no correrlo nunca contra `dev`/prod de Supabase).
- **Bug conocido: archivo `dml.db` viejo puede tapar el init de Postgres.**
  `config.py` decide si "la base ya existe" chequeando si existe un archivo
  `dml.db` en la raíz (leftover de la era SQLite, en `.gitignore`, no
  versionado). Si ese archivo está presente en la máquina, la app se salta
  `init_db()` y va directo a `migrate_db()` sobre una Postgres vacía, mismo
  error en cadena que el punto anterior. Si aparece ese archivo por algún
  motivo, renombrarlo/borrarlo antes de levantar el server.
- **Bug conocido en Windows: prints con emoji rompen la consola.** Varios
  `print()` de `extensions.py`/`app.py` llevan emoji (✅⚠️📁🌱). En una
  consola Windows con codepage `cp1252` (no UTF-8) esto tira
  `UnicodeEncodeError` **dentro del propio `except` que loggea el error
  real**, tapándolo con un traceback distinto. Workaround: forzar UTF-8 en
  el proceso antes de correr la app:
  ```powershell
  $env:PYTHONIOENCODING = "utf-8"
  ```
  (Nota: reportar al equipo - la solución de fondo es sacar los emoji de
  los `print()` o configurar `sys.stdout.reconfigure(encoding="utf-8")` en
  `app.py`.)
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
  1. **#62 — Endpoints sin auth — ✅ cerrado (2026-08-19).** Único endpoint
     desprotegido: `/admin/cargar-stock-csv` en `blueprints/admin.py` (le
     faltaban `@login_required` y `@role_required("ADMIN")`, ya agregados,
     PR #106). Auditadas las 26 rutas protegidas restantes de los 9
     blueprints - ninguna otra desprotegida. Issue duplicado #86 cerrado en
     el mismo PR con `Closes #62` + `Closes #86`.
  2. **#54 — Corregir ingreso RAYPAC — ✅ cerrado (2026-08-19).** Los 3 PRs
     (#109, #110, #115) mergeados a `dev`. Ver detalle abajo.
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

**PRs mergeados a `dev` (todos ✅, 2026-08-19):**
- **#108** `docs/agregar-claude-md` — este archivo
- **#109** `feature/54-campos-contacto-mail-cliente` — oculta contacto/mail para
  roles DML en `dml_entregadas.html` + documenta las columnas en `schema-postgres.sql`
- **#110** `fix/54-numero-correlativo-postgres` — bug encontrado en el camino (ver
  Hallazgos abajo), no estaba en el plan original
- **#113** `chore/103-continuous-integrations` (de Sebastián, no es del #54 pero
  se mergeó en el medio) — CI mínimo (ruff + import check) + 27 fixes automáticos
  de `ruff --fix` en todo `CODIGO_FUENTE/`
- **#115** `feature/54-desplegable-clientes` — tabla `clientes` con
  autoaprendizaje, sembrada con los 39 clientes del Excel de David
- **#116** `docs/checkpoint-sesion` — checkpoint de continuidad + cierre del
  checklist (esta sección, versión anterior)

**Conflicto de merge real al mergear #115:** no fue el anticipado (#110 vs.
`feature/54-desplegable-clientes` en `extensions.py`, que sí estaba previsto y
no llegó a pasar en la práctica porque `raypac.py` conflictuó primero) - fue
un conflicto contra el `ruff --fix` de #113, mergeado un rato antes, que
reordenó imports y algunas líneas de `raypac.py`/`extensions.py` justo donde
`feature/54-desplegable-clientes` también tocaba. Se resolvió localmente
(mergear `origin/dev` en la rama, combinar ambos cambios sin descartar
ninguno, correr `ruff check` + el import-check de la app antes de pushear) y
se pusheó ya resuelto - lección para la próxima vez que se abra una PR de
`chore/` tipo lint/formateo masivo: **avisar a quien tenga ramas activas**,
porque puede generar conflictos "de forma" en cualquier archivo tocado,
no solo en los que uno espera.

**Técnica usada para probar los 3 juntos sin romper el esquema de PRs chicos:**
rama local `test/54-integracion-local` (cortada de `dev`, con los 3 branches
mergeados adentro) **nunca pusheada a GitHub** — sirvió para levantar un único
server local y probar el flujo completo de una sentada. Se borró al cerrar la
sesión (2026-08-19). Los PRs reales en GitHub se revisaron/mergearon por
separado, esto no los reemplazó ni los tocó.

**Definition of done del issue:**
1. Login RAYPAC → `/raypac/new` → completar form → guardar → remito 4 dígitos → freezar
2. Registro visible como "pendiente" del lado DML
3. RAYPAC no puede editar después de freezar (solo ADMIN con código de desbloqueo)
4. 5 flujos consecutivos sin HTTP 500 ni bloqueos
5. Un usuario DML no ve los campos de contacto/mail cliente

### Checklist manual de pruebas — ✅ COMPLETO (cerrado 2026-08-19)

Probado en la rama de integración local `test/54-integracion-local` (no pusheada,
ver más arriba), en dos sesiones (2026-08-13 y 2026-08-19, esta última desde una
máquina distinta). Los 6 puntos quedaron confirmados. Facu todavía no mergeó los
PRs — decisión suya, quiere revisar una vez más antes de apretar el botón.

Usuarios: `raypac@dml.local`/`raypac` · `tecnico@dml.local`/`tecnico` (DML_ST) ·
`admin@dml.local`/`admin`

1. ✅ **Alta de ingreso (PR #110):** confirmado, guarda sin error 500 (antes del fix
   tiraba "no existe la columna numero_correlativo").
2. ✅ **Desplegable de clientes:** confirmado funcional (sugiere existentes,
   `confirm()` al escribir uno nuevo, autoaprendizaje). El estilo original tenía un
   problema real de consistencia: al hacer foco/click con el campo vacío no
   mostraba nada (solo al escribir) — inconsistente con el resto de los `<select>`
   de la app, que muestran todas las opciones al clickear. **Fix aplicado y
   confirmado** (commit `f7f2325` en `feature/54-desplegable-clientes`, ya
   pusheado): ahora al hacer foco sin texto muestra la lista completa (scrollea,
   ya tenía `max-height`), escribiendo sigue filtrando igual que antes.
   - **Hallazgo aparte, no resuelto este sprint** (ver `HALLAZGOS_REFACTOR.md` #8):
     por más parecido que quede, un desplegable armado a mano nunca va a ser
     pixel-idéntico a un `<select>` nativo (el navegador dibuja el popup abierto,
     no Bootstrap). Facu pidió unificar TODOS los `<select>` de la app al mismo
     patrón para consistencia total - alcance grande (~24 selects en 8 templates),
     decidido posponer para no arriesgar el timeline del #54. Queda como issue
     propio para después del sprint.
3. ✅ **Contacto/mail (PR #109):** confirmado en ambos sentidos - se ven como
   `raypac` (con el texto "Visible solo para RAYPAC y ADMIN"), y NO se ven como
   `tecnico` (DML_ST) abriendo `/raypac/<id>` de un ingreso freezado.
4. ✅ **Freeze / edición bloqueada — confirmado, con una corrección importante al
   flujo que se pensaba probar:** el botón Editar está oculto en
   `raypac_view.html` para TODOS los roles (incluido ADMIN) mientras
   `entry.is_frozen` sea true - no hay forma de editar "in place" con un código
   sin desfreezar antes. El código real para volver a habilitar edición es
   **"Desfreezar Definitivamente"** (solo ADMIN), que pide los **últimos 4
   dígitos del número de remito** de ese registro (no un código fijo) - una vez
   desfreezado, tanto ADMIN como RAYPAC pueden editar de nuevo normalmente.
   Confirmado con testing real: bloquea sin desfreezar, desfreezar con los 4
   dígitos correctos funciona, y editar después funciona con los dos roles.
   - **Hallazgo aparte, no resuelto:** `raypac_edit()` (backend) todavía tiene
     una segunda lógica de desbloqueo con el código hardcodeado `"ADMIN2024"`
     (con un TODO de seguridad al lado, ver hallazgo #2 de seguridad) que es
     **inalcanzable desde la UI real** - mismo patrón que el hallazgo #5
     ("Generar Ficha" nunca conectado al frontend), código muerto que nadie
     dispara. No confundir este código con el flujo real que sí funciona
     (últimos 4 dígitos del remito).
5. ✅ **Lado DML — recepcionar:** confirmado, el botón "Dar de Alta en DML" está
   en la sección "Estado de Envío del Equipo" de `/raypac/<id>` (no confundir
   con la tarjeta separada más abajo "Crear Ficha de Servicio Técnico", que es
   un flujo posterior y no forma parte de este checklist).
6. ✅ **`/dml/entregadas` oculta contacto/mail a DML_ST:** confirmado con el
   flujo completo por UI (crear ticket → crear ficha → completar Técnico
   Responsable/Diagnóstico mín. 10 caracteres/N° Remito de Salida → cerrar
   ficha → ENTREGADA). Como `admin`/`raypac` se ven Contacto/Email en
   `/dml/entregadas`; como `tecnico`, no.
   - **Nota de flujo:** el botón "Crear Ticket" en `/raypac` (lista) solo
     aparece si el registro está freezado y sin ticket todavía (`raypac_list.html`,
     condición `entry.is_frozen and not entry.ticket_id`) - si lo desfreezaste
     para probar el punto 4, hay que volver a freezarlo antes de este paso.

## Hallazgos pendientes (no resueltos, documentados en HALLAZGOS_REFACTOR.md)

**Seguridad (Épica 2):**
- Hashes de contraseñas hardcodeados en `migrate_db()` (tarea de Ivo, #64/#65) — cerrado
- Código `"ADMIN2024"` hardcodeado y repetido 5 veces (`raypac_edit`, `dml_edit`,
  `stock_new`, `stock_edit`, `stock_delete`) — issue **#133**, Backlog

**Bugs confirmados:**
- ~~`verificar_stock_api` en `blueprints/api.py` roto~~ — **resuelto (2026-08-26),
  issue #126, PR #130.** Reescrito con `get_db()` + `matriz_repuestos`/`stock_ubicaciones`.
- Botón "Generar Ficha" nunca conectado al frontend (la ruta existe, ningún
  template la llama) — issue **#134**, Backlog
- Botón "Acuse" en `/dml/entregadas` usa sintaxis Bootstrap 4 en proyecto Bootstrap 5
  (`data-toggle` → debería ser `data-bs-toggle`) — agrupado en issue **#132**
  (auditoría UX/UI), Backlog
- `raypac_new()` en `blueprints/raypac.py` inserta y lee la columna `numero_correlativo`
  de `raypac_entries`, pero esa columna no existe en `schema-postgres.sql` ni tenía
  migración en `extensions.py` (a diferencia de `contacto_cliente`/`email_cliente`, que
  sí la tienen). Reproducido en la práctica contra Postgres real (tira
  `no existe la columna «numero_correlativo»` al guardar un ingreso nuevo) — **resuelto,
  PR #110** (`fix/54-numero-correlativo-postgres`) ya mergeado a `dev`.
- ~~`raypac_unfreeze()` no revierte `estado_envio_equipos` a `PENDIENTE` al desfreezar~~
  — **resuelto, PR #119 mergeado a `dev`.** Encontrado probando el #54 (registro de
  prueba "Santi" en la base local): un registro desfreezado podía quedar con
  `is_frozen=FALSE` pero `estado_envio_equipos='ENVIADO'`, mostrando el badge
  "Enviado desde RAYPAC" como si siguiera en tránsito aunque ya no estuviera freezado.
- ~~`eliminar_repuesto()` en `dml_view.html` tira `UndefinedError` en `get_alert_badge`
  y `UndefinedColumn` en `ultima_actualizacion`~~ — **resuelto (2026-08-26), issue
  #114, PR #129.** Reportado por Ivo, confirmado que reproducía tanto en local como
  en Render (no era diferencia de entorno).
- ~~Scripts duplicados de verificación de stock en `dml_edit.html`~~ — **resuelto
  (2026-08-26), issue #128, PR #131.** Dos bloques `<script>` completos enganchados a
  los mismos elementos, mostrando alertas contradictorias.
- ~~Redirect inconsistente entre "Eliminar" y "Mover a Stock" en `dml_edit.html`~~ —
  **resuelto (2026-08-26), issue #127, PR #136.** De paso, se reemplazaron los
  `confirm()` nativos de esos dos botones por modales de Bootstrap.

**No urgente:**
- Dos generadores de PDF sin unificar (`generar_ficha_pdf` y `generate_ficha_pdf`) más
  un tercero sin integrar (`generate_ficha_pdf_new`) — tarea de Ivo (#85) esta sprint,
  puede no completarse y pasar a E3
- ~24 `<select>` nativos sin unificar visualmente con el desplegable armado a mano de
  Cliente — agrupado en issue **#132** (auditoría UX/UI), Backlog
- Archivos backup viejos candidatos a borrar: `dml_view_OLD.html`, `dml_edit_FIXED.html`,
  `dml_edit_BACKUP.html` — issue **#135**, Backlog

## Rutas sin `@login_required` a propósito (no son bugs)

- `tickets.py` → `ticket_view` (`/ticket/<numero_ticket>`) y `ticket_print` — vista
  pública de seguimiento para que el cliente final consulte su equipo sin cuenta

## Documentación / proceso académico

- Bitácora: pedir resumen de sesión al final de cada una para pegar en `BITACORA_DML_2026.xlsx`
- Log de uso de IA: generar entrada para `Log_Uso_IA_DML.docx` (Google Drive) al
  cierre de cada sesión de trabajo con Claude
- `CHANGELOG.md` en la raíz del repo: sigue pendiente
