# Preguntas para el cliente — borrador del 2026-11-02

Preguntas que salieron de la entrega del 2026-10-28 (`docs/NOTAS_ENTREGA_2026-10-28.md`)
y de los archivos que pasó el cliente. Cada punto indica su issue.

**Estado: versión final, revisada con el equipo (2026-11-09), todavía no se mandó.**

- Revisada con los comentarios de Sebastián: se sacaron las preguntas ya respondidas
  (formato y repetición del remito, subdominios del mail) y las que sumaban alcance
  (stock propio de RAYPAC, ubicación propia de RAYPAC). La planilla de stock (punto 6
  viejo) se sacó: las cantidades las ajusta el cliente; antes de cargarla en prod,
  revisar si hubo movimientos después del 31/08 (#310).
- Backup: Sebastián proponía guardarlo dentro del sistema; quedó por mail porque Render
  free no guarda archivos y una copia en la misma base no protege si se pierde la base.
  Se sacó Google Drive (complejo).
- Ubicación: se sacó "código entero o 4 casilleros" (el PR #316 de Ivo ya usa un solo
  campo que normaliza el formato).
- La versión para el cliente se armó como Word (`Consultas_DML_noviembre_2026.docx`,
  sin números de issue, con un recuadro de respuesta por pregunta).
- Cuando respondan, anotar cada respuesta en su issue.

---

**Hola David, ¿cómo estás?** Después de la entrega del 28/10 pasamos en limpio todo
lo que nos comentaron en la demo y ya lo estamos trabajando. Para hacer bien algunas
cosas necesitamos que nos confirmes estos puntos:

## 1. Remito al enviar la máquina a DML (#305)

Entendimos mal un pedido anterior: hoy, al enviar la máquina a DML, el sistema
completa el remito solo, con el número de serie de la máquina. Lo vamos a corregir
para que RAYPAC vuelva a cargar el remito a mano, como antes: se escribe solo el
número (por ejemplo `4321`) y el sistema lo completa con ceros (`00001-00004321`).
También va a aceptar varias máquinas con el mismo remito (cuando viajan juntas).
Una sola duda:

- ¿Toda máquina que se envía a DML lleva remito? ¿O hay casos en que se manda sin
  remito (por ejemplo, si se lleva en mano en vez de mandarla en camión)?

El ticket sigue llevando el número de serie, y la ficha sigue siendo correlativa, como
nos pidieron.

## 2. Mail de "máquina lista para retirar" (#307)

Ese aviso ya existe: cuando DML cierra la ficha, le llega un mail al comercial
responsable que se cargó en el ingreso.

- ¿Es la persona correcta, o también tiene que llegarle a alguien más (el cliente
  final, alguien de RAYPAC)?

## 3. Pedidos de repuestos de RAYPAC a DML (#308)

Hoy el sistema solo maneja envíos de repuestos de RAYPAC hacia DML. Vamos a armar el
circuito al revés: RAYPAC ve el stock de DML para saber qué pedir, hace el pedido, a
DML le llega el aviso y DML envía. Para eso necesitamos saber:

- El aviso del pedido, ¿alcanza con la campanita dentro del sistema o también tiene
  que llegar por mail?
- Cuando DML envía los repuestos, ¿el envío lleva remito? ¿RAYPAC tiene que confirmar
  que los recibió?

## 4. Permisos sobre el stock (#313)

Vamos a dejar a RAYPAC solo para ver y descargar el stock, como pidieron. Una duda: hoy
el encargado de repuestos de DML puede dar de alta repuestos nuevos, pero no editar los
que ya existen (eso lo puede hacer el técnico). ¿El encargado de repuestos también
tendría que poder editarlos?

## 5. Ubicación física de los repuestos (#309)

Vamos a usar el formato de ubicación de su planilla de stock (por ejemplo
`E05-F04-PB-B02`: estante, fila, posición y box).

- Pensamos que la ubicación la puedan cambiar el técnico y el encargado de repuestos
  de DML. ¿Está bien, o tiene que ser alguien más?
- RAYPAC, ¿también tiene que ver dónde está guardado cada repuesto, o eso queda solo
  para DML?
- Al recibir un envío de repuestos, ¿la ubicación se pide solo para los repuestos
  nuevos o que todavía no tienen ubicación? (Si ya la tienen, aparecería cargada.)

## 6. Backup automático (#311)

Vamos a sumar un backup automático, además del botón manual que ya existe: el sistema
les va a mandar por mail una copia de todos los datos cada cierto tiempo.

- ¿Cada cuánto quieren recibirlo? (Sugerimos una vez por semana, o todos los días si
  hay mucho movimiento.)
- ¿A qué casilla lo mandamos? (Mejor una de DML que no use todo el mundo, porque el
  archivo tiene datos de clientes.)

## 7. Un código de repuesto (#314)

En la carga del historial aparece el código **SP00034**, que no está en la planilla de
stock. En el archivo de correcciones pusieron "GRIPPER PLATE". ¿Se refiere al
**SP00367** (GRIPPER PLATE CTT20-25) o es otro repuesto?

## 8. Parte de facturación de la ficha (sin issue todavía)

En la ficha en papel actualizada aparece la sección de mano de obra / presupuesto con
la opción nueva "Sin cargo". El sistema hoy no tiene esa sección (solo horas
adicionales). ¿Quieren que la ficha del sistema la incluya?

¡Gracias! Con esto podemos avanzar con todo.
