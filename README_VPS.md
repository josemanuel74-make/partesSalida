# Guía de Despliegue Seguro en VPS (Flask + Nginx + Certbot)

Esta guía detalla cómo desplegar la versión reforzada de **Student Finder** en tu propio servidor.

## 1. Preparar el Servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias del sistema
sudo apt install python3 python3-pip python3-venv nginx certbot python3-certbot-nginx redis-server -y

# Asegurar que Redis esté corriendo
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

## 2. Configuración del Proyecto

1.  **Subir archivos**: Sube la carpeta del proyecto a `/home/tu_usuario/student-finder`.
2.  **Entorno Virtual (Recomendado)**:
    ```bash
    cd /home/tu_usuario/student-finder
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## 3. Generar Contraseña Segura

Ya no usamos contraseñas en texto plano. Debes generar un "hash" para tu `.env`:

```bash
# Asegúrate de haber instalado las dependencias (flask-bcrypt)
python3 utils/hash_password.py
```
Sigue las instrucciones y copia la línea `ADMIN_PASSWORD_HASH=...`.

## 4. Configurar Variables de Entorno (.env)

Crea el archivo `.env` basado en el ejemplo:
```bash
cp .env.example .env
nano .env
```
Rellena:
- `ADMIN_PASSWORD_HASH`: (El que generaste arriba)
- `STUDENTS_DATA_KEY`: Clave maestra para los datos de los alumnos. Generar con:
  ```bash
  python3 utils/encrypt_data.py
  ```
  (Selecciona la opción 1 para generar una clave).
- `SECRET_KEY`: (Crea una cadena larga y aleatoria)
- `RATELIMIT_STORAGE_URL`: En producción, usa `redis://127.0.0.1:6379/0`
- `DATA_PATH`, `PDF_PATH`, `TIMETABLE_PATH`: Asegúrate de que apunten a tus carpetas en `/home/tu_usuario/...`
- `DEBUG`: 0
- `COOKIE_SECURE`: 1 (Solo cuando tengas HTTPS activo)

### Importante: Cifrado de datos
El fichero `students.json` se almacena **siempre cifrado** en disco.
1. Si subes un nuevo `students.json` manualmente (vía FTP/SSH), debes cifrarlo primero usando `utils/encrypt_data.py` con la clave de tu `.env`.
2. Si pierdes la clave `STUDENTS_DATA_KEY`, los datos de los alumnos serán **irrecuperables**.
3. Las copias de seguridad de la carpeta `data/` contienen datos personales cifrados, lo cual es más seguro y cumple mejor con RGPD.

## 5. Configurar Nginx (Hardened)

1.  Copia la configuración segura:
    ```bash
    sudo cp student-finder.nginx /etc/nginx/sites-available/student-finder
    sudo ln -s /etc/nginx/sites-available/student-finder /etc/nginx/sites-enabled/
    ```
2.  Edita `/etc/nginx/sites-available/student-finder` y pon tu dominio real.
3.  Prueba y reinicia:
    ```bash
    sudo nginx -t
    sudo systemctl restart nginx
    ```
4.  **HTTPS**: `sudo certbot --nginx -d tudominio.com`

## 6. Ejecutar con Gunicorn (Producción)

No uses `python3 server.py` en producción. Usa un servicio de sistema con Gunicorn:

1.  `sudo nano /etc/systemd/system/student-finder.service`
2.  Contenido (Ajusta `tu_usuario`):
    ```ini
    [Unit]
    Description=Gunicorn instance to serve Student Finder
    After=network.target

    [Service]
    User=tu_usuario
    Group=www-data
    WorkingDirectory=/home/tu_usuario/student-finder
    Environment="PATH=/home/tu_usuario/student-finder/venv/bin"
    ExecStart=/home/tu_usuario/student-finder/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8081 server:app
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
3.  Iniciar:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start student-finder
    sudo systemctl enable student-finder
    ```

## Checklist de Seguridad Final

- [ ] `.env` NO está en GitHub (verificado por `.gitignore`).
- [ ] La contraseña es un Hash (BCrypt).
- [ ] HTTPS está activo (Certbot).
- [ ] Los logs de error se guardan en `data/server_error.log`.
- [ ] El proceso corre como usuario normal (no root).
- [ ] Nginx tiene activadas las cabeceras de seguridad (HSTS, CSP).
