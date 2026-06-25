# Log de Uso de IA — Proyecto DML Software de Gestión

Registro de consultas significativas realizadas a Claude (Anthropic) por el equipo de desarrollo.
No se registran consultas menores (nombres de funciones, sintaxis básica, etc.).

---
## [2026-06-25] — Facundo Coca

**Contexto:** Tarea "Identificar endpoints sin autenticación y protegerlos" (Épica 2 — Seguridad).

**Prompt enviado:** Pedí análisis de todas las rutas de CODIGO_FUENTE/app.py para identificar cuáles no tienen @login_required, y cómo proteger la que corresponde a mi tarea.

**Resumen de la respuesta:** Claude analizó el app.py completo, identificó 4 rutas sin @login_required, determinó que 2 son intencionales (vista pública de ticket para clientes) y 2 son problemáticas (/admin/reset-database-with-seeds y /admin/cargar-stock-csv). Para mi tarea, indicó agregar @login_required y @role_required("ADMIN") sobre la función cargar_stock_desde_web.

**Decisión tomada:** Aceptada con revisión. Se verificó manualmente que el resto de rutas sí tenían el decorador antes de aplicar el cambio.

**Estado cognitivo:** Comprendido. Se entiende que los decoradores en Flask actúan como middleware que intercepta la request antes de llegar a la función, y que role_required ya incluye internamente el chequeo de sesión.

---