# Notas de la entrega al cliente — 2026-10-28

Comentarios del cliente durante la demo (entrega del 2026-10-28) que todavía
no están en la app, más las dudas que surgieron. Hay que repasarlo con Facu y
decidir cuáles pasan a issues en el kanban.

> **⚠️ Recordatorio para la próxima sesión (pedido de Facu):** pedirle a Facu
> **todos los archivos que dio el cliente** (ubicaciones del stock, etc.) y
> una **planilla de stock actualizada**, para compararlos con lo que ya está
> en `DOCUMENTOS DML/` (ver punto 6). Además, convertir esta nota en issues.

---

## 1. El remito lo cargan ellos; el número de la máquina es el número de ficha

**Lo que dijo el cliente:** "El número de la máquina no tiene que ser el
remito, el remito lo anotan ellos, el número de la máquina es el número de
ficha."

**Cómo está hoy (desde el PR #292, issue #259, mergeado el 2026-10-26):**
- Al "Freezar y Enviar a ST" ya no se pide remito: el sistema usa
  automáticamente el N° de serie como remito (`raypac_freeze()` en
  `CODIGO_FUENTE/blueprints/raypac.py`).
- El código para desfreezar pasó a ser los últimos 4 caracteres del N° de serie.
- Antes del #292, RAYPAC escribía el remito a mano (los últimos dígitos, que
  se completaban como `00001-XXXXXXXX`), era obligatorio y no podía repetirse.
- El número de ficha ya existe: es correlativo (501, 502, ...) y lo genera
  `generate_ficha_number()` en `CODIGO_FUENTE/services/numeracion.py`.
- El ticket se llama `TK-{N° de serie}` (y `-2`, `-3`... si la máquina vuelve a entrar).

**Conclusión:** el #259 se interpretó mal. La parte del remito del #292
probablemente hay que revertirla, para que se vuelva a cargar a mano.

**Para aclarar con el cliente (idealmente en la demo misma):**
- [ ] El remito: ¿vuelve a ser obligatorio para freezar? ¿Mantiene el formato
      `00001-XXXXXXXX`? ¿Puede repetirse?
- [ ] "Número de la máquina = número de ficha": ¿es el número que ya genera el
      sistema (501, 502...) o uno propio que llevan ellos? ¿Dónde lo quieren ver
      en lugar del N° de serie: ticket (`TK-...`), listados, PDF, búsqueda?
- [ ] El N° de serie, ¿sigue pudiendo repetirse (misma máquina que entra varias
      veces)? Eso del #292 no tiene por qué cambiar.

**Aclaración del cliente (más adelante en la demo):** el número de ficha es
correlativo (1, 2, 3...). El que lleva el N° de serie de la máquina es el **ticket**.

**Contra el código actual:**
- Ticket = `TK-{N° de serie}`: **ya está así**, no hay que tocar nada.
- Ficha correlativa: **ya lo es**, pero arranca en **501**, no en 1
  (`(last['max'] or 500) + 1` en `generate_ficha_number()`). Hay que preguntar
  si quieren que arranque en 1. Si es así, ojo con las fichas que ya existen.
- Remito: **sí hay que cambiarlo**. Tiene que volver a cargarse a mano al
  freezar (revertir esa parte del #292).

**Issue relacionado:** #259 (cerrado), PR #292. Tamaño estimado: S.

---

## 2. Repuesto agregado dos veces en la ficha (bug, lo vio Facu en la demo)

**Qué pasó:** al agregar un repuesto en `/dml/<id>/edit`, el repuesto quedó
cargado dos veces. Probablemente el compañero hizo más de un clic mientras cargaba.

**Causa (confirmada en el código, no reproducida todavía):**
- El botón "Agregar" (`btn_agregar_repuesto`, `dml_edit.html`) no se
  deshabilita después del primer clic.
- El `submit` frena el envío, espera la verificación de stock (`fetch`) y
  recién después manda el formulario. Cada clic mientras tanto vuelve a
  disparar todo, así que se mandan varios POST.
- `agregar_repuesto()` (`dml.py`) no rechaza el mismo código cargado dos
  veces seguidas: inserta las dos veces.
- **Efecto colateral:** si estaba EN STOCK, **el stock se descuenta dos veces**.
  Si se borra el duplicado con "Eliminar", el stock se devuelve bien
  (`eliminar_repuesto()` lo repone).

**Arreglo propuesto:** deshabilitar el botón (y mostrar "Agregando...") apenas
se hace clic, en el form de agregar repuesto y en el "Agregar de todas formas"
del modal. Revisar si conviene también un resguardo en el backend.
Tamaño estimado: XS.

---

## 3. Aviso por mail de "máquina lista"

**Lo que dijo el cliente:** le tiene que llegar a alguien un aviso por mail
cuando la máquina está lista.

**Cómo está hoy:** **ya existe.** Al apretar "Cerrar Ficha" (`dml_close()`
en `dml.py`), se manda el mail "✅ MÁQUINA LISTA PARA RETIRAR" al **comercial
responsable** del ingreso RAYPAC (`mail_comercial`). El mail lleva la ficha,
el N° de serie, el cliente, la fecha y el ticket.

**Para revisar o aclarar:**
- [ ] ¿El destinatario correcto es el comercial? ¿O también (o en su lugar)
      el cliente (`email_cliente`), RAYPAC u otra persona?
- [ ] Confirmar que en Render llega de verdad. Variables a revisar:
      `RESEND_API_KEY`; `MAIL_DEV_REDIRECT`, que si está seteada manda todo a
      una sola casilla de prueba; y `MAIL_FROM`, porque con el default
      `onboarding@resend.dev` sin dominio verificado, Resend solo deja enviar
      a la casilla dueña de la cuenta.

---

## 4. Pedidos de repuestos de RAYPAC a DML (funcionalidad nueva, grande)

**Lo que dijo el cliente:** RAYPAC también le pide repuestos a DML. Que a DML
le llegue una alerta de que le pidieron un repuesto, que DML lo pueda enviar,
y que RAYPAC también pueda ver el stock.

**Cómo está hoy:**
- **Envíos de repuestos** (`envios.py`, #57): solo existe el sentido
  **RAYPAC → DML**. RAYPAC arma el envío con remito, lo freeza, y DML
  confirma la recepción y suma al stock. La campanita (#290) le avisa a
  DML_REPUESTOS cuando llega un envío.
- **No existe un "pedido de repuestos"** (RAYPAC pide → DML recibe una
  alerta → DML envía a RAYPAC). Tampoco hay envíos en sentido DML → RAYPAC.
- **Stock:** RAYPAC ya entra a `/stock`, pero **solo ve el stock de la
  ubicación RAYPAC** (`stock_list()` en `stock.py` fuerza
  `ubicacion = "RAYPAC"`). No puede ver el stock de DML. ADMIN ve las dos
  ubicaciones.

**Lo que habría que construir (a desglosar):**
- Pedido de repuestos creado por RAYPAC (repuestos + cantidades).
- Alerta a DML: campanita (reusar la del #290) y ¿mail?
- DML prepara o despacha el pedido: descuenta stock de DML y ¿suma al de RAYPAC
  al recibirlo? ¿Con remito?
- Estados del pedido: pedido → enviado → recibido.
- RAYPAC puede ver el stock de DML (solo lectura): cambio chico, se puede
  hacer aparte y primero.

**Para aclarar con el cliente:**
- [ ] "Que RAYPAC pueda ver el stock": ¿el de DML, para saber qué pedir?
- [ ] ¿La alerta es solo dentro del sistema (campanita) o también por mail?
- [ ] ¿El envío DML → RAYPAC lleva remito? ¿RAYPAC confirma que lo recibió?
- [ ] ¿Se lleva stock de RAYPAC en el sistema (que se sume al recibir)?

Por el criterio de CLAUDE.md, es un hallazgo grande: va con issue propio.
Tamaño estimado: L (ver stock de DML: XS).

---

## 5. Ubicación física del repuesto en el stock (ej. "Estante 1, Fila 2")

**Lo que dijo el cliente:** el stock tiene que tener una columna que diga
dónde está físicamente cada repuesto, por ejemplo "Estante 1, Fila 2".
Todavía no saben cómo van a ser las ubicaciones.

**Cómo está hoy:** **la columna ya existe en la base pero no se ve en la app.**
- `stock_ubicaciones.codigo_ubicacion_fisica` (TEXT, default
  `'SIN UBICACIÓN'`), en el schema y con migración en `extensions.py`.
- Solo se carga desde la carga masiva por CSV de Admin
  (`/admin/cargar-stock-csv`, `admin.py`) y el seed. No se muestra en el
  listado de stock ni se puede editar desde Nuevo o Editar repuesto.
- Ojo con no confundir: la columna `ubicacion` ("DML"/"RAYPAC") es en
  qué empresa está, no el lugar físico.

**Propuesta:** mostrar la columna "Ubicación" en `/stock` y agregar el campo
en Nuevo y Editar repuesto, como **texto libre**. Como todavía no definieron el
formato, el texto libre sirve para cualquier esquema, y más adelante se puede
pasar a un desplegable. Que también se pueda buscar por ubicación. Tamaño
estimado: S.

**Ampliación del cliente:** la ubicación la cargan ellos cuando **se crea**
un repuesto nuevo **o cuando llega** uno. Al crear o recibir tiene que haber
un campo para completarla.

**Dónde tiene que aparecer el campo:**
1. **Nuevo repuesto** (`/stock/new`, `stock_new()` en `stock.py`).
2. **Editar repuesto** (`/stock/<codigo>/edit`), para cambiarla o
   completar las que quedaron "SIN UBICACIÓN".
3. **Confirmar recepción de un envío de RAYPAC** (`envios_confirmar()` en
   `envios.py`). Hoy suma la cantidad al stock de DML y, si el código no
   estaba en la matriz, lo da de alta solo, sin ubicación. Agregar un campo
   de ubicación por cada línea del envío. ¿Obligatorio solo para los códigos
   nuevos o que todavía no tienen ubicación, y precargado si ya la tienen?
   (Si ya está guardado, no hace falta volver a pedirlo.)

Tamaño estimado: S → **M** con la parte de recepción de envíos.

**Para aclarar:** ¿la ubicación es solo para el stock de DML, o RAYPAC
también quiere cargar la suya?

---

## 6. Stock desactualizado + documentos del cliente

**Lo que dijo el cliente:** ya nos pasaron varios documentos (ubicaciones del
stock, etc.). Además, el stock cargado en el sistema probablemente no coincide
con el real.

**Lo que ya está en el repo (`DOCUMENTOS DML/`):**
- `Copia de NUEVO STOCK DE REPUESTOS COMPLETO.xlsx/.csv`, con el stock al
  11/12/2025 (última carga general marcada 26-06-2025). **Ya trae las
  ubicaciones**: columnas Estante / Fila / Posición / Box y un código armado,
  ej. `E05-F05-B02`, `E01-F04-PB-B02` (~250 filas con ubicación).
  → **El formato de ubicación del punto 5 ya está definido por ellos.**
- `STOCK 26-05-25.xlsx`, `FICHA VACIA PARA RELLENAR 2 con stock.xlsx`,
  `CAMPOS DE INGRESO DML*.xlsx/.csv`, `PROYECTO SOFTWARE DE GESTION DE ST Y
  REPUESTOS (1) copy.pdf`, y `Observaciones del soft.docx` (en la raíz).

**Pendiente:**
- [ ] **RECORDARLE A FACU que pase todos los archivos que dio el cliente**,
      para compararlos con lo que ya está en `DOCUMENTOS DML/` y ver si hay
      algo nuevo (ubicaciones, stock más reciente, etc.).
- [ ] Pedirle al cliente un **stock actualizado** (planilla con el mismo
      formato) y recargarlo con la carga masiva por CSV de Admin. Antes,
      revisar qué pasa con el stock que ya se movió en el sistema (repuestos
      usados en fichas, envíos recibidos), porque la carga pisa las cantidades.

---

## 7. Ubicación: editable y opcional (complementa el punto 5)

**Lo que dijo el cliente (aclarado por Facu):**
- Un **botón para editar la ubicación** de un ítem del stock, por si lo cambian de lugar.
- Al **crear o recibir** un repuesto, la ubicación **puede quedar vacía**
  (en el momento quizás no saben dónde va). Se guarda igual, y en el listado
  queda **marcado como pendiente de cargar ubicación** para completarlo después.

**Cómo está hoy y qué tener en cuenta:**
- "Editar" de stock (`stock_edit()` en `stock.py`) existe, pero solo para
  **ADMIN y DML_ST** (DML_REPUESTOS no puede). Si el que edita es ADMIN, pide
  la **contraseña de admin** (#133). Para algo tan simple como la ubicación
  conviene un **botón propio "Editar ubicación"** (ej. un modal en la fila del
  listado), sin pedir contraseña. Aclarar qué roles pueden: ¿DML_REPUESTOS sí?
- El default actual de la columna es el texto `'SIN UBICACIÓN'`. Sirve como
  marca de "pendiente": se muestra con un badge de advertencia en el listado
  y conviene sumar un **filtro "Sin ubicación"** para encontrar rápido los que
  faltan.
- Formato: el de la planilla del cliente (`E05-F05-B02`). Se puede cargar
  como texto libre o como 4 campos (Estante/Fila/Posición/Box) que arman el
  código. A decidir.

Junto con el punto 5 → un issue "Ubicación física en stock", tamaño M,
cortado en PRs chicos: (a) columna + filtro + editar ubicación,
(b) campo en Nuevo repuesto, (c) campo en recepción de envíos.

---

## 8. ¿Dónde se carga (restaura) el backup?

**Pregunta en la demo:** ¿hay algún lugar en la app para cargar un backup?

**Respuesta:** no, **a propósito** (decisión del #52, PR #291). Desde la app
solo se **descarga** (Admin → 💾 Backup de datos). Restaurar lo hace el
equipo de desarrollo siguiendo `docs/BACKUPS.md` (psql o SQL Editor de
Supabase), porque un botón que pisa toda la base es demasiado peligroso.

**Si el cliente insiste en restaurar desde la app:** anotar el pedido y
evaluarlo aparte (con confirmación fuerte, solo ADMIN, backup automático
previo, etc.). Pendiente del #52: envío automático del backup por mail.

---

## 9. Backup automático (además del manual)

**Lo que dijo el cliente:** el backup tiene que ser también automático, cada
cierto tiempo, y que se pueda seguir haciendo uno manual cuando quieran.

**Cómo está hoy:** solo el manual (Admin → Backup de datos, PR #291). El
automático figuraba como "segundo PR del #52" en `docs/BACKUPS.md`, pero el
**#52 está CERRADO** → reabrirlo o crear un issue nuevo.

**Cómo hacerlo (a decidir):**
- **Disparador:** Render free no tiene cron jobs (son pagos). Opciones: un
  workflow de GitHub Actions con `schedule` que le pegue a un endpoint
  protegido con token (ej. `/admin/backup/auto`), o que genere el backup
  conectándose a la base. Se reusa `generar_backup_zip()`
  (`services/backup.py`).
- **Destino:** el automático tiene que quedar **fuera de Supabase** (es el
  sentido del #52). Opciones: mail con el .zip adjunto (`send_mail` ya
  soporta adjuntos; Resend tiene límite de tamaño por mail) o Google Drive de DML.
  Ojo: el archivo es sensible (datos de clientes + hashes de contraseñas).
- Mostrar en la pantalla de Backup cuándo corrió el último automático y si
  falló.

**Para aclarar con el cliente:**
- [ ] ¿Cada cuánto? (sugerencia: semanal, o diario si hay mucho movimiento)
- [ ] ¿Dónde lo quieren recibir? ¿Mail (a qué casilla) o una carpeta de Drive?
- [ ] ¿Cuántos backups viejos guardar?

Tamaño estimado: M.

---

## 10. Descargar el stock en Excel

**Lo que dijo el cliente:** que el stock se pueda descargar en un Excel.

**Cómo está hoy:** existe a medias. En `/stock` hay un botón verde **"CSV"**
(`export_stock_csv()` en `estadisticas.py`) que baja Código / Descripción /
Stock DML / Stock RAYPAC / Stock Total. Problemas:
- Es **CSV con comas y UTF-8 sin BOM**: en un Excel en español suele abrirse
  todo en **una sola columna** y con los acentos rotos.
- El botón lo ve también **DML_ST**, pero la ruta no lo deja pasar
  (`role_required("ADMIN","DML_REPUESTOS","RAYPAC")`): le aparece un error o
  lo redirige.
- Exporta siempre las dos ubicaciones: RAYPAC baja el stock de DML aunque
  en la pantalla solo ve el suyo (relacionado con el punto 4).
- No incluye la ubicación física (puntos 5 y 7).

**Propuesta:** cambiarlo por un **.xlsx real** (`openpyxl` ya está en
`requirements.txt`), con encabezados en negrita, columnas con ancho
ajustado, filtro automático y la columna de ubicación física. Botón
"Descargar Excel". Alinear los roles. De paso, revisar los otros
exports CSV (fichas en `/dml`, RAYPAC). Tamaño estimado: S.

---

## 11. Permisos de stock: RAYPAC solo ver y descargar; todos descargan

**Lo que dijo el cliente:**
- RAYPAC: **solo ver y descargar** el stock. Nada de crear, editar ni borrar.
- DML_REPUESTOS y DML_ST (técnico): también pueden **descargar**.

**Cómo está hoy (`stock.py` + `stock_list.html`):**
| Acción | ADMIN | RAYPAC | DML_ST | DML_REPUESTOS |
|---|---|---|---|---|
| Ver `/stock` | sí (DML y RAYPAC) | sí, **escritura**, solo su ubicación | solo lectura | escritura |
| Nuevo repuesto (`stock_new`) | sí | **sí** ❌ | sí | no |
| Editar (`stock_edit`) | sí (pide contraseña) | no | sí | no |
| Eliminar (`stock_delete`) | sí | no | no | no |
| Descargar CSV | sí | sí | **no** ❌ (ve el botón pero rebota) | sí |

**Cambios:**
- `stock_list`: sacar RAYPAC de `write_roles` y pasarlo a `read_roles`.
- `stock_new`: sacar RAYPAC del `role_required`. Ocultarle "+ Nuevo Repuesto".
- `export_stock_csv`: sumar DML_ST (queda para los 4 roles). Va junto
  con el punto 10 (Excel real).

**Para aclarar con el cliente:**
- [ ] ¿Qué stock ve y descarga RAYPAC: **el de DML** (para saber qué
      pedir, punto 4), el suyo, o los dos? Hoy la pantalla le muestra solo
      RAYPAC y el CSV le baja los dos.
- [ ] La tabla muestra una inconsistencia vieja: DML_ST puede crear y
      editar, pero DML_REPUESTOS (el encargado de repuestos) no. ¿Quién
      tiene que poder crear y editar stock en DML? (Relacionado con
      "Editar ubicación", punto 7.)

Tamaño estimado: XS–S.

---
