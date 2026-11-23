"""Backup automático semanal por mail (#311).

David pidió que el backup también sea automático: una vez por semana, al
mail que se carga en Admin → Notificaciones por mail (tipo "Backup semanal"),
y que se haga siempre, aunque no haya habido movimientos (si un lunes no
llega, es una alarma).

Render free no tiene tareas programadas: lo dispara un workflow de GitHub
Actions (.github/workflows/backup-semanal.yml) que le pega a
/admin/backup/auto con un token. El resultado de la última corrida queda en
app_meta para mostrarlo en la pantalla de Backup.
"""
import json
from datetime import datetime, timedelta, timezone

from CODIGO_FUENTE.services.backup import generar_backup_zip
from CODIGO_FUENTE.services.mail import get_destinatarios, send_mail

CLAVE_ULTIMO = "backup_auto_ultimo"
DIAS_ALERTA = 8  # semanal + un día de margen
LIMITE_ADJUNTO = 35 * 1024 * 1024  # Resend admite hasta 40 MB por mail
HORA_ARGENTINA = timezone(timedelta(hours=-3))  # sin horario de verano


def _guardar_resultado(db, ok, detalle):
    db.rollback()  # por si lo que falló dejó la transacción abortada
    db.execute("CREATE TABLE IF NOT EXISTS app_meta (clave TEXT PRIMARY KEY, valor TEXT)")
    valor = json.dumps({"fecha": datetime.now(timezone.utc).isoformat(), "ok": ok, "detalle": detalle})
    db.execute(
        """INSERT INTO app_meta (clave, valor) VALUES (%s, %s)
           ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor""",
        (CLAVE_ULTIMO, valor),
    )
    db.commit()


def ejecutar_backup_automatico(db):
    """Genera el backup y lo manda por mail. Devuelve (ok, detalle) y lo deja registrado."""
    destinatarios = get_destinatarios("BACKUP")
    if not destinatarios:
        detalle = "No hay destinatarios: cargá uno en Admin → Notificaciones por mail, tipo «Backup semanal»."
        _guardar_resultado(db, False, detalle)
        return False, detalle

    try:
        nombre, contenido = generar_backup_zip(db)
    except Exception as e:
        detalle = f"No se pudo generar el backup: {type(e).__name__}: {e!s}"
        _guardar_resultado(db, False, detalle)
        return False, detalle

    if len(contenido) > LIMITE_ADJUNTO:
        detalle = f"El backup pesa {len(contenido) // (1024 * 1024)} MB y no entra en un mail."
        _guardar_resultado(db, False, detalle)
        return False, detalle

    html = (
        "<h3>💾 Backup semanal - Software de Gestión DML</h3>"
        f"<p>Adjunto va la copia completa de los datos del sistema (<strong>{nombre}</strong>).</p>"
        "<ul><li><strong>csv/</strong>: una planilla por tabla, se abre con Excel.</li>"
        "<li><strong>backup.sql</strong>: para restaurar el sistema completo.</li></ul>"
        "<p>Tiene datos de clientes y las contraseñas (cifradas) de los usuarios: guardalo en un lugar seguro.</p>"
        "<p>Este mail llega todas las semanas, aunque no haya habido movimientos. "
        "Si una semana no llega, avisá al equipo de desarrollo.</p>"
    )
    if not send_mail(destinatarios, f"💾 Backup semanal DML - {nombre}", html, attachments=[(nombre, contenido)]):
        detalle = f"No se pudo mandar el mail a {', '.join(destinatarios)}."
        _guardar_resultado(db, False, detalle)
        return False, detalle

    detalle = f"{nombre} ({len(contenido) // 1024} KB) enviado a {', '.join(destinatarios)}."
    _guardar_resultado(db, True, detalle)
    return True, detalle


def ultimo_backup_automatico(db):
    """Resultado de la última corrida para la pantalla de Backup, o None si nunca corrió.

    {"fecha": datetime (hora de Argentina), "ok": bool, "detalle": str, "atrasado": bool}. atrasado = hace
    más de DIAS_ALERTA días que no corre: el disparador semanal dejó de andar.
    """
    try:
        fila = db.execute("SELECT valor FROM app_meta WHERE clave = %s", (CLAVE_ULTIMO,)).fetchone()
    except Exception:
        db.rollback()
        return None
    if not fila:
        return None
    datos = json.loads(fila["valor"])
    fecha = datetime.fromisoformat(datos["fecha"])
    return {
        "fecha": fecha.astimezone(HORA_ARGENTINA),
        "ok": datos["ok"],
        "detalle": datos["detalle"],
        "atrasado": datetime.now(timezone.utc) - fecha > timedelta(days=DIAS_ALERTA),
    }
