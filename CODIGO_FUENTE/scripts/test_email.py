"""
Script de prueba para verificar configuración SMTP de Gmail
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_gmail_connection(gmail_user, gmail_password, recipient_email):
    """
    Prueba conexión SMTP con Gmail
    
    Args:
        gmail_user: Tu email de Gmail (ej: tusistema@gmail.com)
        gmail_password: Contraseña de aplicación de 16 caracteres (NO tu contraseña normal)
        recipient_email: Email destino para prueba
    """
    print("=" * 60)
    print("🔧 PRUEBA DE CONFIGURACIÓN SMTP - GMAIL")
    print("=" * 60)
    
    # Configuración Gmail
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    
    print(f"\n📧 Remitente: {gmail_user}")
    print(f"📧 Destinatario: {recipient_email}")
    print(f"🌐 Servidor: {SMTP_SERVER}:{SMTP_PORT}")
    
    try:
        # Crear mensaje de prueba
        msg = MIMEMultipart('alternative')
        msg['From'] = gmail_user
        msg['To'] = recipient_email
        msg['Subject'] = "✅ Prueba de conexión SMTP - Sistema DML"
        
        html_body = """
        <html>
            <body>
                <h2>✅ Configuración SMTP Exitosa</h2>
                <p>Este email confirma que la conexión SMTP está funcionando correctamente.</p>
                <p><strong>Sistema:</strong> DML Gestión de Reparaciones</p>
                <p><strong>Fecha:</strong> {}</p>
                <hr>
                <p style="color: green;">Si recibiste este correo, el sistema está listo para enviar notificaciones automáticas.</p>
            </body>
        </html>
        """.format(MIMEText)
        
        from datetime import datetime
        html_body = html_body.replace("{}", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        
        msg.attach(MIMEText(html_body, 'html'))
        
        print("\n🔐 Conectando al servidor SMTP...")
        
        # Conectar con timeout
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            print("✅ Conexión establecida")
            
            print("🔒 Iniciando TLS...")
            server.starttls()
            print("✅ TLS activado")
            
            print("🔑 Autenticando...")
            server.login(gmail_user, gmail_password)
            print("✅ Autenticación exitosa")
            
            print("📨 Enviando email de prueba...")
            server.send_message(msg)
            print("✅ Email enviado exitosamente")
        
        print("\n" + "=" * 60)
        print("🎉 PRUEBA EXITOSA - Configuración correcta")
        print("=" * 60)
        print("\n📋 PRÓXIMOS PASOS:")
        print("1. Revisa tu bandeja de entrada en:", recipient_email)
        print("2. Si lo recibiste, configura estas variables en Render:")
        print(f"   MAIL_SERVER=smtp.gmail.com")
        print(f"   MAIL_PORT=587")
        print(f"   MAIL_USE_TLS=True")
        print(f"   MAIL_USERNAME={gmail_user}")
        print(f"   MAIL_PASSWORD=[tu_contraseña_app_16_caracteres]")
        print(f"   MAIL_DEFAULT_SENDER=Sistema DML <{gmail_user}>")
        print("\n")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print("\n" + "=" * 60)
        print("❌ ERROR DE AUTENTICACIÓN")
        print("=" * 60)
        print("Problema: Gmail rechazó usuario/contraseña")
        print("\nPosibles causas:")
        print("1. ⚠️ Contraseña de aplicación incorrecta")
        print("2. ⚠️ Verificación en 2 pasos NO activada en Gmail")
        print("3. ⚠️ Contraseña de aplicación NO generada")
        print("\n📖 SOLUCIÓN:")
        print("1. Ve a: https://myaccount.google.com/security")
        print("2. Activa 'Verificación en 2 pasos'")
        print("3. Busca 'Contraseñas de aplicaciones'")
        print("4. Genera una nueva para 'Correo' o 'Otra app'")
        print("5. Usa esos 16 caracteres (sin espacios)")
        print(f"\nError técnico: {e}")
        return False
        
    except smtplib.SMTPException as e:
        print("\n" + "=" * 60)
        print("❌ ERROR SMTP")
        print("=" * 60)
        print(f"Problema con el servidor SMTP: {e}")
        return False
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR INESPERADO")
        print("=" * 60)
        print(f"Tipo: {type(e).__name__}")
        print(f"Mensaje: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("📧 TEST DE CONFIGURACIÓN SMTP - GMAIL")
    print("=" * 60)
    print("\n⚠️  IMPORTANTE: Necesitas una 'Contraseña de Aplicación' de Gmail")
    print("NO uses tu contraseña normal de Gmail\n")
    
    # Solicitar datos
    gmail_user = input("📧 Tu email de Gmail: ").strip()
    
    if not gmail_user:
        print("❌ Email requerido")
        exit(1)
    
    print("\n🔐 Contraseña de Aplicación (16 caracteres)")
    print("   Cómo obtenerla: https://myaccount.google.com/apppasswords")
    gmail_password = input("   Contraseña: ").strip().replace(" ", "")
    
    if not gmail_password:
        print("❌ Contraseña requerida")
        exit(1)
    
    recipient = input("\n📨 Email destino para prueba: ").strip()
    
    if not recipient:
        print("❌ Email destino requerido")
        exit(1)
    
    # Ejecutar prueba
    print("\n")
    test_gmail_connection(gmail_user, gmail_password, recipient)
