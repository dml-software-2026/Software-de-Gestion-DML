# Cómo modificar el schema de la base (léeme antes de tocar tablas)

## Regla de oro

**Nunca se edita `db/schema-postgres.sql` a mano.**
**Nunca se usa `db/schema-postgres.sql` para aplicar cambios sobre una base que ya tiene datos** (Dev o producción existentes), salvo la única excepción documentada al final de este archivo.

Todo cambio de schema sobre una base existente (agregar columna, agregar tabla, cambiar un default, etc.) se escribe en `migrate_db()`, dentro de `CODIGO_FUENTE/extensions.py`.

`db/schema-postgres.sql` sí tiene un uso legítimo: levantar una base **nueva, vacía, desde cero** (un Dev nuevo, un entorno de testing). Para eso sirve tener todos los `CREATE TABLE IF NOT EXISTS` juntos en un solo archivo — no hay riesgo de pérdida de datos porque no hay datos todavía. Lo que nunca se hace es correrlo contra una base que ya está en uso.

## Por qué

`migrate_db()` corre solo, automáticamente, en cada deploy de la app (se ve en los logs de Render como líneas `[MIGRATION]`). Es idempotente: antes de aplicar cualquier cambio, chequea `information_schema` para ver si ya existe. Y por diseño **nunca dropea nada** — solo `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`. Esa es la garantía de que nadie pierde datos por accidente en un deploy.

`db/schema-postgres.sql` es un archivo **generado**, no una fuente de verdad. Documenta cómo quedó la base después del hecho, para que el equipo la pueda mirar sin entrar a Supabase. Se regenera solo, nunca se escribe a mano.

## Flujo para agregar una columna o tabla nueva

1. Editar `migrate_db()` en `extensions.py`, agregando un bloque `try/except` nuevo con el patrón que ya usa el resto del archivo:

   ```python
   try:
       col_names = _columnas_de(db, "nombre_tabla")

       if "columna_nueva" not in col_names:
           db.execute("ALTER TABLE nombre_tabla ADD COLUMN IF NOT EXISTS columna_nueva TEXT")
           print("[MIGRATION] ✅ Columna columna_nueva agregada a nombre_tabla")

       db.commit()
   except Exception as e:
       print(f"[MIGRATION] ⚠️  Error agregando columna_nueva: {e}")
       db.rollback()
   ```

2. Probar primero contra **Dev**, nunca directo contra producción.
3. Deployar (o correr la app localmente apuntando a Dev) y confirmar en los logs el mensaje `[MIGRATION] ✅ ...`.
4. Correr `python scripts/sync_schema.py` para regenerar `db/schema-postgres.sql`.
5. Revisar el diff en git — confirma que el cambio se ve reflejado y que no hay nada raro (tipo de columna mal mapeado, etc.).
6. Commitear `extensions.py` + `schema-postgres.sql` juntos.

## Excepción: borrar una columna o tabla

`migrate_db()` no tiene forma de sacar cosas — es intencional, para que nunca corra un DROP solo en un deploy. Por eso borrar es la **única** operación manual permitida, y siempre puntual y consciente:

1. Entrar al SQL Editor de Supabase, **en Dev**, una sola vez.
2. Ejecutar el `DROP COLUMN` / `DROP TABLE` a mano.
3. **Sacar de `migrate_db()` el bloque que agregaba esa columna/tabla.** Si no se saca, queda un `ADD COLUMN IF NOT EXISTS` zombie: el día que se corra `migrate_db()` contra una base nueva o recién creada, lo va a volver a agregar solo, sin que nadie lo pida.
4. Correr `python scripts/sync_schema.py` de nuevo para que `schema-postgres.sql` refleje que ya no existe.
5. Revisar el diff en git (tanto en `extensions.py` como en `schema-postgres.sql`) y commitear todo junto.
6. Nunca hacer esto directo contra producción.

## Resumen visual

| Acción | Cómo se hace | Dónde |
|---|---|---|
| Agregar columna / tabla | Bloque nuevo en `migrate_db()` | Se aplica solo en el próximo deploy |
| Borrar columna / tabla | `DROP` manual, una vez | SQL Editor de Supabase, **solo en Dev** |
| Ver el estado real del schema | `python scripts/sync_schema.py` | Regenera `db/schema-postgres.sql` |
| Editar `schema-postgres.sql` a mano | ❌ Nunca | — |
| Correr `schema-postgres.sql` contra una base con datos (Dev/prod existentes) | ❌ Nunca | — |
| Correr `schema-postgres.sql` para levantar una base nueva y vacía | ✅ Válido | Entorno nuevo, sin datos |