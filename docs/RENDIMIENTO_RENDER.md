# Rendimiento en Render - investigación (#244)

**Pregunta del issue:** la app está lenta en Render, ¿hace falta pagar un plan
o hay margen de mejora con lo que tenemos?

**Respuesta corta:** pagar un plan de Render **no arregla** la lentitud
principal. El problema es que **Render está en Oregon (EE.UU.) y la base de
Supabase en São Paulo (Brasil)**, y la app le hace muchas consultas a la base
por cada página. Cada consulta cruza esa distancia ida y vuelta. Se resuelve
juntando los dos servicios en la misma región y bajando la cantidad de
consultas - ninguna de las dos cosas cuesta plata.

Investigación hecha el 2026-10-26. Solo investigación: las mejoras quedan
para tareas aparte (ver "Qué hacer").

## Datos

| | Render (Dev y Prod) | Supabase |
|---|---|---|
| Región | Oregon (EE.UU. oeste) | São Paulo (`sa-east-1`) |

Distancia aproximada: 10.000 km. Una ida y vuelta de red entre los dos tarda
del orden de **0,17-0,19 s**.

## Mediciones

Tiempo hasta recibir la respuesta (TTFB), 5 pedidos seguidos a cada URL desde
Argentina (mediana):

| Pedido | ¿Toca la base? | Dev | Prod |
|---|---|---|---|
| `/static/style.css` | No | 0,33 s | 0,24 s |
| `/login` (sin sesión) | No | 0,24 s | 0,23 s |
| `/ticket/<inexistente>` (vista pública) | Sí, 1 consulta | 1,63 s | 2,30 s |

- Lo que **no** toca la base responde en ~0,24 s: Render en sí anda rápido.
- **Una sola consulta a la base suma ~1,4-2 s**: abrir la conexión a
  Supabase (la app abre una nueva en cada request: conexión + cifrado +
  login a Postgres, varias idas y vueltas) más la consulta.
- El primer pedido a Dev tardó **18 s**: el servidor estaba dormido (ver
  "Arranque en frío").

### Consultas por página (medido en local)

| Pantalla | Consultas | De esas, "buscar el usuario logueado" |
|---|---|---|
| Inicio | 12 | 12 |
| `/raypac`, `/dml`, `/stock` | 14 | 13 |
| `/envios` | 21 | 15 |
| Ficha `/dml/<id>` | 18 | 13 |

**Estimación** con esos números: una pantalla con ~14 consultas en Render
tarda alrededor de **0,24 + 1,2 (conexión) + 14 × 0,18 ≈ 4 segundos**. En
local la misma pantalla tarda 0,05 s.

## Causas encontradas (de mayor a menor impacto)

1. **Render y Supabase en continentes distintos.** Multiplica el costo de
   cada consulta. Es la causa principal.
2. **El usuario logueado se busca 12-15 veces por página.** `base.html` llama
   a `get_current_user()` 7 veces, más los decoradores y la vista - y cada
   llamada es una consulta nueva. Con guardarlo una vez por request
   (`flask.g`) bajaría a 1.
3. **Una conexión nueva a la base en cada request** (`get_db()` en
   `extensions.py`). Con un pool de conexiones (`psycopg2.pool`) se reusa la
   conexión y se ahorra ~1 s por página.
4. **Migraciones y seed en el primer request después de cada arranque.**
   `apply_migrations()` (`app.py`) corre ~63 consultas (entre ellas 39 INSERT
   de la lista de clientes) en el primer pedido de cada arranque o deploy -
   en Render, más de 10 s. Además, como Render no tiene el archivo `dml.db`,
   `config.py` cree que la base es nueva y corre `init_db()` completo cada vez.
5. **Logo de 496 KB.** `INTERFAZ/static/logo.png` es de 1513×864 px y se
   muestra a 30 px de alto; se manda con `Cache-Control: no-cache`, así que el
   navegador lo vuelve a consultar en cada página. Reducido a ~120 px de alto
   pesaría unos pocos KB.
6. **Un solo proceso de servidor.** El `Procfile` levanta gunicorn sin
   `--workers`/`--threads`: si dos personas piden una página a la vez, una
   espera a que termine la otra (y cada página espera a la base varios
   segundos).

### Arranque en frío

El plan gratis de Render duerme el servidor después de 15 min sin tráfico
(Starter y superiores no). El primer pedido después de dormir tarda
~15-30 s: despertar + la causa 4. UptimeRobot evita que se duerma si está
apuntando a esa URL - en Dev no lo estaba (18 s medidos), Prod respondió
normal. Revisar en UptimeRobot que esté configurado para las dos URLs.

## ¿Conviene pagar Render?

Precios de compute de Render a la fecha (por servicio, por mes):

| Plan | RAM / CPU | Precio | Qué cambia para nosotros |
|---|---|---|---|
| Free | 512 MB / 0,1 CPU | US$ 0 | Se duerme a los 15 min |
| Starter | 512 MB / 0,5 CPU | US$ 7 | No se duerme, 5x más CPU |
| Standard | 2 GB / 1 CPU | US$ 25 | Más memoria (no la necesitamos) |

- **Starter** saca el arranque en frío y da más CPU, pero **no toca el viaje
  Oregon ↔ São Paulo**: las páginas logueadas seguirían tardando segundos.
- **Standard o más:** no aporta nada para el tamaño de la app.

**Conclusión: no pagar todavía.** Primero aplicar las mejoras de abajo (gratis)
y volver a medir. Si después de eso molesta el arranque en frío y UptimeRobot
no alcanza, Starter (US$ 7/mes) es la única que tiene sentido.

## Qué hacer (propuesta de tareas, en orden)

1. **Juntar Render y Supabase en la misma región** - el cambio de mayor
   impacto. Render no tiene región en Sudamérica y Supabase no tiene Oregon;
   las regiones en común más cercanas a Argentina son **Virginia** (Render) +
   **North Virginia `us-east-1`** (Supabase). Ninguno de los dos permite
   cambiar la región de un servicio existente: hay que crear el proyecto de
   Supabase nuevo, pasar los datos (el backup del #52 sirve para eso,
   ver `docs/BACKUPS.md`), crear el servicio de Render en Virginia y apuntar el
   dominio. Con los dos en el mismo lugar, cada consulta pasa de ~0,18 s a
   ~0,001 s. Coordinarlo con todo el equipo (y con David si hay que avisar un
   corte).
2. **Guardar el usuario logueado una vez por request** (`get_current_user()`
   con `flask.g`). Cambio chico: de 12-15 consultas por página a 1.
3. **Pool de conexiones a la base** en `get_db()`.
4. **Migraciones al arrancar, no en el primer request**, y que no corra
   `init_db()`/seed completo cada vez (arreglar el chequeo de `dml.db`).
5. **Achicar el logo** y darle cache a los archivos estáticos.
6. **Más workers/threads en gunicorn** (ej. `--workers 2 --threads 4`;
   revisar la memoria en el plan gratis).

Las 2-6 se pueden hacer sin tocar la infraestructura y ya mejoran bastante
aunque no se haga la 1.

## Otro hallazgo

En **Prod**, `/ticket/<número que no existe>` devuelve **error 500**; en Dev
redirige bien. Prod tiene código más viejo que Dev - se arregla solo con el
próximo pase de `dev` a `main`.

## Fuentes

- Regiones de Render: https://render.com/docs/regions
- Regiones de Supabase y cambio de región: https://supabase.com/docs/guides/platform/regions ,
  https://supabase.com/docs/guides/troubleshooting/change-project-region-eWJo5Z
- Precios de Render: https://www.srvrlss.io/provider/render/ ,
  https://temps.sh/blog/render-pricing-2026
