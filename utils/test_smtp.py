import smtplib
from email.mime.text import MIMEText
import os

# Load from .env if possible (manual load to avoid dependencies)
def load_env():
    env = {}
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    env[key] = value
    except:
        pass
    return env

config = load_env()

server = config.get("SMTP_SERVER", "smtp.gmail.com")
port = int(config.get("SMTP_PORT", 587))
user = config.get("SMTP_USER", "")
pwd = config.get("SMTP_PASS", "")
sender = config.get("SENDER_EMAIL", user)

print(f"--- Valores detectados en el archivo .env ---")
print(f"Servidor: {server}")
print(f"Puerto: {port}")
print(f"Usuario: {user}")
print(f"Contraseña: {'********' if pwd else 'VACÍA'}")
print(f"---------------------------------------------\n")

if "TU_CUENTA_DE_GMAIL" in user or "PON_AQUI_TU_CONTRASENA" in pwd:
    print("⚠️ ATENCIÓN: Parece que todavía no has editado el archivo .env con tus datos reales.")
    print("Abre el archivo .env que está en la carpeta 'student-finder' y sustituye los textos de ejemplo.\n")

print(f"Probando conexión con {server}:{port}...")
print(f"Remitente configurado: {sender}")

try:
    print("Conectando al servidor...")
    s = smtplib.SMTP(server, port, timeout=10)
    s.set_debuglevel(1) # Esto mostrará toda la conversación con el servidor
    
    print("Iniciando TLS (STARTTLS)...")
    s.starttls()
    
    print(f"Intentando login para {user}...")
    s.login(user, pwd)
    print("\n¡CONEXIÓN EXITOSA!")
    
    # Send test email
    print(f"Enviando correo de prueba a {user}...")
    msg = MIMEText("Esto es una prueba de conexión SMTP para el sistema de Partes de Salida.")
    msg['Subject'] = 'Prueba SMTP Partes de Salida'
    # Use friendly name and the configured sender_email (noreply)
    msg['From'] = f"Partes de Salida <{sender}>"
    msg['To'] = user
    
    s.send_message(msg)
    print(f"¡Correo de prueba enviado correctamente!")
    
except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ ERROR DE AUTENTICACIÓN (535): {e}")
    print("\n--- POSIBLE SOLUCIÓN ---")
    print("Parece que estás usando una cuenta de Google Workspace.")
    print("1. El sistema NO puede usar tu contraseña normal 'Riesco01' por seguridad.")
    print("2. Tienes que generar una 'Contraseña de Aplicación' de 16 letras.")
    print("3. Ve a: https://myaccount.google.com/apppasswords")
    print("4. Copia el código de 16 letras y ponlo en el .env en lugar de Riesco01.")
except Exception as e:
    print(f"\n❌ ERROR INESPERADO: {e}")
