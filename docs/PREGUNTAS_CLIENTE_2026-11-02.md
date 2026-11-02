# Preguntas para el cliente — borrador del 2026-11-02

Preguntas que salieron de la entrega del 2026-10-28 (`docs/NOTAS_ENTREGA_2026-10-28.md`)
y de los archivos que pasó el cliente. Cada punto indica su issue.

**Estado: BORRADOR, todavía no se mandó.** Próximos pasos:

1. Facu se lo pasa a sus compañeros. Algunas preguntas puede que ya se le hayan
   hecho al cliente antes: Facu trae qué hay que sacar o cambiar.
2. Con eso, armar la versión final como **Google Doc** (prolija, con espacio para
   que el cliente responda en el mismo doc, porque el mensaje es largo).
3. Cuando respondan, anotar cada respuesta en su issue.

---

**Hola David, ¿cómo estás?** Después de la entrega del 28/10 pasamos en limpio todo
lo que nos comentaron en la demo y ya lo estamos trabajando. Para hacer bien algunas
cosas necesitamos que nos confirmes estos puntos:

## 1. Remito al enviar la máquina a DML (#305)

Entendimos mal un pedido anterior e hicimos que el sistema use el número de serie de
la máquina como remito. Lo vamos a corregir para que RAYPAC vuelva a cargar el remito
a mano. Para eso necesitamos saber:

- ¿El remito es obligatorio para poder enviar la máquina?
- ¿Sigue el formato `00001-XXXXXXXX`?
- ¿Puede haber dos máquinas con el mismo número de remito?

El ticket sigue llevando el número de serie, y la ficha sigue siendo correlativa, como
nos pidieron.

## 2. Mail de "máquina lista para retirar" (#307)

Ese aviso ya existe: cuando DML cierra la ficha, le llega un mail al comercial
responsable que se cargó en el ingreso.

- ¿Es la persona correcta, o también tiene que llegarle a alguien más (el cliente
  final, alguien de RAYPAC)?
- Para que los mails lleguen a casillas reales hace falta configurar los dos
  subdominios que te explicamos en el documento del dominio (`raypac-dev` y
  `raypac-prod`). ¿Pudiste hacerlo? Si querés, lo vemos juntos.

## 3. Pedidos de repuestos de RAYPAC a DML (#308)

Hoy el sistema solo maneja envíos de repuestos de RAYPAC hacia DML. Para armar el
circuito al revés (RAYPAC pide, a DML le llega el aviso y DML envía) necesitamos saber:

- Cuando dicen que RAYPAC "pueda ver el stock": ¿es el stock de DML, para saber qué
  pedir? ¿El suyo? ¿Los dos?
- El aviso del pedido, ¿alcanza con la campanita dentro del sistema o también tiene
  que llegar por mail?
- Cuando DML envía los repuestos, ¿el envío lleva remito? ¿RAYPAC tiene que confirmar
  que los recibió?
- ¿Quieren llevar en el sistema el stock de RAYPAC, para que se sume cuando recibe los
  repuestos?

## 4. Permisos sobre el stock (#313)

Vamos a dejar a RAYPAC solo para ver y descargar el stock, como pidieron. Una duda: hoy
el encargado de repuestos de DML puede dar de alta repuestos nuevos, pero no editar los
que ya existen (eso lo puede hacer el técnico). ¿El encargado de repuestos también
tendría que poder editarlos?

## 5. Ubicación física de los repuestos (#309)

Vamos a usar el formato de ubicación de su planilla de stock (por ejemplo
`E05-F05-B02`: estante, fila, posición y box).

- Para cargarla, ¿prefieren escribir el código entero, o completar 4 casilleros
  separados (estante, fila, posición, box) y que el sistema arme el código solo?
- ¿Quién tiene que poder cambiar la ubicación de un repuesto?
- ¿La ubicación es solo para el stock de DML, o RAYPAC también quiere cargar la suya?
- Al recibir un envío de repuestos, ¿la ubicación se pide solo para los repuestos
  nuevos o que todavía no tienen ubicación? (Si ya la tienen, aparecería cargada.)

## 6. Planilla de stock (#310)

Vamos a cargar en el sistema la planilla de stock que nos pasaron (*Copia de NUEVO
STOCK DE REPUESTOS COMPLETO*). En el encabezado dice "Stock de Servicio Técnico al
31/08/2026". Al cargarla se reemplazan las cantidades del sistema, así que queremos
asegurarnos:

- ¿Las cantidades están actualizadas a hoy, y solo quedó vieja la fecha del
  encabezado?
- Si hubo movimientos después (repuestos usados o recibidos), ¿nos pasarían la
  versión más nueva?

## 7. Backup automático (#311)

Vamos a sumar un backup automático, además del botón manual que ya existe.

- ¿Cada cuánto quieren que se haga? (Sugerimos una vez por semana, o todos los días si
  hay mucho movimiento.)
- ¿Dónde lo quieren recibir? ¿Por mail (a qué casilla) o en una carpeta de Google
  Drive?
- ¿Cuántos backups viejos quieren guardar?

## 8. Un código de repuesto (#314)

En la carga del historial aparece el código **SP00034**, que no está en la planilla de
stock. En el archivo de correcciones pusieron "GRIPPER PLATE". ¿Se refiere al
**SP00367** (GRIPPER PLATE CTT20-25) o es otro repuesto?

## 9. Parte de facturación de la ficha (sin issue todavía)

En la ficha en papel actualizada aparece la sección de mano de obra / presupuesto con
la opción nueva "Sin cargo". El sistema hoy no tiene esa sección (solo horas
adicionales). ¿Quieren que la ficha del sistema la incluya?

¡Gracias! Con esto podemos avanzar con todo.
