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

- En el caso de que psql no sea reconocido como comando ("'psql' is not recognized"):
  Falta agregar la carpeta bin de PostgreSQL al PATH de Windows. Buscar
  "Variables de entorno" > Variables del sistema > Path > Nuevo > pegar la ruta
  (ej: C:\Program Files\PostgreSQL\18\bin). Cerrar y volver a abrir la terminal.

- Error "could not translate host name ... to address: Name or service not known":
  Significa que estás usando la connection string de "Direct connection"
  (host tipo db.xxxxx.supabase.co), que requiere IPv6 y tu red no lo soporta.
  Solución: usar la connection string de "Session pooler" en su lugar
  (host tipo aws-0-region.pooler.supabase.com, puerto 5432).

- Error "password authentication failed for user postgres":
  Revisar que no haya quedado el placeholder [YOUR-PASSWORD] literal en el
  comando en vez de la password real. Si la password tiene caracteres
  especiales (@, #, %, /), hay que codificarlos en URL-encoding o conectar
  con flags separados en vez de la URL completa:
  psql -h HOST -p 5432 -d postgres -U postgres.PROJECT_REF

- Diferencia entre los tres tipos de connection string:
  - Direct connection (5432, db.xxxxx.supabase.co): requiere IPv6, uso puntual.
  - Session pooler (5432, ...pooler.supabase.com): usar para conexiones
    manuales/largas (psql interactivo, migraciones, debugging).
  - Transaction pooler (6543, ...pooler.supabase.com): usar para la app en
    Render (muchas conexiones cortas y concurrentes).

- Si el proyecto está en el plan Free y no conecta:
  Verificar que no esté "paused" por inactividad. Se resume manualmente
  desde el dashboard de Supabase.
