import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def send_mail(to_email, subject, html_body):
    """Envía mail con manejo de errores y timeout."""
    try:
        # Verificar que email no esté vacío
        if not to_email or not to_email.strip():
            print("⚠️ Email destinatario vacío, saltando envío", file=sys.stderr, flush=True)
            return False

        # Verificar configuración SMTP
        if not current_app.config.get('MAIL_USERNAME'):
            print(f"⚠️ SMTP no configurado (MAIL_USERNAME vacío). Email NO enviado a {to_email}", file=sys.stderr, flush=True)
            print(f"   Asunto: {subject}", file=sys.stderr, flush=True)
            return False

        msg = MIMEMultipart('alternative')
        msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        print(f"📧 Intentando enviar email a {to_email}...", file=sys.stderr, flush=True)
        print(f"   Servidor: {current_app.config['MAIL_SERVER']}:{current_app.config['MAIL_PORT']}", file=sys.stderr, flush=True)

        # Timeout de 10 segundos para evitar bloqueos
        with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'], timeout=10) as server:
            if current_app.config['MAIL_USE_TLS']:
                server.starttls()
            if current_app.config['MAIL_USERNAME']:
                server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✅ Mail enviado exitosamente a {to_email}", file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print(f"❌ Error enviando mail a {to_email}: {type(e).__name__}: {e!s}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        return False
