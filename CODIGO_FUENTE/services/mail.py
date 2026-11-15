import base64
import re
import sys
import traceback

import resend
from flask import current_app


def _normalizar(direcciones):
    """Acepta un string ("a@x.com, b@x.com"), una lista o None, y devuelve
    una lista limpia y sin repetidos."""
    if not direcciones:
        return []
    if isinstance(direcciones, (list, tuple)):
        direcciones = ",".join(d for d in direcciones if d)
    vistos = []
    for d in re.split(r"[;,]", direcciones):
        d = d.strip()
        if d and d.lower() not in [v.lower() for v in vistos]:
            vistos.append(d)
    return vistos


def send_mail(to_email, subject, html_body, attachments=None, cc=None):
    """Envía mail vía Resend. Devuelve True/False, nunca rompe la request.

    to_email y cc aceptan un mail, varios separados por coma, o una lista.
    attachments (#171): lista de (nombre_archivo, bytes).
    """
    try:
        destinatarios = _normalizar(to_email)
        copias = [c for c in _normalizar(cc) if c.lower() not in [d.lower() for d in destinatarios]]
        if not destinatarios:
            print("⚠️ Email destinatario vacío, saltando envío", file=sys.stderr, flush=True)
            return False

        api_key = current_app.config.get("RESEND_API_KEY")
        if not api_key:
            print(f"⚠️ RESEND_API_KEY no configurada. Mail NO enviado a {destinatarios}", file=sys.stderr, flush=True)
            return False

        # Modo dev: redirige todo a un único mail (y descarta las copias)
        redirect = current_app.config.get("MAIL_DEV_REDIRECT")
        if redirect:
            originales = ", ".join(destinatarios + copias)
            subject = f"[DEV → {originales}] {subject}"
            destinatarios = [redirect.strip()]
            copias = []

        params = {
            "from": current_app.config["MAIL_FROM"],
            "to": destinatarios,
            "subject": subject,
            "html": html_body,
        }
        if copias:
            params["cc"] = copias
        if attachments:
            params["attachments"] = [
                {"filename": nombre, "content": base64.b64encode(contenido).decode("ascii")}
                for nombre, contenido in attachments
            ]

        resend.api_key = api_key
        resend.Emails.send(params)
        print(f"✅ Mail enviado a {', '.join(destinatarios)} (cc: {', '.join(copias) or '-'})",
              file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print(f"❌ Error enviando mail a {to_email}: {type(e).__name__}: {e!s}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return False


# Tipos de aviso que se pueden configurar desde Admin → Notificaciones por mail.
TIPOS_AVISO = {
    "STOCK_BAJO": "Stock bajo",
    "MAQUINA_LISTA": "Máquina lista para retirar (copia)",
    "NUEVO_INGRESO": "Nuevo pedido o máquina ingresada",
    "RECEPCION_REPUESTOS": "Recepción de repuestos en DML (aviso a RAYPAC)",
    "BACKUP": "Backup semanal",
}


def get_destinatarios(tipo):
    """Emails activos de usuarios_notificaciones para un tipo de aviso."""
    from CODIGO_FUENTE.extensions import get_db
    rows = get_db().execute(
        "SELECT email FROM usuarios_notificaciones WHERE activo = TRUE AND tipo = %s",
        (tipo,),
    ).fetchall()
    return [r["email"] for r in rows]


def get_destinatarios_activos():
    """Compatibilidad: el aviso de stock bajo sigue usando esta función."""
    return get_destinatarios("STOCK_BAJO")