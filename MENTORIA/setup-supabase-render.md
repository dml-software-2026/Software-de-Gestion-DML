# Como se creo el proyecto #

- Te registras o inicias sesion en el sitio oficial de Supabase
- Vas al dashboard de tu cuenta
- Creas una organizacion
- Creas dos proyectos: Uno para el entorno dev y otro para el entorno prod
- Entras a ambos proyectos y haces click en el boton "connect" situado en la barra superior del sitio web
- Vas a la seccion "Direct", elegis el Connection Method y copias y guardas la connection String

# Donde viven las credenciales #

Las credenciales viven en las variables de entorno dentro del deploy de render.

# Como obtener la connection string #

- Entras a cualquiera de los dos proyectos y haces click en el boton "connect" situado en la barra superior del sitio web
- Vas a la seccion "Direct", elegis el Connection Method, Type y copias y guardas la connection String

# Como probrar la conexion # 

- La mas segura y directa sin que estropee demas es descargando postgresql
- En Windows CMD Usas el siguiente comando: "set DATABASE_URL=[CONNECTION STRING]" 
- Eso es para preparar y conectarse con la base de datos, lo que sigue es ejecutar la conexion en tiempo real
- "psql "%DATABASE_URL%" y desde ahi podes acceder a la base de datos.

## Troubleshooting ##


