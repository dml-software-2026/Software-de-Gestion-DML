El motivo de esta carga inicial es para que David pueda ver la implementacion del historial previo al servicio web para que quede registrado en el sistema con tal de que no haga falta seguir con el excel cuando termine la Practica Profesionalizante por objetivo.

La forma en la que este proceso fue llevado a cabo es mediante la utilizacion de "Pandas", una libreria de python que permite leer, ordenar y reestructurar datos de un archivo excel. 

En la segunda reunion con David le habiamos pedido el historial que ellos tenian sobre las maquinas con las que trabajaban, para poder tener una mejor idea de como poder guardar estos datos en la base de datos. 

Hasta entonces, DML sigue trabajando con el mismo archivo excel (Planilla de reparacion interna), por ende, debera ser actualizado una vez que se ponga en practica el servicio web por parte de Raypac Y DML.

Las columnas de la planilla fueron ruteadas a las de los campos de ingreso raypac (raypac_entries), las fichas de dml (dml_fichas), el estado general de las maquinas (estado_general) y el stock que fue usado para la maquina (dml_stock)

Una vez establecido el schema de la base de datos con Pandas, ademas de archivos csv de las 4 tablas mencionadas, los siguientes archivos fueron generados: Ingresos con error.csv & insert all.sql

Ingresos con error.csv son aquellas fichas en la planilla que contienen datos conflictivos ante el schema PostgreSQL de la base de datos, como por ejemplo: "Codigo de repuesto inexistente", "Numero de ficha invalida", "Fecha de ingreso faltante/invalida", entre otras.

La forma en la que esto podia ser solucionado era mediante la confirmacion por parte de DML, de que estos ingresos invalidos podrian ser corregidos con las soluciones que el equipo dio a entender. (Lo cual no llego a ser posible debido a que aparentemente DML hasta el dia de hoy no respondio a estos archivos, lo unico que obtuvimos ante este tema fue una llamada por parte de Ricardo, estableciendo una medida de alcance ya vista. La confirmacion de Ricardo no fue prometedora, lo cual significa tener que realizar la solucion deducida por el equipo para la reunion de la primera entrega, y dejarla ahi hasta que David pueda responder las preguntas acerca de estos ingresos con errores)

insert all.sql no es nada mas que el script de carga para el editor en supabase que permite crear todos esos ingresos con un boton.

La unica observacion a esto es que como el excel no fue pensado para satisfacer los requerimientos del servicio web, hay datos faltantes debido a que los campos de ingreso pide informacion que la Planilla no posee, entonces son rellenadas con datos nulos/historicos.