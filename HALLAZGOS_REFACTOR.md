# Hallazgos del refactor de app.py

Encontrados durante la modularización de `app.py` (branch
`refactor/modularizar-app-py`) y durante el testing manual posterior.
No se resuelven en este refactor - se documentan acá para no perderlos,
especialmente porque el squash-and-merge borra el detalle de los commits
individuales.

## Seguridad (Épica 2)

1. **Hashes de contraseñas hardcodeados** - bloque `CORRECT_HASHES` en
   `migrate_db()` (app.py original, líneas ~449-465). Se reescriben en cada
   arranque del server. Ivo ya tiene esto en su tarea (#64/#65).

2. **Código de desbloqueo "ADMIN2024" hardcodeado** - aparece repetido
   5 veces en todo el proyecto:
   - `raypac_edit`
   - `dml_edit`
   - `stock_new`
   - `stock_edit`
   - `stock_delete`
   Candidato claro para centralizar en una sola variable de entorno.

3. **`/admin/cargar-stock-csv` sin ningún decorador de autenticación**
   (función `cargar_stock_desde_web`). Cualquiera con la URL puede
   reescribir todo el stock del sistema. Ya cargado como tarea en el
   Kanban (#62 lo detectó, falta la protección puntual de este endpoint).

## Código roto (confirmado con testing real, no solo lectura)

4. **`verificar_stock_api` (`/api/verificar-stock/<codigo>`) está roto.**
   - Usa una variable `db` que nunca se define (falta `get_db()`) -> tira
     `NameError: name 'db' is not defined`, confirmado con status 500 real
     en Network tab del navegador.
   - Consulta una tabla `stock_repuestos` que no existe en ningún otro
     lugar del proyecto (el resto usa `stock_ubicaciones` + `matriz_repuestos`).
   - **Impacto real detectado en testing:** el JS de "Agregar Repuesto" en
     `dml_edit.html` llama a esta API para validar stock antes de agregar.
     Como la API siempre falla (500), el JS muestra la advertencia
     "Este repuesto NO tiene stock disponible" incluso con repuestos que sí
     tienen stock real en DML (confirmado con A000006, A000007, A000038 -
     todos con stock > 0 y aun así marcados sin stock por el cartel previo).
   - El guardado real en el servidor SÍ valida bien contra `stock_ubicaciones`
     (confirmado: A000038 se guardó correctamente como EN STOCK pese al
     cartel de advertencia falso) - el bug es solo en el aviso previo de JS,
     no corrompe datos.
   - Recomendación: arreglar (agregar `get_db()` y corregir tabla/columnas)
     o eliminar si no se usa para nada más, y revisar el JS de
     `dml_edit.html` que la llama innecesariamente ya que el servidor ya
     valida esto igual al guardar.

5. **Botón "Generar Ficha" nunca conectado al frontend.**
   - La ruta `dml.generar_ficha` (`/dml/<id>/generar-ficha`) existe y
     funciona en el backend (usa el generador de PDF `generate_ficha_pdf`
     con logo, marca `ficha_generada=1`, intenta mandar mail al comercial).
   - Confirmado revisando `dml_view.html` completo: no hay ningún link o
     `<form>` en el template que apunte a esta ruta, con ninguna condición
     de estado. Es código huérfano - existe en el servidor pero no hay
     forma de dispararlo desde la interfaz.
   - Recomendación: agregar el botón faltante (condicionado a
     `ficha.estado_reparacion == 'MÁQUINA LISTA PARA RETIRAR'`) o, si ya no
     hace falta (por ejemplo si `descargar_ficha_pdf` cubre el caso de uso),
     eliminar la ruta completa.

6. **Botón "Acuse" en `/dml/entregadas` no abre el modal.**
   - Usa sintaxis de Bootstrap 4 (`data-toggle="modal"`,
     `data-target="#modalAcuse1"`) en un proyecto que carga Bootstrap 5.3.3
     (`base.html` confirma la versión). Bootstrap 5 requiere el prefijo
     `bs-`: `data-bs-toggle="modal"`, `data-bs-target="#modalAcuse1"`.
   - Sin el prefijo correcto, Bootstrap 5 ignora los atributos
     silenciosamente - no tira error en consola, el modal simplemente
     nunca se abre.
   - Confirmado con testing real: click en "Acuse" no hace nada, sin
     errores propios de la app en consola (los únicos errores en consola
     eran de extensiones del navegador, ajenos al proyecto).
   - Recomendación: en `dml_entregadas.html`, agregar el prefijo `bs-` a
     los atributos `data-toggle`/`data-target` del botón de Acuse.

## Sin resolver, no urgente

7. **Dos generadores de PDF distintos, sin unificar**
   - `generar_ficha_pdf` (usado en `/dml/<id>/pdf`, descarga on-demand)
   - `generate_ficha_pdf` (usado en `/dml/<id>/generar-ficha`, botón
     "generar ficha final" - actualmente huérfano, ver hallazgo #5)
   - Un tercero, `generate_ficha_pdf_new`, vive en `pdf_generator_new.py`
     y no está integrado a la app (según el plan de ordenamiento de
     Matías). No se unifican este sprint - queda para issue aparte.
   - Detalle adicional confirmado con testing: `generar_ficha_pdf` tiene
     un texto de relleno hardcodeado ("Pendida de potencia, cuchilla
     gastada" - con error de tipeo, "Pendida" en vez de "Pérdida") que
     aparece en el PDF cuando el campo `diagnostico_inicial` está vacío,
     en vez de mostrar algo vacío o un texto genérico tipo "Sin
     diagnóstico". Parece un dato de prueba olvidado.

9. **Desplegables inconsistentes entre sí (nativo `<select>` vs. custom armado
   a mano).** Encontrado probando el checklist manual del #54: el campo
   Cliente en `raypac_form.html` es un `<input>` de texto libre con una lista
   de sugerencias armada a mano (`<ul class="dropdown-menu">` + JS), necesario
   porque soporta autoaprendizaje (RF03) - un `<select>` no puede. El resto de
   los campos de selección de la app son `<select class="form-control">`
   nativos. Un `<select>` nativo no se puede stylear para que su lista
   desplegada coincida pixel a pixel con un widget armado en HTML/CSS (el
   navegador/SO dibuja esa lista, no Bootstrap) - por eso conviven dos looks
   distintos.
   - **Alcance confirmado (2026-08-19):** 31 `<select>` en 11 templates,
     de los cuales 3 son archivos backup/muertos ya candidatos a borrar más
     abajo (`dml_view_OLD.html`, `dml_edit_FIXED.html`,
     `dml_edit_BACKUP.html`) → quedan **~24 selects reales en 8 templates
     vivos**: `raypac_form.html` (5), `ticket_nuevo.html` (12),
     `dml_edit.html` (2), `envios_form.html`, `ficha_view.html`,
     `tickets_list.html`, `usuario_form.html`, `usuario_edit.html` (1 c/u).
   - **Decisión de Facu (2026-08-19):** no se ataca en el sprint E2 actual
     (riesgo de corte de alcance del #54 ya anotado, no forma parte de su
     DoD). Candidato a issue propio: reemplazar los `<select>` nativos por
     el mismo patrón de dropdown-menu armado a mano que ya tiene Cliente,
     de a un template/grupo chico por PR. Ojo con la accesibilidad de
     teclado/lector de pantalla al reimplementar - un `<select>` nativo la
     tiene gratis, un dropdown armado a mano no.

## Archivos viejos / de backup dando vueltas (candidatos a borrar)

8. `CODIGO_FUENTE/app_backup.py` (ya en proceso de eliminación, branch
   `chore/eliminar-app-backup-obsoleto`).

9. En `INTERFAZ/templates/`: `dml_view_OLD.html`, `dml_edit_FIXED.html`,
   `dml_edit_BACKUP.html` - no referenciados por ningún `render_template()`
   del código actual, probablemente de la cohorte anterior.

---

## Testing manual realizado (post-refactor)

Se probó manualmente cada blueprint con los 4 roles del sistema
(ADMIN, RAYPAC, DML_ST, DML_REPUESTOS) sobre una base de datos limpia:
login/logout, ingreso RAYPAC completo (crear/ver/editar/freezar), ticket
(creación + vista pública sin login), ficha DML completa (crear, editar,
agregar repuestos en stock y en falta, mover a stock, descargar PDF,
cerrar ficha con validaciones), envíos de repuestos (crear + confirmar
recepción), stock (listar, buscar, crear, editar), usuarios (crear,
editar, activar/desactivar), y los 3 exports CSV (fichas, stock, raypac).

Conclusión: el refactor es funcionalmente equivalente al `app.py`
monolítico original. Todo lo probado funciona igual (o falla igual, en
los casos de bugs pre-existentes documentados arriba) que antes de
separar el código en blueprints.
