# Guía Definitiva de Despliegue en VPS

Sigue estos pasos en orden estricto para poner la aplicación en producción en tu servidor.

## 1. Actualizar Código y Dependencias
En tu terminal de VPS, ejecuta:
```bash
cd /home/guardias/partesSalida
git fetch origin main
git reset --hard origin/main
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Configurar el Entorno (.env)
Si no tienes el archivo `.env`, créalo:
```bash
cp .env.example .env
nano .env
```
Asegúrate de configurar estas rutas exactas:
```ini
DATA_PATH=/home/guardias/partesSalida/data
PDF_PATH=/home/guardias/partesSalida/pdfs
TIMETABLE_PATH=/home/guardias/partesSalida/data/horarios_profesores_limpio.json
DEBUG=0
COOKIE_SECURE=1
```

## 3. Configuración de Seguridad (Claves y Hashes)
Genera los valores para tu `.env`:

1.  **Contraseña de Admin**:
    `./venv/bin/python3 utils/hash_password.py` -> Copia el resultado en `ADMIN_PASSWORD_HASH`.
2.  **Clave de Cifrado**:
    `./venv/bin/python3 utils/encrypt_data.py` (Opción 1) -> Copia el resultado en `STUDENTS_DATA_KEY`.

## 4. Cifrar Datos Actuales
**Muy importante**: La app no arrancará si los archivos JSON no están cifrados en disco.
1. Sube tus archivos `students.json` y `horarios_profesores_limpio.json` a la carpeta `data/`.
2. Ejecuta: `./venv/bin/python3 utils/encrypt_data.py` (Opción 2) para CADA uno de los dos archivos usando la clave que pusiste en el `.env`.

## 5. Configurar el Servicio del Sistema (Gunicorn)
Esto hará que la app arranque sola con el servidor.

1. Crea el archivo: `sudo nano /etc/systemd/system/student-finder.service`
2. Pega este contenido EXACTO:
```ini
[Unit]
Description=Gunicorn instance to serve Student Finder
After=network.target

[Service]
User=guardias
Group=www-data
WorkingDirectory=/home/guardias/partesSalida
Environment="PATH=/home/guardias/partesSalida/venv/bin"
ExecStart=/home/guardias/partesSalida/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8081 server:app
Restart=always

[Install]
WantedBy=multi-user.target
```
3. Activa el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable student-finder
sudo systemctl restart student-finder
```

## 6. Configurar Nginx
Copia la configuración y reinicia Nginx:
```bash
sudo cp student-finder.nginx /etc/nginx/sites-available/student-finder
sudo ln -s /etc/nginx/sites-available/student-finder /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```
