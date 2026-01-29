import getpass
import sys
try:
    from flask_bcrypt import Bcrypt
    from flask import Flask
except ImportError:
    print("Error: Necesitas instalar flask-bcrypt.")
    print("Corre: pip install flask-bcrypt flask")
    sys.exit(1)

def generate_bash():
    app = Flask(__name__)
    bcrypt = Bcrypt(app)
    
    password = getpass.getpass("Introduce la contraseña que quieres para el panel de administración: ")
    confirm = getpass.getpass("Confírmala de nuevo: ")
    
    if password != confirm:
        print("Las contraseñas no coinciden.")
        return

    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    
    print("\n--- COPIA ESTA LÍNEA A TU ARCHIVO .env ---")
    print(f"ADMIN_PASSWORD_HASH={hashed}")
    print("------------------------------------------\n")

if __name__ == "__main__":
    generate_bash()
