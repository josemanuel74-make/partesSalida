# Instrucciones: Sistema de Control de Salidas

Esta aplicación permite buscar alumnos, verificar sus tutores y registrar sus salidas. Los datos se guardan en un archivo `salidas.csv`.

## ⚠️ IMPORTANTE: Cómo Iniciar
Para que el botón "Grabar Salida" funcione, **debes iniciar el servidor incluido** (no basta con abrir el archivo HTML).

1. Abre la terminal en esta carpeta (`student-finder`).
2. Ejecuta el siguiente comando:
   ```bash
   python3 server.py
   ```
3. Verás un mensaje que dice `Server started at http://localhost:8000`.
4. Abre tu navegador web y escribe: `http://localhost:8000`

## Uso
1. **Buscar**: Escribe el nombre, DNI o grupo del alumno.
2. **Verificar**: En la ficha verás los datos del alumno y de sus **Tutores (Nombre y DNI)**.
3. **Registrar Salida**:
   - Pulsa el botón "Registrar Salida".
   - Selecciona el **Motivo** (Cita Médica, Enfermedad, etc.).
   - Selecciona el **Acompañante** (Solo, Tutor 1, Tutor 2...).
   - Pulsa **Grabar Salida**.
4. **Datos Guardados**: Cada salida se guarda automáticamente en el archivo `salidas.csv` en esta misma carpeta, con fecha y hora.

## Archivos
- `server.py`: El "motor" que guarda los datos.
- `students.json`: Base de datos de alumnos.
- `salidas.csv`: Registro de todas las salidas.
