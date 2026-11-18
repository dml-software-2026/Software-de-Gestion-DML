# Respuestas y observaciones del cliente — 2026-11-15

El 2026-11-15 el cliente devolvió tres documentos. **No se versionan** porque el
repo es público y tienen datos de clientes (empresas, N° de serie, el mail
personal de una persona de RAYPAC). Los tiene Facu:

1. `Consultas_DML_noviembre_2026.docx`: las preguntas de
   `docs/PREGUNTAS_CLIENTE_2026-11-02.md`, respondidas por David.
2. `Observaciones SOFTWARE.docx`: una lista nueva de observaciones sobre la app,
   con capturas de la demo del 28/10. No es la misma que `Observaciones del
   soft.docx` de la raíz, que es de 2025.
3. `ficha_0000844 MODIFICADA.docx`: el PDF de una ficha cerrada pasado a Word,
   con las correcciones marcadas en rojo.

Todo quedó en el kanban: respuestas comentadas en los issues existentes y
**issues nuevos #323-#342**.

---

## 1. Respuestas de David

| # | Pregunta | Respuesta | Issue |
|---|---|---|---|
| 1 | ¿Toda máquina enviada a DML lleva remito? | "Toda máquina y/o repuesto viene con remito." | #305 |
| 2 | ¿El mail de "máquina lista" al comercial es correcto? | Sí, y con copia a Daniela Sofio (RAYPAC). El mail lo tiene Facu. | #307 (hecho en #322), #323 |
| 3.1 | El aviso de pedido de repuestos, ¿campanita o mail? | También por mail, y "lo mismo cuando llega una máquina". A `service@dmlelectricidadind.com.ar`. | #341, #324 |
| 3.2 | El envío de DML a RAYPAC, ¿lleva remito? ¿Se confirma la recepción? | Hoy no, pero quieren empezar a hacer remitos, y la confirmación de recepción valida las cantidades. | #342 |
| 4 | ¿El encargado de repuestos también edita los repuestos? | Sí. | #313 (hecho en #320) |
| 5.1 | ¿La ubicación la cambian el técnico y el de repuestos? | "Perfecto así." | #309 (hecho) |
| 5.2 | ¿RAYPAC ve la ubicación? | No, le alcanza con ver el stock. | #320 (hecho), #312 (export) |
| 5.3 | ¿La ubicación se pide solo para los repuestos nuevos? | Las existentes no se tocan pero se pueden editar, y los que nunca entraron necesitan una al llegar. | #309 (hecho en #319) |
| 6.1 | ¿Cada cuánto el backup automático? | Una vez por semana. **Nos pregunta si se hace aunque no haya movimientos** (hay que contestarle; propuesta: sí, siempre). | #311 |
| 6.2 | ¿A qué mail va el backup? | `service@dmlelectricidadind.com.ar` | #311, #323 |
| 7 | SP00034, ¿es el SP00367 (GRIPPER PLATE)? | No: es el **CLAMP PLATE CT25**. Cargarlo con stock 0 y ubicación **E06-F03-B04**. | #314 |
| 8 | ¿La ficha incluye la parte de mano de obra con "Sin cargo"? | Sí, y además una opción **"En garantía"**. | #331 |

## 2. Observaciones SOFTWARE

**Importante:** las capturas son del **usuario Administrador**. Varias quejas de
"RAYPAC ve cosas que no son suyas" probablemente vienen de haber probado todo con
ADMIN (ver #336).

| Observación | Issue |
|---|---|
| RAYPAC: ver solo sus funciones (sin Nuevo Usuario ni Nuevo Repuesto) y no dar de alta en DML en ningún lado | #336 |
| Envío de repuestos: buscador, Guardar arriba o fijo, "repuesto no listado" arriba | #337 |
| Envío de repuestos: guardar y editar antes del remito, que se pide recién al freezar | #338 |
| Botón "Atrás" en todas las pantallas | #335 |
| Solapa Envíos: elegir entre envío de repuestos y nuevo ingreso de máquina | #339 |
| Nuevo ingreso: modelo "OTRA" con nombre manual (cargador, batería suelta) | #340 |
| Remito del ingreso a mano, no el N° de serie | #305 |
| Técnicos: elegir entre Ricardo y David | #327 |
| Al generar el ticket, mail al cliente | #325 |
| Ticket impreso: tiene que decir RAYPAC SRL | #326 |
| Crear ficha va directo a la edición, con un orden nuevo de secciones | #328 |
| "Reparación completada" pasa a "REPARADA" | #329 |
| PDF con fechas día/mes/año | #332 |
| La ficha se edita hasta que RAYPAC la recibe; después la edita RAYPAC con clave; el OK de RAYPAC cierra el circuito | #333 |
| Estado del equipo: OTROS como texto libre que sale en la ficha cerrada | #330 |
| Barra negra de arriba fija en todas las pantallas | #335 |
| Máquinas Entregadas: "N° de Serie", fecha de entrega, recibido por, contacto y mail | #334 |

## 3. Ficha 0000844 modificada (PDF de la ficha)

Todo en el **#332**: título de la empresa en cuerpo 14 y negrita, "EQUIPO
REPARADO" en vez de "EN REVISIÓN", "Servicio Técnico" en cuerpo 14, fechas
dd/mm/aaaa, observaciones y diagnóstico reales de la ficha cerrada (sin textos de
relleno), repuestos con solo cantidad, código y descripción en mayúscula, y el
nombre del archivo en mayúscula. La parte de "Sin cargo / En garantía" va en el
#331.

## 4. Otros issues nuevos que salieron de esta ronda

- #323: configurar los mails en producción (sacar `MAIL_DEV_REDIRECT` en Render y cargar destinatarios).
- #324: mail a DML cuando RAYPAC envía una máquina.
- #341 y #342: el #308 (pedidos de repuestos) partido en dos sub-issues.
