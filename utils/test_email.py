import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

def test_email():
    load_dotenv()
    
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    sender_email = os.environ.get('SENDER_EMAIL', smtp_user)
    guardian_emails = os.environ.get('GUARDIAN_EMAILS', '').split(',')
    
    if not smtp_user or not smtp_pass:
        print("ERROR: SMTP_USER o SMTP_PASS no configurados en .env")
        return

    test_receiver = guardian_emails[0].strip() if guardian_emails else smtp_user
    print(f"Probando envío de email:")
    print(f"  Servidor: {smtp_server}:{smtp_port}")
    print(f"  Usuario:  {smtp_user}")
    print(f"  De:       {sender_email}")
    print(f"  Para:     {test_receiver}")
    print("-" * 30)

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Prueba Student Finder <{sender_email}>"
        msg['To'] = test_receiver
        msg['Subject'] = "Prueba de conexión SMTP"
        msg.attach(MIMEText("Si recibes este correo, la configuración SMTP es correcta.", 'plain', 'utf-8'))

        print("Conectando al servidor...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.set_debuglevel(1)  # Mostrar detalle técnico
            server.starttls()
            print("Autenticando...")
            server.login(smtp_user, smtp_pass)
            print("Enviando mensaje...")
            server.send_message(msg)
            print("-" * 30)
            print("¡ÉXITO! El correo se ha enviado correctamente.")
            
    except Exception as e:
        print("-" * 30)
        print(f"ERROR AL ENVIAR EMAIL: {e}")
        print("\nPosibles causas:")
        print("1. El puerto 587 está bloqueado en el VPS por el firewall.")
        print("2. Las credenciales de Gmail son incorrectas (¿Has usado una 'App Password'?).")
        print("3. Google está bloqueando la conexión desde una IP nueva.")

if __name__ == "__main__":
    test_email()
