# Flujo de branches y ritual de release

**Autor:** Matias Coca (mentor)
**Fecha:** 2026-08-10
**Estado:** decisión tomada — 2 branches (dev + main)
**Aplica desde:** sprint E2 (2026-08-10)

---

## Decisión

Vamos con **2 branches long-lived**: `dev` y `main`. Feature branches cortas nacen y mueren desde `dev`.

Discutimos también la opción de **3 branches** (`dev` + `testing` + `main`), donde `testing` sería un ambiente estable donde David prueba sin ver los WIP que los devs mergean a `dev`. Es la práctica más "de libro", pero para nuestro contexto tiene más costo que beneficio. Este doc explica por qué elegimos 2, y qué reglas hacen que 2 funcionen bien.

---

## Las dos opciones evaluadas

### Opción A: 2 branches (dev + main) — LA QUE ELEGIMOS

```
feature/*   ──►  dev            (integración continua; deploy auto a raypac-dev en Render)
                  │
                  └─►  main     (release estable; deploy auto a raypac-prod en Render)
```

- 2 environments de Render (`raypac-dev`, `raypac-prod`)
- 2 CNAMEs configurados por David (`raypac-dev.dmlelectricidadind.com.ar`, `raypac-prod.dmlelectricidadind.com.ar`)
- David prueba entregas mensuales en `raypac-dev` cuando el equipo le avisa que está listo

### Opción B: 3 branches (dev + testing + main) — DESCARTADA

```
feature/*   ──►  dev            (dev del equipo; puede estar roto)
                  │
                  └─►  testing  (staging para David; siempre estable)
                        │
                        └─►  main  (producción firmada por David)
```

- 3 environments de Render
- 3 CNAMEs
- Cliente prueba en un env intermedio siempre estable
- Devs pueden mergear a `dev` sin cuidar la demo

---

## Por qué 2 y no 3

**Ventajas de la opción B (3 branches) que perdemos con 2:**
- El cliente nunca ve `dev` con algo roto porque prueba en `testing`
- Los devs pueden experimentar libre en `dev` sin miedo a romper la demo
- Separación más clara de responsabilidades por ambiente

**Costos de la opción B que evitamos con 2:**
- **Overhead de PRs:** cada cambio pasa `feature → dev → testing → main`, tres merges por feature. Con 3 devs y 6 hs/semana, ese overhead se come tiempo de codificación.
- **Complejidad cognitiva:** 3 branches long-lived requiere disciplina de saber en cuál estás siempre, sincronizar cambios de main a dev cuando hay hotfixes, resolver conflictos entre las 3. Es GitFlow completo, pensado para equipos senior con ciclos de release largos y complejos. Para 3 estudiantes con entregas mensuales, es sobredimensionado.
- **Un environment más:** Render permite 25 servicios gratuitos, no es problema técnico. Pero cada env es una URL más que configurar, monitorear y explicar a David.
- **Aprendizaje pedagógico:** los principios de branching se aprenden igual con 2 que con 3. Sumar el tercero cuando aún no dominan los rituales básicos multiplica el chance de que se confundan y no lo respeten.

**La regla de decisión general:** la complejidad de proceso debe ser proporcional al tamaño del equipo y la frecuencia de release. 3 devs entregando cada 3 semanas = 2 branches. Un equipo de 20 devs entregando cada 24h = 3+ branches.

---

## Cómo hacer que 2 branches funcione bien

La opción B (3 branches) es más segura "por diseño": el cliente está aislado de lo que hacen los devs. Con 2 branches el cliente prueba directamente donde los devs trabajan, así que **la seguridad depende de reglas de proceso**, no de estructura. Estas son las tres que hacen la diferencia:

### Regla 1 — `dev` siempre debe estar deployable

- Ningún merge a `dev` sin PR + review de otro integrante + CI verde (ver `MENTORIA/ci-setup.md`)
- El autor del PR probó localmente que la app arranca y el flujo afectado anda
- Feature branches cortas (1-3 días máximo) — nada de vivir semanas en un branch propio

**Traducido:** aunque David pudiera entrar a `raypac-dev` cualquier día del sprint, el sistema debería arrancar y hacer al menos las cosas que hacía la semana pasada.

### Regla 2 — Freeze de `dev` desde el aviso de demo hasta el feedback de David

Los momentos donde `dev` NO puede estar roto son:
- Las 24h antes de cualquier demo con David
- Todo el período que David está probando (típicamente 3-5 días después de la demo)
- Hasta que David complete el formulario feedback y digamos "listo, seguimos"

Durante ese freeze:
- No se mergea a `dev` nada nuevo
- Solo se aceptan hotfixes de bugs que David reportó
- Los devs siguen trabajando en sus feature branches, pero acumulan mergeos

Es una regla simple pero requiere disciplina. En cada sprint doc está marcado cuándo empieza y termina el freeze.

### Regla 3 — Ritual de release al cierre de cada entregable

`main` se actualiza **solo** en momentos definidos, no continuamente. Cada release a `main` es un evento:

1. David completa el formulario feedback de la entrega
2. Si hay bugs bloqueantes reportados: se arreglan en `dev` primero, David reprueba
3. Cuando David dice "OK" (por WhatsApp, mail, o en el formulario): un release manager designado hace:
   - PR de `dev` → `main`
   - Tag de release con nombre semántico: `v2.0-E2`, `v2.0-E3`, etc.
   - Merge del PR (o "Squash and merge" para dejar main limpio)
   - Verificación de que Render `raypac-prod` deployó bien (~5 min post-merge)
4. Se anuncia en la daily del día siguiente: "main actualizado a v2.0-E2"

**Sin este ritual, `main` queda desactualizado por semanas** (fue lo que pasó entre 2026-07-06 y 2026-08-05 — un mes de trabajo en `dev` y `main` intacto). Cada release-to-main que se atrasa aumenta el gap entre lo que ve el cliente y lo que existe en producción.

---

## Quién es el release manager

Para este sprint (E2, cierra 2026-08-29): **Seba**. Rota cada sprint. Al arrancar cada sprint, en el doc del sprint queda anotado quién le toca.

Responsabilidades del release manager:
- Coordina el freeze de `dev` (avisa al resto en la daily y por WhatsApp)
- Hace el PR de `dev` → `main` cuando David firma
- Crea el tag de release
- Verifica el deploy de producción
- Notifica en la próxima daily

Es un rol de 30-60 min por sprint. Bajo, pero indispensable.

---

## Feature branches — reglas simples

Al empezar cualquier tarea que modifique código, crear una branch nueva desde `dev`:

```bash
git checkout dev
git pull            # traer los últimos cambios
git checkout -b feat/54-ingreso-raypac    # nombre descriptivo con # de issue
```

Prefijos usados en el proyecto (mantener consistencia):
- `feat/` — nueva funcionalidad
- `fix/` — bug fix
- `refactor/` — cambio interno sin afectar comportamiento
- `chore/` — mantenimiento (deps, config, docs)
- `docs/` — documentación
- `hotfix/` — fix urgente que sale de `main` (excepción, ver abajo)

**Nombre de la branch:** prefijo/número-de-issue-y-descripción-corta. Ejemplos reales del repo:
- `feat/54-ingreso-raypac`
- `fix/remove-hardcoded-credentials`
- `chore/setup-ci`

**Duración:** máximo 1-3 días. Si la tarea es más grande, cortar en sub-tareas y varios PRs chicos.

---

## Hotfixes — la excepción al flujo

Si sale un bug crítico en `main` (David reporta "no puedo loguearme" en pleno horario laboral):

```bash
git checkout main
git checkout -b hotfix/descripcion-corta
# arreglar
# PR a main, review, merge
git checkout dev
git merge main    # traer el fix también a dev para no perderlo
git push
```

- Hotfix va directo de `main` a `main` para saltear la cola de features en `dev`
- Después el fix se propaga de vuelta a `dev` (importante — si no, la próxima release desde `dev` reintroduce el bug)
- Documentar en el PR por qué fue hotfix, no está bueno abusar de este flujo

---

## Local development

**Nunca desarrollar directo sobre `main` ni sobre `dev`.** Siempre en una feature branch propia.

**Configurar el local para que apunte a Supabase-dev, no a una BD local:**
- Cada dev crea su `.env` local (nunca commiteado) con `DATABASE_URL=<connection string de Supabase-dev>`
- Al probar cambios, están usando la BD real de dev — lo mismo que va a ver David en `raypac-dev`
- No hay SQLite local escondido que oculte bugs de Postgres

`.env.example` en el repo tiene la plantilla con los nombres de variables. Las credenciales reales de Supabase-dev las tiene Seba, pasalas por canal privado (no por WhatsApp del grupo del proyecto).

---

## Preguntas frecuentes

**Si estamos con Regla 1 estricta, ¿por qué existiría alguna vez el freeze de Regla 2?**
Regla 1 garantiza que la app *arranca* y *funciona en general*. Regla 2 garantiza que *nada cambió* mientras el cliente prueba — que no le aparezca una feature nueva a mitad de sesión que no esperaba, o un campo que se movió de lugar. Son garantías distintas.

**¿Qué pasa si necesitamos experimentar con algo que puede romper la app?**
Feature branch propia (siempre lo es). Nunca se mergea a `dev` sin haber verificado localmente. Si el experimento no funciona: se descarta la branch, no se mergea. `git checkout dev && git branch -D nombre-branch`.

**¿Y si David quiere probar algo específico que todavía no está mergeado?**
Excepción manejada por el release manager: se puede deployar temporalmente una branch a `raypac-dev` (Render lo permite). Pero es raro — normalmente conviene primero terminar el feature, mergear, y que pruebe eso.

**¿Cuándo mergeamos de `dev` a `main`?**
Al cierre de cada entregable (E2, E3, etc.), después que David firma. Ver "Ritual de release" arriba. Fuera de esos momentos: no.

**¿Puedo mergear un fix de docs directo a `main`?**
No. Va a `dev` como cualquier PR, y llega a `main` en el próximo release. La única excepción es hotfix a bug crítico en producción.

---

## Checklist rápido antes de mergear un PR

Antes de apretar "Merge" en cualquier PR contra `dev`:

- [ ] CI verde
- [ ] Al menos 1 approval de otro integrante
- [ ] Probaste el flujo end-to-end en tu local (con Supabase-dev)
- [ ] Si tocaste un blueprint, probaste que las rutas afectadas siguen respondiendo
- [ ] Actualizaste el checkbox del issue en el kanban
- [ ] Si usaste Claude para escribir el código, registraste en el log de uso de IA (ver Política de uso de IA sec. 6)

Si algo de eso no está, no mergees. Los 5 minutos que ahorrás merging ahora se pagan en horas después.
