import os
import json
import base64
from cryptography.fernet import Fernet
import sys

def generate_key():
    key = Fernet.generate_key()
    print("\n" + "="*50)
    print("NUEVA CLAVE GENERADA (Copia esto en tu .env)")
    print("="*50)
    print(f"STUDENTS_DATA_KEY={key.decode()}")
    print("="*50)
    print("IMPORTANTE: Si pierdes esta clave, perderás el acceso a los datos.\n")
    return key

def encrypt_file(file_path, key):
    if not os.path.exists(file_path):
        print(f"Error: El archivo {file_path} no existe.")
        return

    try:
        fernet = Fernet(key)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = f.read()
        
        # Verify it's valid JSON before encrypting
        json.loads(data)
        
        encrypted_data = fernet.encrypt(data.encode('utf-8'))
        
        backup_path = file_path + ".bak"
        os.rename(file_path, backup_path)
        print(f"Backup creado en: {backup_path}")
        
        with open(file_path, 'wb') as f:
            f.write(encrypted_data)
        
        print(f"¡Éxito! {file_path} ha sido cifrado.")
    except Exception as e:
        print(f"Error durante el cifrado: {e}")

def decrypt_file(file_path, key):
    if not os.path.exists(file_path):
        print(f"Error: El archivo {file_path} no existe.")
        return

    try:
        fernet = Fernet(key)
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = fernet.decrypt(encrypted_data).decode('utf-8')
        
        # Verify it's valid JSON before saving
        json.loads(decrypted_data)
        
        backup_path = file_path + ".enc.bak"
        os.rename(file_path, backup_path)
        print(f"Versión cifrada guardada en: {backup_path}")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(decrypted_data)
        
        print(f"¡Éxito! {file_path} ha sido descifrado y guardado como JSON plano.")
    except Exception as e:
        print(f"Error durante el descifrado: {e}")

def main():
    print("Herramienta de Cifrado para Student Finder")
    print("1. Generar nueva clave")
    print("2. Cifrar archivo JSON (requiere clave)")
    print("3. Descifrar archivo JSON (requiere clave)")
    
    choice = input("\nSelecciona una opción: ")
    
    if choice == '1':
        generate_key()
    elif choice in ['2', '3']:
        key_str = input("Introduce la clave STUDENTS_DATA_KEY: ").strip()
        if not key_str:
            print("Error: Clave no proporcionada.")
            return
        
        path = input("Ruta al fichero (default: data/students.json): ").strip() or "data/students.json"
        
        try:
            if choice == '2':
                encrypt_file(path, key_str.encode())
            else:
                decrypt_file(path, key_str.encode())
        except Exception as e:
            print(f"Error: Clave inválida o error de sistema ({e})")
    else:
        print("Opción no válida.")

if __name__ == "__main__":
    main()
