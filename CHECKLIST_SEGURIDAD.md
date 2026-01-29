# Guía de Despliegue Seguro - Checklist Final 🛡️

Esta guía es de cumplimiento obligatorio para garantizar que la aplicación sea segura en producción.

## 1. Gestión de Secretos (.env)
- [ ] **Prohibido subir `.env`**: Asegúrate de que `.env` está en `.gitignore` y NUNCA se sube a GitHub o se comparte en archivos ZIP.
- [ ] **SECRET_KEY**: Genera una clave única en el VPS: `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`. Sin ella, la app no arrancará.
- [ ] **DEBUG**: Debe estar a `0` en el `.env` de producción.
- [ ] **COOKIE_SECURE**: Poner a `1` solo cuando HTTPS esté activo vía Certbot.

## 2. Infraestructura y Permisos
- [ ] **Usuario No-Root**: La aplicación debe correr bajo un usuario normal, nunca como `root`.
- [ ] **Permisos de Archivos**:
  - `chmod 600 .env` (Solo lectura para el dueño).
  - `chmod 700 data/ pdfs/` (Solo acceso para el dueño).
- [ ] **Firewall (UFW)**: Solo deben estar abiertos los puertos 80 (redirigido) y 443.

## 3. Servidor de Producción (Gunicorn)
- [ ] **Ejecución**: No uses `python3 server.py`. Usa el servicio systemd configurado para arrancar Gunicorn.
- [ ] **Workers**: Configura 2 o 3 workers para manejar concurrencia.

## 4. Nginx y HTTPS
- [ ] **Certbot**: Ejecuta `sudo certbot --nginx` para activar el certificado SSL.
- [ ] **HSTS**: Una vez que HTTPS funcione, verifica que la cabecera `Strict-Transport-Security` esté activa.
- [ ] **Bloqueos**: Verifica que `https://tu-dominio/.env` devuelva un error 403 o 404.

## 5. Mantenimiento y Rotación
- [ ] **SMTP Filtrado / Fuga de .env**: Si has compartido un archivo ZIP que contenía el `.env` (o si sospechas filtración):
  1. **Rotar SECRET_KEY**: Genera una nueva inmediatamente. Todas las sesiones actuales se invalidarán.
  2. **Rotar SMTP**: Entra en tu cuenta de Google -> Seguridad -> Contraseñas de Aplicaciones. Borra la antigua y genera una nueva.
  3. **Rotar HASH**: Aunque sea un hash, es buena práctica cambiar la contraseña de administración si el .env fue expuesto.
- [ ] **Backups**: Haz copia de seguridad semanal de `data/salidas.csv` y `data/students.json`.

---
**Nota sobre el archivo ZIP compartidos:** Si has compartido un archivo ZIP que contenía el `.env` original, **asume que todas las contraseñas están comprometidas**. Rota la SECRET_KEY y las credenciales SMTP de inmediato.
