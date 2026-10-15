import sys
import traceback

import resend
from flask import current_app


def send_mail(to_email, subject, html_body):
    """Envía mail vía Resend. Devuelve True/False, nunca rompe la request."""
    try:
        if not to_email or not to_email.strip():
            print("⚠️ Email destinatario vacío, saltando envío", file=sys.stderr, flush=True)
            return False

        api_key = current_app.config.get("RESEND_API_KEY")
        if not api_key:
            print(f"⚠️ RESEND_API_KEY no configurada. Mail NO enviado a {to_email}", file=sys.stderr, flush=True)
            return False

        # Modo dev: redirige todo a un único mail para no escribirle a usuarios reales
        redirect = current_app.config.get("MAIL_DEV_REDIRECT")
        if redirect:
            subject = f"[DEV → {to_email}] {subject}"
            to_email = redirect

        resend.api_key = api_key
        resend.Emails.send({
            "from": current_app.config["MAIL_FROM"],
            "to": [to_email.strip()],
            "subject": subject,
            "html": html_body,
        })
        print(f"✅ Mail enviado a {to_email}", file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print(f"❌ Error enviando mail a {to_email}: {type(e).__name__}: {e!s}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return False


def get_destinatarios_activos():
    """Emails activos de la tabla usuarios_notificaciones."""
    from CODIGO_FUENTE.extensions import get_db
    rows = get_db().execute(
        "SELECT email FROM usuarios_notificaciones WHERE activo = TRUE"
    ).fetchall()
    return [r["email"] for r in rows]