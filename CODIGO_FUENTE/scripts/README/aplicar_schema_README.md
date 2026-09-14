# `aplicar_schema.py` — sincronizar Supabase con `db/schema-postgres.sql`

## Qué es y para qué sirve

Lee `db/schema-postgres.sql` (el archivo con el schema **declarado** — cómo
queremos que sea la base) y modifica Supabase para que quede exactamente
igual a eso: agrega lo que falte, corrige tipos que no coincidan, y borra lo
que sobre. Siempre te muestra la lista completa de cambios antes de tocar
nada y pide confirmación explícita.

## `db/schema-postgres.sql` ahora se edita a mano

**Cambio importante respecto a la versión inicial de este README:**
`sync_schema.py` (el script que leía Supabase y sobreescribía este archivo)
quedó deprecado — generaba un archivo con `DROP TABLE` al principio, lo cual
es peligroso, y su formato de salida era además el único que el parser de
`aplicar_schema.py` entendía. Eso ya no aplica.

`db/schema-postgres.sql` es ahora la fuente de verdad **editada a mano**,
directamente en el repo, en el estilo prolijo estándar de Postgres:
constraints (`PRIMARY KEY`, `UNIQUE`, `FOREIGN KEY`) declarados **inline**
dentro de cada `CREATE TABLE`, sin `DROP TABLE` al principio. El parser de
`aplicar_schema.py` se actualizó para leer ese formato directamente (ver
sección "Qué entiende el parser" más abajo).

Si en algún momento aparece un `sync_schema.py` corriendo de nuevo o alguien
propone reintroducirlo: no. El flujo es unidireccional, `.sql` → Supabase.

## Requisitos

- `DATABASE_URL` seteada (mismo `.env` que ya usan `cargar_historico.py` y
  el resto de los scripts de `scripts/`).
- `psycopg2-binary` y `python-dotenv` instalados (ya están en el proyecto).

## Uso

```bash
python scripts/aplicar_schema.py
```

Conecta a la base que indique `DATABASE_URL` en ese momento — **el script
no valida que sea Dev**, esa responsabilidad sigue siendo del que lo
corre. Apuntar siempre a Dev primero.

El flujo es siempre el mismo:

1. Parsea `db/schema-postgres.sql`.
2. Consulta el estado real en Supabase (`information_schema`, `pg_enum`).
3. Calcula la diferencia y te la muestra completa, agrupada por categoría,
   con el SQL exacto que se va a correr.
4. Pide confirmación escrita (`si`) antes de aplicar nada. Cualquier otra
   respuesta cancela sin tocar la base.
5. Si confirmás, aplica los cambios en orden y comittea cada uno por
   separado (si uno falla, se frena ahí — lo anterior ya aplicado queda).

## Qué detecta y aplica

- **Tipos ENUM nuevos** → `CREATE TYPE ... AS ENUM`.
- **Valores nuevos dentro de un ENUM existente** → `ALTER TYPE ... ADD VALUE`.
- **Tablas nuevas** → `CREATE TABLE IF NOT EXISTS`.
- **Columnas nuevas** → `ALTER TABLE ... ADD COLUMN`.
- **Tipo de columna que no coincide** → `ALTER TABLE ... ALTER COLUMN ...
  TYPE ... USING`.
- **Foreign keys nuevas** → `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`
  (sin `IF NOT EXISTS` en el SQL que efectivamente se ejecuta — esa cláusula
  no existe en Postgres para constraints, así que el script arma el `ADD
  CONSTRAINT` liso y solo lo corre si el diff dice que hace falta).
- **Columnas/tablas que están en Supabase pero no en el archivo** →
  `DROP COLUMN` / `DROP TABLE CASCADE`. Se marcan explícitamente como
  `⚠️ DESTRUCTIVO` en la lista, pero pasan por la **misma** confirmación
  que todo lo demás — no hay un modo que las salte.

## Qué NO hace (a propósito)

- **No corre en el deploy automático.** Es una herramienta de uso manual,
  para correr a mano con alguien mirando la pantalla y confirmando. El
  mecanismo que corre solo en cada deploy (hoy `migrate_db()`) sigue
  siendo additive-only — eso se analiza aparte, no lo reemplaza este
  script todavía (ver "Próximos pasos" más abajo).
- **No previene fallos de conversión de tipo.** Si el `.sql` declara un
  tipo más chico que lo que ya hay cargado (ej. `TEXT` largo →
  `VARCHAR(50)`), Postgres va a tirar el error en el momento de aplicar,
  no antes. El script no valida los datos existentes de antemano.
- **No tiene flag para saltear la confirmación.** Es intencional: no hay
  forma de correrlo "silencioso" ni en modo no interactivo.

## Salvedad importante: columnas SERIAL

`SERIAL`/`BIGSERIAL` no son tipos reales de Postgres — son un atajo que,
al crear la columna, queda guardado como `INTEGER`/`BIGINT` con un
default `nextval(...)`. El script ya sabe reconocer ese patrón y no lo
marca como "tipo distinto" cuando el archivo dice `SERIAL` y la base
tiene `INTEGER` + `nextval()` (son la misma cosa). Si alguna vez ves un
cambio de tipo propuesto que involucre `SERIAL`/`BIGSERIAL` en una
columna que ya existía, sospechá antes de confirmar.

## Qué entiende el parser

El parser sigue siendo simple (regex), no un parser SQL genérico — pero ya
no está atado al formato exacto de un único generador. Reconoce:

- `CREATE TABLE nombre (...)` y `CREATE TABLE IF NOT EXISTS nombre (...)`
  indistintamente.
- `PRIMARY KEY` y `UNIQUE` tanto **inline** en la definición de una columna
  (`id SERIAL PRIMARY KEY`, `email TEXT NOT NULL UNIQUE`) como en línea
  separada al final del cuerpo (`PRIMARY KEY (id)`, `UNIQUE (email)`).
- `FOREIGN KEY (col) REFERENCES tabla (col_ref) [ON DELETE regla]` tanto
  **inline** dentro del `CREATE TABLE` como suelto después, en
  `ALTER TABLE tabla ADD CONSTRAINT [IF NOT EXISTS] nombre FOREIGN KEY
  (...) REFERENCES ...` — el `IF NOT EXISTS` ahí es opcional para el
  parser (nunca se genera en el SQL que el script ejecuta, porque esa
  sintaxis no existe en Postgres).

Ambos estilos (inline y separado) pueden convivir en el mismo archivo sin
problema. Aun así, seguimos con una única convención en el repo — hoy,
todo inline — para no tener el archivo con estilos mezclados sin motivo.

Si alguna vez se necesita soportar una construcción SQL que el parser no
reconoce todavía (`CHECK` con expresión compleja, `GENERATED ALWAYS AS`,
etc.), hay que extenderlo a mano — no asumir que "debería andar" sin
probarlo primero contra el `.sql` real.

## Flujo de prueba recomendado antes de confiar en él

1. Correrlo contra Dev tal cual está hoy → esperás "✅ ya coincide, nada
   que hacer".
2. Agregar una columna en el `.sql` a mano → correrlo → debería proponer
   el `ADD COLUMN` correspondiente, y aplicarlo al confirmar.
3. Sacar esa columna del `.sql` → correrlo → debería proponer el `DROP
   COLUMN`, marcado como destructivo, y aplicarlo solo al confirmar.
4. Si se edita el parser (como en esta versión), antes de tocar Supabase
   conviene validar solo el parseo: cargar `parse_schema_file()` sobre el
   `.sql` real y revisar a mano que la cantidad de tablas, FKs y primary
   keys detectadas tenga sentido, sin llegar a conectar a ninguna base.

## Próximos pasos (pendiente, no resuelto acá)

Sigue habiendo dos mecanismos de schema en el repo que no están unificados:
este script (manual, con confirmación) y `migrate_db()` en
`extensions.py` (automático en cada deploy, additive-only). Unificarlos o
documentar claramente cuándo usar cada uno queda pendiente.