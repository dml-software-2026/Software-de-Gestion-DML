# Setup de CI mínimo — GitHub Actions

**Autor:** Matias Coca (mentor)
**Fecha:** 2026-08-10
**Estado:** listo para implementar
**Tiempo estimado:** 45-60 minutos

---

## ¿Qué es CI y por qué lo necesitan ahora?

**CI (Continuous Integration)** = chequeos automáticos que corren cada vez que abren un PR o pushean a `dev`/`main`. Si algún chequeo falla → GitHub bloquea el merge.

**Por qué es especialmente importante ahora que usan Claude Code:**

La **Política de uso de IA v2.0** del equipo (secciones 5-N3 y 11) exige que cada integrante entienda y evalúe críticamente lo que Claude genera antes de aceptarlo. Cuando eso se cumple, la mayoría de bugs se atrapan leyendo el diff. Pero es una defensa humana, y los humanos se cansan. CI es la **segunda capa** de seguridad, automática y sin dependencia del estado de ánimo del reviewer.

Los errores típicos que CI atrapa cuando el review humano se le escapa algo:
- Importa un módulo que no existe (Claude alucinó el nombre)
- Llama un método con un typo
- Rompe un blueprint que ya andaba (Claude cambió una firma y no actualizó los llamadores)
- Deja variables no definidas después de un refactor

CI atrapa ~60-80% de estos en 2 minutos. Es complementario, no sustituto, del N3 de la política.

**Sin CI:** el bug llega a `dev`, David lo ve en la demo, nadie sabe cuándo se rompió → horas de debug.
**Con CI:** PR queda rojo, el autor lo arregla en 5 min, `dev` siempre está deployable.

---

## Estado actual del repo (transparencia antes de arrancar)

Corrí `ruff check CODIGO_FUENTE/` sobre `dev` y encontré **171 errores**. No se asusten — la mayoría es ruido conocido:

| Regla | Cantidad | Realidad |
|---|---|---|
| F821 (variable no definida) | 130 | **126 están en `pdf_generator_new.py`** (archivo muerto que el propio refactor #75 documentó como "no integrado"), 3 en `scripts/cargar_stock_nuevo.py`, 1 en `blueprints/api.py` (endpoint `verificar_stock_api` con docstring que dice literal "CÓDIGO ROTO EN EL ORIGINAL"). Todo esto es basura conocida. |
| F541 (f-string sin placeholder) | 22 | Cosmético, auto-fixable |
| E722 (`except:` sin tipo) | 11 | Mala práctica, arreglo manual rápido |
| F401 (import sin usar) | 4 | Auto-fixable |
| F841 (variable sin usar) | 4 | Auto-fixable |

**Real que queda para arreglar manualmente:** ~14 errores. Los otros se arreglan solos con `ruff check --fix` o excluyendo los archivos muertos.

Por eso el setup tiene un **Paso 0** de limpieza previa antes de activar CI. Sin ese paso, CI arrancaría rojo desde el minuto uno.

---

## Setup paso a paso

### Paso 0 — Limpieza previa (arreglar lo que sí es real)

Antes de agregar CI, corren esto en `dev` (o en una branch nueva) para aplicar los 27 fixes automáticos:

```bash
pip install ruff  # si no lo tienen
ruff check CODIGO_FUENTE/ --fix
```

Esto arregla los F541 + F401 + F841 automáticamente (27 cambios). Revisen el diff con `git diff` para ver que los cambios sean razonables (borra prefijos `f` innecesarios y borra imports no usados).

Los 11 errores E722 (`except:` sin tipo) los tienen que arreglar a mano. En cada caso reemplazar `except:` por `except Exception:` (o el tipo específico si saben qué excepción esperan).

**Commitear los fixes** con mensaje tipo `chore: aplicar ruff --fix + arreglar bare except`.

### Paso 1 — Crear config de ruff (`pyproject.toml`)

En la **raíz del repo** (al mismo nivel que `requirements.txt`, no dentro de `CODIGO_FUENTE/`), crear `pyproject.toml`:

```toml
# Config de ruff — linter usado en CI y localmente
# Docs: https://docs.astral.sh/ruff/configuration/

[tool.ruff]
# Qué carpetas revisar
target-version = "py311"
line-length = 120  # relajado vs default 88, la app tiene muchas queries largas

# Archivos y carpetas que ruff IGNORA completamente
exclude = [
    # Archivo muerto — reemplazado por services/pdf.py en el refactor #75.
    # Pendiente de borrar en issue #85 (unificar los 3 generadores de PDF).
    "CODIGO_FUENTE/pdf_generator_new.py",

    # Scripts auxiliares — no son código de producción. Se corren manualmente.
    # Cuando alguno se estabilice y quiera lint estricto, sacarlo de esta lista.
    "CODIGO_FUENTE/scripts/",
]

[tool.ruff.lint.per-file-ignores]
# Endpoint verificar_stock_api documentado como "CÓDIGO ROTO EN EL ORIGINAL"
# en su propio docstring — usa una variable `db` sin definir y consulta una tabla
# inexistente. Pendiente de eliminar o reescribir (relacionado con #62 y #86).
# Mientras tanto, silenciamos el warning para que CI no se caiga por esto.
"CODIGO_FUENTE/blueprints/api.py" = ["F821"]
```

**¿Por qué en la raíz y no dentro de CODIGO_FUENTE/?** `pyproject.toml` es un archivo estándar que herramientas como ruff, pytest y otras buscan desde la raíz del proyecto hacia arriba. Si lo dejamos en un subdirectorio no lo encuentran cuando corren desde la raíz.

### Paso 2 — Verificar que ruff pasa localmente

```bash
ruff check CODIGO_FUENTE/
```

Debería decir `All checks passed!` o algo cercano (a lo sumo los E722 si no los arreglaron). Si sigue rojo, revisar por qué antes de seguir.

### Paso 3 — Crear el workflow de GitHub Actions

Crear la carpeta y el archivo:

```bash
mkdir -p .github/workflows
```

**¿Por qué esa carpeta específica?** GitHub Actions solo mira archivos `.yml` dentro de `.github/workflows/`. Si el archivo va a otro lado, GitHub lo ignora silenciosamente.

Crear `.github/workflows/ci.yml` con este contenido:

```yaml
# CI mínimo del proyecto DML
# Corre en cada PR contra dev/main y en cada push a esas ramas.
# Objetivo: atrapar errores de sintaxis, imports rotos y app que no bootea
# ANTES de que lleguen a dev y rompan la demo con David.

name: CI

# Cuándo se dispara este workflow
on:
  pull_request:
    branches: [dev, main]   # PRs apuntando a dev o main
  push:
    branches: [dev, main]   # Y pushes directos (aunque la branch protection ya los bloquea)

jobs:
  # Un solo job llamado "check" — todo lo que valida corre acá adentro
  check:
    runs-on: ubuntu-latest   # GitHub nos da una VM Linux gratis por 2 min por run

    steps:
      # PASO 1 — bajar el código del repo a la VM
      - name: Checkout del código
        uses: actions/checkout@v4

      # PASO 2 — instalar Python
      # Usamos 3.11 fijo para matchear lo que corre en Render (ver runtime.txt).
      # Si algún día cambian de versión, actualizar acá TAMBIÉN.
      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'   # Cachea las dependencias entre runs, acelera 30-60 seg

      # PASO 3 — instalar libs de sistema que necesitan algunas deps de Python
      # reportlab (para generar PDFs) trae pycairo como dep transitiva, y pycairo
      # necesita libcairo2 + pkg-config compilados. Sin estas dos líneas, pip install falla.
      - name: Instalar dependencias de sistema (para pycairo/reportlab)
        run: sudo apt-get update && sudo apt-get install -y libcairo2-dev pkg-config

      # PASO 4 — instalar las deps del proyecto
      # Si requirements.txt está roto o falta algún paquete, esto falla acá.
      - name: Instalar dependencias Python
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install ruff   # linter — no lo agregamos a requirements.txt porque solo lo usa CI y devs

      # PASO 5 — lint con ruff
      # Usa la config de pyproject.toml automáticamente (exclusiones y line-length).
      - name: Lint con ruff
        run: ruff check CODIGO_FUENTE/

      # PASO 6 — verificar que la app importa sin errores
      # Este es el chequeo más valioso: si Claude alucinó un import o rompió
      # un blueprint, la app no arranca y este comando explota acá, no en producción.
      # Nota: se corre desde CODIGO_FUENTE/ porque los blueprints hacen imports relativos.
      - name: Import check — la app bootea?
        run: |
          cd CODIGO_FUENTE
          python -c "from app import app; print('OK: app importa correctamente')"
```

### Paso 4 — Crear `runtime.txt` (opcional pero recomendado)

Sin este archivo, Render usa una versión de Python "default" que puede cambiar sin aviso. Para garantizar que **la versión de Python en local, en CI y en Render sean la misma**, crear en la raíz:

```
python-3.11.9
```

(sí, el archivo se llama exactamente `runtime.txt`, tiene 1 línea, sin saltos ni comentarios). Render lee este archivo y usa exactamente esa versión.

### Paso 5 — Verificar sintaxis del YAML antes de commitear

Los archivos YAML son sensibles a indentación (usan 2 espacios, NO tabs). Un error de indentación y GitHub Actions ignora el workflow silenciosamente:

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

Si imprime nada = OK. Si tira error, revisar indentación.

### Paso 6 — Branch, commit y PR

```bash
git checkout -b chore/setup-ci
git add .github/workflows/ci.yml pyproject.toml runtime.txt
git commit -m "chore: agregar CI mínimo (ruff + import check) + runtime.txt"
git push -u origin chore/setup-ci
```

Abrir PR en GitHub de `chore/setup-ci` → `dev`.

### Paso 7 — Ver el CI corriendo

Apenas abren el PR, GitHub muestra arriba:
- 🟡 "Some checks haven't completed yet" (mientras corre)
- ✅ "All checks have passed" (si todo OK)
- ❌ "Some checks failed" (si algo falló)

Click en "Details" al lado del check para ver el log completo. Los logs de GitHub Actions te dicen exactamente qué falló y en qué línea.

### Paso 8 — Marcar CI como *required check* (obligatorio)

**Este paso es el que hace que CI bloquee merges cuando falla.** Sin esto, CI es solo informativo — se puede mergear rojo.

1. Ir a **Settings → Rules → Rulesets** del repo.
2. Editar el ruleset que ya existe para `main` (creado en issue #67).
3. Activar **"Require status checks to pass"**.
4. En "Status checks required", agregar **`check`** (el nombre del job del YAML).
5. Guardar.
6. Repetir para el ruleset de `dev`.

**Importante:** GitHub solo permite agregar checks que ya corrieron al menos una vez. Por eso este paso va después del Paso 7.

### Paso 9 — Mergear el PR

Con CI verde y required checks configurados, mergear `chore/setup-ci` → `dev`. Desde ese momento, CI corre en todos los PRs futuros. Cuando cierren el próximo release (E2), mergear `dev` → `main` con CI activo también ahí.

---

## Cómo leer un CI que falla

Cuando abren un PR y CI queda rojo:

1. Click en **"Details"** al lado del check rojo.
2. GitHub muestra el log completo del run.
3. Buscar la línea que dice **`Error:`** o `❌`.
4. El error dice qué paso falló y por qué.

**Errores comunes y cómo interpretarlos:**

| Error | Qué pasó | Cómo arreglarlo |
|---|---|---|
| `ModuleNotFoundError: No module named 'xyz'` | Import de un módulo que no existe. Claude probablemente inventó el nombre. | Borrar el import o agregarlo a `requirements.txt` |
| `SyntaxError: invalid syntax` | Error de sintaxis Python | Ir a la línea que indica y arreglar |
| `ruff: F401 'xxx' imported but unused` | Import que se dejó pero no se usa | Borrar el import (o correr `ruff check --fix`) |
| `ruff: F821 undefined name 'xxx'` | Se usa una variable/función que no está definida | Verificar el nombre (¿typo?) o agregar el import |
| `pip install` falla | requirements.txt roto o paquete inexistente | Verificar que el paquete y versión existan en PyPI |

**Regla de oro:** si CI falla, NO mergear "a la fuerza". Arreglar el error primero. El CI está para protegerlos.

---

## Cuándo saltarse el CI

**En principio nunca.** Pero si por alguna razón excepcional hay que mergear con CI rojo (ej: falla del propio CI, no del código):

- Un admin del repo puede desactivar temporalmente el required check
- Documentar en el PR **por qué** se saltó y volver a activarlo inmediatamente después
- **Nunca hacerlo por presión de tiempo** — es la puerta de entrada de bugs a producción

---

## Paso siguiente (más adelante) — agregar pytest cuando escriban tests reales

Los "tests" actuales (`smoke_test.py`, `test_email.py`, `test_login.py`) son scripts que requieren BD y SMTP conectados. No corren en CI así como están.

Cuando quieran empezar a tener **unit tests reales** — recomendado, especialmente con Claude Code (Claude puede escribir la primera versión de cada test en 30 segundos):

1. Agregar a `requirements.txt`:
   ```
   pytest==8.0.0
   pytest-flask==1.3.0
   ```

2. Crear carpeta `CODIGO_FUENTE/tests/` con archivos `test_*.py` estilo pytest.

3. Agregar un paso más al `ci.yml` al final del job `check`:
   ```yaml
   - name: Correr pytest
     run: |
       cd CODIGO_FUENTE
       pytest tests/ -v
   ```

**Tip:** Claude Code es muy bueno escribiendo tests. Pídanle *"escribí tests unitarios para el blueprint auth.py cubriendo login exitoso, login fallido y logout"* — arma el archivo listo para correr.

---

## Preguntas frecuentes

**¿Cuánto tarda cada corrida?**
~2 minutos la primera vez, ~1 min con cache de pip.

**¿Cuánto cuesta?**
Gratis. GitHub Actions da 2.000 minutos gratis por mes (ilimitado si el repo es público). El proyecto va a usar ~50 minutos por mes.

**¿Si CI está rojo puedo seguir trabajando?**
Sí. Podés hacer más commits al mismo branch, cada uno vuelve a disparar el CI. Solo no podés *mergear* hasta que quede verde.

**¿Y si el error no es culpa mía, es una falla de la infraestructura de GitHub?**
Raro pero pasa (~1 vez cada varios meses). Se identifica por errores tipo "network timeout" o "runner unavailable". En ese caso: botón "Re-run failed jobs" en la UI del PR.

---

## Checklist final

Antes de dar por hecho el setup:

- [ ] Paso 0: `ruff check --fix` corrido y E722 arreglados a mano, commiteado
- [ ] Paso 1: `pyproject.toml` en la raíz del repo
- [ ] Paso 2: `ruff check CODIGO_FUENTE/` pasa localmente sin errores
- [ ] Paso 3: `.github/workflows/ci.yml` creado
- [ ] Paso 4: `runtime.txt` creado con `python-3.11.9`
- [ ] Paso 5: YAML valida
- [ ] Paso 6: PR abierto
- [ ] Paso 7: CI verde en el PR
- [ ] Paso 8: `check` marcado como required para `dev` y `main`
- [ ] Paso 9: PR mergeado
- [ ] Bonus: el próximo PR que abran ven el CI corriendo automáticamente
