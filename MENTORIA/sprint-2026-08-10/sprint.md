# Sprint 2026-08-10 → 2026-08-29 (E2)

**Entregable:** Módulo RAYPAC — ingreso y gestión de máquinas · **Demo a David:** viernes 29/08
**Docs relacionados:** `./descripciones-issues.md` (guías paso a paso) · `../ci-setup.md` · `../flujo-branches.md`

---

## Modo de trabajo (cambio desde este sprint)

Matías escribe el plan de cada sprint con las tareas priorizadas y el "por qué". Ustedes ejecutan y hacen el seguimiento diario. En E4 rotamos: ustedes proponen el plan y Matías revisa. Ejecución técnica, kanban, bitácora y comunicación con David siguen siendo suyos.

---

## Objetivos del sprint

**Cara al cliente:**
- [ ] David puede crear un ingreso RAYPAC completo, freezarlo y verlo del lado DML
- [ ] David completa el formulario de feedback

**Internos:**
- [ ] `main` sincronizado con `dev` (arranca el sprint alineado)
- [ ] `main` incluye Postgres Fase 2 al cierre del sprint
- [ ] CI activo bloqueando merges rotos
- [ ] Endpoints de admin protegidos con auth
- [ ] `SCOPE_v3.0.md` consolidado (resuelve las 8 contradicciones entre docs julio — ver Anexo A)
- [ ] Todos los issues del board con descripciones claras
- [ ] Board limpio (epics falsos cerrados, duplicados cerrados)

---

## Tareas por integrante

### 🟦 Facu — ~20h

| Prio | # | Tarea | Estimado |
|---|---|---|---|
| 1 | #62 | Terminar `endpoints sin auth` (2 checkpoints restantes) | 4h |
| 2 | #54 | **Core E2:** corregir ingreso RAYPAC (8 sub-items) | 16h |

Trabajar en `feature/54-ingreso-raypac` desde `dev`. PRs chicos, no uno gigante. Guías en `descripciones-issues.md`.

### 🟧 Ivo — ~24-25h

| Prio | # | Tarea | Estimado |
|---|---|---|---|
| 1 | #46 | Pedir review y mergear (trabajo terminado) | 1h |
| 2 | — | Cleanup del board (cerrar #22/#23/#24/#26 epics + #51 + #56) | 30-60m |
| 3 | — | **Actualizar descripciones de los 17 issues no-Done en GitHub** (copy-paste desde `descripciones-issues.md`) | 1h |
| 4 | #59 | Alertas mail stock bajo | 4h |
| 5 | — | Formulario feedback + mensaje WhatsApp para David | 2h |
| 6 | — | Consolidar docs julio → `SCOPE_v3.0.md` (ver Anexo A) | 5-6h |
| 7 | #85 | Unificar los 3 generadores de PDF — avanzar lo que se pueda, si no queda se completa en E3 | 8h |

### 🟩 Seba — ~14-16h

| Prio | # | Tarea | Estimado |
|---|---|---|---|
| 1 | #95 | Cerrar Postgres Fase 2 (mergear PR a `dev`) | 2h |
| 2 | — | **Sync inicial `dev` → `main`** con todo lo acumulado (10 commits: postgres F1+F2, refactor, credentials, .exe borrado). Tag `v1.9-preE2`. Cierra el gap antes de arrancar E2. | 1h |
| 3 | — | Setup CI (seguir `../ci-setup.md`, 9 pasos) — queda activo para todos los PRs futuros | 5-6h |
| 4 | #76 | Adecuar script de carga histórico (ver spec en `descripciones-issues.md` — es script Python reejecutable con `INSERT ON CONFLICT DO NOTHING`, valida + reporta errores; NO son INSERTS manuales) | 3-4h |
| 5 | — | Release manager: coordinar freeze + PR `dev`→`main` final + tag `v2.0-E2` cuando David firme | 1-2h |
| 6 | — | Grabar video-demo E2 (Anexo B) | 2-3h |

**#99 (Actualizar Flask/Python) → MOVIDO A BACKLOG.** Se difiere a E3 (mid-sprint upgrade = riesgo alto).

---

## Ceremonias

- **Planning:** hoy (este doc es el output)
- **Dailies:** lun / mié / jue · 10-15 min (Matías participa)
- **Freeze `dev`:** jue 28/08 EOD (coordina Seba)
- **Envío a David:** vie 29/08 mediodía (Seba manda el paquete)
- **Release `dev` → `main`:** cuando David firme (Seba ejecuta)
- **Retro + planning E3:** lun 01/09

---

## Definition of Done

Un item está *done* cuando:
1. PR mergeado a `dev` con review de otro integrante
2. CI verde
3. Acceptance criteria del issue cumplido
4. Flujo end-to-end probado manualmente
5. Checkbox del kanban movido a Done

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| #54 se extiende (Facu solo, L) | Daily del mié 20/08 (mitad sprint): si < 60% avance, cortamos scope. |
| #85 no llega a completarse | Se completa al arranque de E3, no bloquea la entrega de E2. |
| CI genera fricción | Escribirlo en la retro, no desactivar. |
| David no completa el formulario | Recordatorio lunes 01/09. Si no responde en 48h, escalar a Hugo. |

---

## Anexo A — Las 8 contradicciones para `SCOPE_v3.0.md` (Ivo)

Fuente: cruce de Scope v2.0 + SRS v2.0 + TO BE v2.1 + AS IS v2.0 + Plan v1.1 (todos de 2026-07-01).

| # | Tema | Contradicción | Decisión propuesta (Ivo ratifica o discute) |
|---|---|---|---|
| C1 | Roles: 4 o 2 | Scope/SRS/TO BE dicen 4 (ADMIN, RAYPAC, DML_ST, DML_REPUESTOS); AS IS §4 propone 2 (RAYPAC + DML con admin como atributo) | Van 4. Actualizar AS IS. |
| C2 | Umbrales stock | Scope F20: 1=Naranja, 2=Amarillo; TO BE F20: 1=Amarillo, 2=Naranja (invertido); SRS RF27 coincide con Scope; Scope §5.1 usa escala totalmente distinta (1-5, 6-10, >10) | Van Scope F20 / SRS RF27. Borrar §5.1 y corregir TO BE. |
| C3 | Máquina irreparable | Plan F32 propone "flujo devolución por irreparabilidad" — David dijo textual en la reunión: *"todas son reparables, no existe máquina irreparable"* | Eliminar F32 o redefinir como "devolución sin reparar por costo económico". |
| C4 | F30-F34 fantasmas | Aparecen en Plan v1.1 sin numeración en Scope/SRS/TO BE | Mover F30 (PRs Git), F33 (UptimeRobot), F34 (soporte 30 días) a categoría "operacional" fuera del scope funcional. F31 (log errores) mapea a RNF08. F32 se elimina. |
| C5 | "Jira" en el Plan | Plan v1.1 dice "backlog en Jira" — se usa GitHub Projects | Corregir a "GitHub Projects" en el Plan. |
| C6 | SRS "en revisión" | SRS v2.0 dice "En Proceso de Revisión (Corrección de Brechas)", el resto dice "Homologado/Consolidado" | Cerrar la revisión o degradar el SRS a "referencia" (el Scope tiene el peso). |
| C7 | Comerciales | AS IS lista 9 en el form actual; SRS RF08 nombra 4; David en la reunión listó 5 (Leonardo Bastagel, Luciana, Ezequiel Pacheco, Daniela Sofio, +1 a confirmar) | Van los 5 que dijo David. Pedirle el nombre del quinto en el mensaje del 29/08. |
| C8 | Fechas pasadas en supuestos | Supuesto 5 del Scope dice "formato PDF congelado por acta antes del 19/06/26" — esa fecha pasó | Reprogramar como "borrador PDF en la demo del 29/08, David lo aprueba antes del 12/09". |

---

## Anexo B — Video-demo E2 (Seba graba)

**Rotación de presenter:** Ivo → julio · **Seba → agosto (este sprint)** · Facu → E3 · Ivo → E4.

**Formato:** celular, horizontal, 3-5 min, sin edición. Grabar el jueves 28/08 EOD o viernes 29/08 mañana (post-freeze de `dev`).

**Guión sugerido:**
1. *"Hola David, te muestro qué hicimos en estas 3 semanas."* (30s)
2. Abrir `raypac-dev.dmlelectricidadind.com.ar`, mostrar login. *"Usuario y clave te los mando aparte."* (30s)
3. Login como RAYPAC → nuevo ingreso → llenar campo por campo con datos reales. (2 min)
4. Cargar remito, freezar. Mostrar que ya no se puede editar. (30s)
5. Cambiar a usuario DML → ver la máquina en la solapa Fichas. (30s)
6. *"Probá vos 2-3 ingresos. Después completá el formulario que te mando. Cualquier duda me escribís."* (30s)

---

## Anexo C — Formulario feedback (Ivo arma en Google Forms)

**Título:** *"Feedback de la 2ª entrega — Módulo RAYPAC"*

1. ¿Pudiste crear un ingreso completo sin problemas? [Sí / Sí pero con algún problema / No]
2. Si tuviste problemas, ¿cuáles? [texto libre]
3. ¿Faltó algún campo que necesites en el ingreso? [texto libre]
4. Del 1 al 5, ¿qué tan claro te resultó el formulario? [1-5]
5. Comentarios libres [texto libre]

Se envía junto con el video, el viernes 29/08 mediodía por WhatsApp. Recordatorio a las 48h si David no lo completó.
