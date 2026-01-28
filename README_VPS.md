# Guía de Despliegue Seguro en VPS (Con Nginx y Certbot)

Has decidido subir el proyecto manualmente usando Nginx como servidor web.

## 1. Preparar el Servidor (VPS)

Asumiendo un VPS con Ubuntu/Debian:

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3, pip, Nginx y Certbot
sudo apt install python3 python3-pip nginx certbot python3-certbot-nginx -y
```

## 2. Subir los Archivos

Sube toda la carpeta `student-finder` a tu VPS, por ejemplo a `/var/www/student-finder`.
Asegúrate de que la carpeta `data/` tenga permisos de escritura.

```bash
# Dar permisos al usuario de Nginx (habitualmente www-data) o a tu usuario
# Si lo ejecutas con tu usuario, asegúrate de que tiene acceso de escritura.
chmod -R 755 /var/www/student-finder
chmod -R 777 /var/www/student-finder/data
chmod -R 777 /var/www/student-finder/pdfs
```

## 3. Instalar Dependencias del Proyecto

```bash
cd /var/www/student-finder
pip3 install -r requirements.txt
# (Asegúrate de ejecutar esto con permisos o en un entorno virtual)
```

## 4. Configurar Seguridad (Variables de Entorno)

Es CRÍTICO que configures una contraseña de administrador segura.
Crea/Edita el archivo `.env` en la carpeta del proyecto:

```bash
nano .env
```

Añade lo siguiente:
```ini
ADMIN_PASSWORD=TuContraseñaSuperSeguraAquí
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tuemail@gmail.com
SMTP_PASS=tu_contraseña_de_aplicacion
SENDER_EMAIL=tuemail@gmail.com
```

### 4.1. (OPCIONAL) Proteger los Datos
Para "esconder" los datos de los alumnos y las fotos, muévelos fuera de la carpeta pública:

1.  Crea una carpeta segura en tu usuario (fuera de /var/www):
    ```bash
    mkdir -p /home/tu_usuario/secure_data
    ```
2.  Mueve la carpeta `data`, `pdfs` y el archivo de horarios allí:
    ```bash
    mv /var/www/student-finder/data /home/tu_usuario/secure_data/
    mv /var/www/student-finder/pdfs /home/tu_usuario/secure_data/
    mv /var/www/student-finder/horarios_profesores_limpio.json /home/tu_usuario/secure_data/
    ```
3.  Añade estas líneas a tu archivo `.env`:
    ```ini
    DATA_PATH=/home/tu_usuario/secure_data/data
    PDF_PATH=/home/tu_usuario/secure_data/pdfs
    TIMETABLE_PATH=/home/tu_usuario/secure_data/horarios_profesores_limpio.json
    ```

## 5. Ejecutar la Aplicación como Servicio

Para que la app de Python se inicie sola:

```bash
sudo nano /etc/systemd/system/student-finder.service
```

Pega esto (ajusta rutas y usuario):

```ini
[Unit]
Description=Student Finder Python Server
After=network.target

[Service]
User=root
# Lo ideal es usar un usuario no-root, pero necesitará acceso a las carpetas.
WorkingDirectory=/var/www/student-finder
ExecStart=/usr/bin/python3 /var/www/student-finder/server.py
Restart=always
EnvironmentFile=/var/www/student-finder/.env

[Install]
WantedBy=multi-user.target
```

Activa el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable student-finder
sudo systemctl start student-finder
```

## 6. Configurar Nginx y Certbot (HTTPS)

1.  **Configurar Nginx**:
    Copia el archivo de configuración incluido o crea uno nuevo:
    
    ```bash
    sudo nano /etc/nginx/sites-available/student-finder
    ```
    
    Pega el contenido:
    ```nginx
    server {
        listen 80;
        server_name tudominio.com; # <--- CAMBIA POR TU DOMINIO REAL
    
        location / {
            proxy_pass http://localhost:8081;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
    ```

2.  **Activar el sitio**:
    ```bash
    sudo ln -s /etc/nginx/sites-available/student-finder /etc/nginx/sites-enabled/
    sudo nginx -t # Comprobar errores
    sudo systemctl restart nginx
    ```

3.  **Activar HTTPS con Certbot**:
    ```bash
    sudo certbot --nginx -d tudominio.com
    ```
    Sigue las instrucciones en pantalla. Certbot modificará la configuración de Nginx automáticamente para securizarla.

¡Listo! Tu web estará segura en `https://tudominio.com`.
