# Fase 2 - Migración PostgreSQL

## Contexto (Fase 1)

Previamente, en la Fase 1 de la migracion, se establece que el motivo a este proceso es debido a que la base de datos que la corte anterior pretendio armar, no solo es volatil, sino que inexistente a la vez.

## Motivo de la Fase 2

El motivo de la Fase 2 es modificar las funciones del codigo para asi realmente poder manipular la base de datos, que reside en supabase, desde el servicio web. De manera que SQLite3 es cambiado con funciones de PostgreSQL/Psycopg2

Principalmente, el proceso fue en base a los blueprints del sistema, modificando sus funciones y migrando sus contenidos que tratan SQLite3 a PostgreSQL.

## Troubleshooting de errores

Pero al terminar estas modificaciones ocurrieron abundantes cantidades de "error 500 internal server error", las cuales fueron capaces de poder realizar su troubleshoot mediante los logs del servicio web en el build de Render.

Por cada error arreglado, hubo un push origin de un commit que lidiaba con ese error.

Estos errores fueron encontrados a medida que se iba probando el sistema en su totalidad, incluyendo el flujo de trabajo, creacion de usuarios, stock, entre todas las funcionalidades posibles.

## Observación de rendimiento

Una observacion notoria a declarar, es que la redireccion interna en el sistema, ya sea haciendo cualquier click que te lleve a una nueva, es muchisimo mas lenta, promediando en medio minuto a cargar (anteriormente eran 4 segundos).

## Proceso de prueba (primera entrega DML)

La manera en la que el proceso de prueba por parte de DML en la primera entrega a realizar sera llevado a cabo es la siguiente:

David accedera al sitio web en el entorno de development, lo cual le permitira llevar a cabo el flujo de trabajo promedio (Ingreso Raypac > Recepcion DML > Ticket > Ficha > Cierre de ficha). A todo este proceso el equipo tendra presente informacion en la base de datos sobre como los movimientos realmente estan siendo realizados y almacenados aun asi con el servicio web dado de baja, demostrando que no es una base de datos volatil, y que existe.

### Aclaración de seguridad (urgente)

Lo mas importante y urgente para aclarar es que luego de la reunion, estos datos seran borrados de la base de datos por cuestiones de seguridad (Cualquier persona que tenga la direccion URL a la pagina web puede acceder a la base de datos alojada en el servicio web. Esto sera arreglado para futuras entregas.) La carga inicial no es mas que una muestra de que nuestro trabajo esta presente.