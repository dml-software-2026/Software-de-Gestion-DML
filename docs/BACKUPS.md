# Backups de la base de datos

Pedido de David (reunión 2026-07-02, issue #52): tener una copia de los datos
**fuera de Supabase**, porque si todo está en el mismo servicio "se te cae el
original y se te cae la copia". Supabase hace su propio backup diario, pero
queda dentro de Supabase - esto es la segunda copia, guardada por la empresa.

## Cómo hacer un backup

1. Entrar al sistema con un usuario **ADMIN**.
2. Menú **Admin → 💾 Backup de datos**.
3. **Descargar backup**. Baja un archivo `backup_dml_AAAA-MM-DD_HHMM.zip`.

La misma pantalla muestra cuándo se descargó el último backup y quién lo hizo.

### Qué tiene el .zip

| Archivo | Para qué sirve |
|---|---|
| `csv/*.csv` | Una planilla por tabla (fichas, ingresos RAYPAC, tickets, stock...). Se abren con Excel para consultar datos sin depender del sistema. |
| `backup.sql` | Estructura + datos completos, para **restaurar** el sistema (ver abajo). |
| `LEEME.txt` | Fecha del backup y cantidad de filas por tabla. |

> **El archivo es sensible:** tiene datos de clientes y las contraseñas
> (cifradas) de los usuarios. No mandarlo por mail ni dejarlo en una carpeta
> compartida abierta.

## Cuándo y dónde guardarlo

- **Frecuencia sugerida:** una vez por semana, y siempre antes de un cambio
  grande del sistema (actualización a producción, carga masiva de stock, etc.).
- **Dónde:** en **dos lugares distintos** que no sean Supabase - por ejemplo
  una PC de la empresa + un pendrive/disco externo o un Google Drive de DML.
- **Cuántos guardar:** alcanza con los últimos 4-5 (un mes). Los más viejos se
  pueden borrar.

## Cómo restaurar

Solo hace falta si se perdieron o se rompieron los datos de Supabase. **Lo
hace alguien del equipo de desarrollo**, no desde la app (un botón que pisa
toda la base es demasiado peligroso - decisión del #52).

`backup.sql` funciona sobre cualquier base Postgres (versión 13 o más nueva):
borra las tablas del sistema que haya y las vuelve a crear con los datos del
backup. Se puede correr sobre una base vacía o sobre la misma base rota.

### 1. Elegir dónde restaurar

- **Si Supabase sigue andando pero los datos están mal:** restaurar sobre la
  misma base (se pierde todo lo cargado después del backup).
- **Si se perdió el proyecto de Supabase:** crear un proyecto nuevo y
  restaurar ahí. Después, cambiar `DATABASE_URL` en Render (servicio de Prod →
  *Environment*) por la cadena de conexión del proyecto nuevo.

Antes de restaurar sobre una base que todavía tiene datos, **descargar un
backup de cómo está ahora**, por si hay que volver atrás.

### 2. Correr backup.sql

**Opción A - psql (recomendada):** necesita el cliente de PostgreSQL
instalado (viene con el instalador de postgresql.org). La cadena de conexión
de Supabase está en *Project Settings → Database → Connection string*.

```bash
psql "postgresql://USUARIO:CONTRASEÑA@HOST:5432/postgres" -v ON_ERROR_STOP=1 -f backup.sql
```

**Opción B - SQL Editor de Supabase:** abrir `backup.sql`, copiar todo el
contenido, pegarlo en *SQL Editor → New query* y ejecutar. Sirve si el
archivo no es muy grande (unos pocos MB).

El script corre todo dentro de una transacción: si algo falla, no cambia
nada y la base queda como estaba.

### 3. Verificar

1. Comparar la cantidad de filas de algunas tablas con las que figuran en
   `LEEME.txt` (ej. `SELECT COUNT(*) FROM dml_fichas;`).
2. Entrar al sistema, abrir algunas fichas e ingresos y confirmar que están.
3. Crear algo de prueba (ej. un cliente) y confirmar que se guarda sin error.

## Detalles técnicos

- Lo genera `CODIGO_FUENTE/services/backup.py` desde Python, sin `pg_dump`
  (no está garantizado en Render y tiene que coincidir con la versión de
  Postgres de Supabase).
- La estructura se lee de la base real al momento del backup, no de
  `schema-postgres.sql` (que puede no coincidir con Supabase, ver #125).
- Copia todas las tablas del esquema `public`, que es donde vive todo el
  sistema. No incluye vistas ni funciones (el sistema no usa ninguna) ni
  otras partes de Supabase (Auth, Storage) que la app no usa.
- Pendiente (segundo PR del #52): envío automático del backup por mail.
