import os
import csv
import json
import secrets
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta
from functools import wraps
import pandas as pd
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet

from flask import Flask, request, jsonify, session, send_from_directory, redirect, url_for, make_response
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# --- INITIALIZATION ---
app = Flask(__name__, static_folder='static', static_url_path='')
load_dotenv()

# Security Configuration (STRICT PRODUCTION SETTINGS)
DEBUG_MODE = os.environ.get('DEBUG', '0') == '1'
IS_PROD = not DEBUG_MODE

# SECRET_KEY is MANDATORY in production
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if IS_PROD:
        raise RuntimeError("FATAL: SECRET_KEY must be set in production environment variables.")
    else:
        SECRET_KEY = secrets.token_urlsafe(32)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG_MODE
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE', '0') == '1'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB Max Upload

bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)

# Rate Limiting with Redis for production (multi-worker support)
STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["2000 per day", "500 per hour"] if DEBUG_MODE else ["5000 per day", "2000 per hour"],
    storage_uri=STORAGE_URI,
    enabled=not DEBUG_MODE  # Disable limiter in local debug mode for easier testing
)

# --- ENCRYPTION SETUP ---
STUDENTS_DATA_KEY = os.environ.get('STUDENTS_DATA_KEY')
if not STUDENTS_DATA_KEY:
    # We must have the key to decrypt personal data.
    # Exception: if the file doesn't exist yet (first run), we might defer this, 
    # but the requirement says "app should NOT start".
    raise RuntimeError("FATAL: STUDENTS_DATA_KEY is missing. Application cannot handle student data.")

try:
    cipher_suite = Fernet(STUDENTS_DATA_KEY.encode())
except Exception as e:
    raise RuntimeError(f"FATAL: Invalida STUDENTS_DATA_KEY format: {e}")

# Paths & Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_PATH', os.path.join(BASE_DIR, "data"))
PDF_DIR = os.environ.get('PDF_PATH', os.path.join(BASE_DIR, "pdfs"))
TIMETABLE_PATH = os.environ.get('TIMETABLE_PATH', os.path.join(DATA_DIR, "horarios_profesores_limpio.json"))

for d in [DATA_DIR, PDF_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

CSV_FILE = os.path.join(DATA_DIR, "salidas.csv")
LOG_FILE = os.path.join(DATA_DIR, "server_error.log")
DB_FILE = os.path.join(DATA_DIR, "sessions.db")

CSV_HEADERS = ["Fecha", "Hora", "ID Alumno", "Nombre", "Grupo", 
               "DNI Alumno", "Motivo", "Acompañante", "Detalle Acompañante", 
               "PDF", "Vuelve", "Horas", "TicketID", "HaVuelto"]

# Ensure CSV exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

# --- DB FOR PERSISTENT SESSIONS ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS sessions 
                        (session_id TEXT PRIMARY KEY, user_id TEXT, expires_at DATETIME)''')
init_db()

# --- UTILS ---
def log_error(msg):
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        f.write(f"{datetime.now()}: {msg}\n")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

def safe_text(text):
    if not text: return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

# --- BUSINESS LOGIC ---
def load_timetable():
    if os.path.exists(TIMETABLE_PATH):
        try:
            with open(TIMETABLE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Error loading timetable: {e}")
def load_secure_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'rb') as f:
            encrypted_content = f.read()
        
        # Check if content is empty
        if not encrypted_content:
            return []
            
        # Try to decrypt. If it fails, assume it might be plain text (for migration) 
        # or it's just wrong key. Requirement: app NO arranca if encrypted fails? 
        # No, requirements said skip plain text.
        decrypted_content = cipher_suite.decrypt(encrypted_content)
        return json.loads(decrypted_content.decode('utf-8'))
    except Exception as e:
        # Check if it was plain text and we are in transition (for dev ease)
        # But for prod we want strict. In local debug, maybe we allow fallthrough?
        # Actually, user requirement: "no debe almacenarse nunca en texto plano".
        log_error(f"Error decrypting secure data at {path}: {e}")
        return []

def save_secure_json(path, data):
    try:
        json_data = json.dumps(data, indent=4)
        encrypted_data = cipher_suite.encrypt(json_data.encode('utf-8'))
        with open(path, 'wb') as f:
            f.write(encrypted_data)
        return True
    except Exception as e:
        log_error(f"Error encrypting secure data at {path}: {e}")
        return False

# --- BUSINESS LOGIC ---
def load_timetable():
    return load_secure_json(TIMETABLE_PATH)

TIMETABLE = load_timetable()

SESSIONS_TIMES = [
    ("07:35", "08:30", "Sesión 1"), ("08:30", "09:25", "Sesión 2"),
    ("09:25", "10:20", "Sesión 3"), ("10:20", "11:15", "Sesión 4"),
    ("11:15", "11:45", "Recreo 1"), ("11:45", "12:40", "Sesión 5"),
    ("12:40", "13:35", "Sesión 6"), ("13:35", "14:30", "Sesión 7"),
    ("14:30", "15:25", "Sesión 8"), ("16:00", "16:55", "Sesión 9"),
    ("16:55", "17:50", "Sesión 10"), ("17:50", "18:45", "Sesión 11"),
    ("18:45", "19:00", "Recreo 2"), ("19:00", "19:55", "Sesión 12"),
    ("19:55", "20:50", "Sesión 13"), ("20:50", "21:45", "Sesión 14"),
]

# Mapping from UI names (1ª, 2ª...) to Timetable names (Sesión 1, Sesión 2...)
SESSION_MAPPING = {
    "1ª": "Sesión 1", "2ª": "Sesión 2", "3ª": "Sesión 3", "4ª": "Sesión 4",
    "5ª": "Sesión 5", "6ª": "Sesión 6", "7ª": "Sesión 7", "8ª": "Sesión 8"
}

def get_current_session_info():
    time_str = datetime.now().strftime("%H:%M")
    for i, (start, end, name) in enumerate(SESSIONS_TIMES):
        if start <= time_str < end:
            return name, i
    return None, -1

def get_teacher_for_group(group_name, session_name):
    if not session_name or not group_name: return None
    day_name = datetime.now().strftime("%A")
    days_map = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", "Thursday": "Jueves", "Friday": "Viernes"}
    spanish_day = days_map.get(day_name)
    if not spanish_day: return None

    for teacher in TIMETABLE:
        for tramo in teacher.get('horario', []):
            if session_name in tramo.get('tramo', ''):
                class_info = tramo.get(spanish_day, {})
                teacher_group = class_info.get('grupo', '')
                if isinstance(teacher_group, list) and group_name in teacher_group: return teacher
                if isinstance(teacher_group, str) and (group_name == teacher_group or (group_name in teacher_group and "_" in teacher_group)): return teacher
    return None

def send_email(to_email, subject, body):
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')
    if not smtp_user or not smtp_pass: return False
    try:
        msg = MIMEMultipart()
        display_name = "Control de Salidas (No responder)"
        sender_email = os.environ.get('SENDER_EMAIL', smtp_user)
        msg['From'] = f"{display_name} <{sender_email}>"
        msg['Reply-To'] = "noreply@iesleopoldoqueipo.com"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        with smtplib.SMTP(os.environ.get('SMTP_SERVER', 'smtp.gmail.com'), int(os.environ.get('SMTP_PORT', 587))) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        log_error(f"Email error: {e}")
        return False

# --- ROUTES ---

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    return send_from_directory('static', 'index.html')

@app.route('/login.html')
def login_page():
    return send_from_directory('static', 'login.html')

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf():
    return jsonify({'csrf_token': generate_csrf()})

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per 15 minutes")
def login():
    data = request.json
    password = data.get('password')
    hashed_pw = os.environ.get('ADMIN_PASSWORD_HASH')
    
    if not hashed_pw:
        return jsonify({"error": "Configuración de seguridad incompleta en el servidor"}), 500
    
    if bcrypt.check_password_hash(hashed_pw, password):
        session.permanent = True
        session['logged_in'] = True
        return jsonify({"status": "success"})
    
    return jsonify({"error": "Contraseña incorrecta"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "success"})

@app.route('/api/student-history', methods=['GET'])
@admin_required
def student_history():
    student_id = request.args.get('id', '')
    total_count = 0
    monthly_count = 0
    current_month = datetime.now().strftime("%Y-%m")
    
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('ID Alumno') == student_id:
                    total_count += 1
                    fecha = row.get('Fecha', '')
                    if fecha and fecha.startswith(current_month):
                        monthly_count += 1
    return jsonify({"count": total_count, "monthlyCount": monthly_count})

@app.route('/api/history', methods=['GET'])
@admin_required
def history():
    exits = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            exits = list(reader)
    exits.reverse()
    return jsonify(exits)

@app.route('/api/history/<pdf_filename>', methods=['DELETE'])
@admin_required
def delete_record(pdf_filename):
    # The filename in the CSV is what we use to match.
    # We should normalize the input pdf_filename to avoid traversal, 
    # but keep it exactly as it probably is in the CSV.
    clean_filename = secure_filename(pdf_filename)
    
    rows = []
    deleted = False
    
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Match against the stored PDF filename
                    if row.get('PDF') == pdf_filename or row.get('PDF') == clean_filename:
                        deleted = True
                        # Remove the actual file
                        target_filename = row.get('PDF') or clean_filename
                        pdf_path = os.path.join(PDF_DIR, target_filename)
                        if os.path.exists(pdf_path) and os.path.isfile(pdf_path):
                            os.remove(pdf_path)
                    else:
                        rows.append(row)
        except Exception as e:
            log_error(f"Error reading CSV during deletion: {e}")
            return jsonify({"error": "Error interno al leer historial"}), 500
    
    if deleted:
        try:
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writeheader()
                writer.writerows(rows)
            return jsonify({"status": "success"})
        except Exception as e:
            log_error(f"Error writing CSV during deletion: {e}")
            return jsonify({"error": "Error al actualizar historial"}), 500
            
    log_error(f"Deletetion failed: record {pdf_filename} not found in CSV.")
    return jsonify({"error": "Registro no encontrado en el historial"}), 404

@app.route('/api/exit', methods=['POST'])
@admin_required
def register_exit():
    try:
        data = request.json
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        vuelve = data.get('vuelve', False)
        horas = data.get('horas', '') if vuelve else ''
        
        # Sanitize ID for filename
        safe_student_id = secure_filename(str(data.get('studentId', 'unknown')))
        pdf_filename = f"ticket_{now.strftime('%Y%m%d_%H%M%S')}_{safe_student_id}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        
        # PDF generation logic...
        try:
            pdf = FPDF()
            pdf.add_page()
            logo_path = os.path.join(DATA_DIR, 'logo.gif')
            if os.path.exists(logo_path):
                pdf.image(logo_path, x=92, y=10, w=25)
            pdf.set_y(38)
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 8, safe_text('PARTE DE SALIDA'), 0, 1, 'C')
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 8, safe_text('I.E.S. Leopoldo Queipo'), 0, 1, 'C')
            pdf.ln(5)
            pdf.set_font("Arial", '', 11)
            
            def row(l, v):
                pdf.set_font("Arial", 'B', 11); pdf.cell(90, 8, safe_text(l), 0, 0, 'R')
                pdf.set_font("Arial", '', 11); pdf.cell(5); pdf.cell(0, 8, safe_text(v), 0, 1, 'L')
                
            row("Fecha:", date_str); row("Hora:", time_str)
            pdf.ln(2); pdf.line(50, pdf.get_y(), 160, pdf.get_y()); pdf.ln(4)
            pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, safe_text("Alumno:"), 0, 1, 'C')
            pdf.set_font("Arial", '', 12); pdf.cell(0, 8, safe_text(data.get('studentName', '')), 0, 1, 'C')
            row("Grupo:", data.get('group', '')); row("DNI:", data.get('dni', ''))
            pdf.ln(4); pdf.line(50, pdf.get_y(), 160, pdf.get_y()); pdf.ln(4)
            pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, safe_text("Motivo:"), 0, 1, 'C')
            pdf.set_font("Arial", '', 11); pdf.cell(0, 8, safe_text(data.get('motive', '')), 0, 1, 'C')
            if vuelve: pdf.ln(3); row("Regreso:", f"SÍ - Horas: {horas}")
            pdf.set_y(-25); pdf.set_font('Arial', 'I', 9); pdf.cell(0, 10, safe_text('Documento oficial de control'), 0, 1, 'C')
            pdf.output(pdf_path)
        except Exception as e:
            log_error(f"Error generating PDF at {pdf_path}: {e}")
            return jsonify({"error": f"Error al generar el PDF: {str(e)}"}), 500

        try:
            ticket_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{safe_student_id}"
            with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([date_str, time_str, data.get('studentId', ''), data.get('studentName', ''),
                                 data.get('group', ''), data.get('dni', ''), data.get('motive', ''),
                                 data.get('accompaniedBy', ''), data.get('tutorName', ''), pdf_filename,
                                 'Sí' if vuelve else 'No', horas, ticket_id, 'No'])
        except Exception as e:
            log_error(f"Error writing to CSV {CSV_FILE}: {e}")
            return jsonify({"error": f"Error al guardar en el historial: {str(e)}"}), 500

        # Notifications logic...
        try:
            guardian_emails = os.environ.get('GUARDIAN_EMAILS', '').split(',')
            
            # Email Templates (Teacher templates are the master ones now)
            teacher_subject_tpl = os.environ.get('EMAIL_TEACHER_SUBJECT', "Aviso Salida Alumno: {periodo}")
            teacher_body_tpl = os.environ.get('EMAIL_TEACHER_BODY', 
                "El alumno {alumno} del grupo {grupo} ha salido del centro.\nMotivo: {motivo}\nPeriodo afectado: {periodo}\n¿Regresa?: {regreso}\n\n--- mensaje automático ---").replace('\\n', '\n')
            
            # Guardian templates fallback to teacher templates for consistency
            guardian_subject_tpl = os.environ.get('EMAIL_GUARDIAN_SUBJECT', teacher_subject_tpl)
            guardian_body_tpl = os.environ.get('EMAIL_GUARDIAN_BODY', teacher_body_tpl).replace('\\n', '\n')

            regreso_text = f"Sí ({horas})" if vuelve else "No"
            
            if guardian_emails:
                subject = guardian_subject_tpl.format(
                    alumno=data.get('studentName'),
                    grupo=data.get('group'),
                    motivo=data.get('motive'),
                    periodo="Varios (RESUMEN)",
                    regreso=regreso_text
                )
                body = guardian_body_tpl.format(
                    alumno=data.get('studentName'), 
                    grupo=data.get('group'), 
                    motivo=data.get('motive'), 
                    periodo=horas if vuelve else "Resto del día",
                    regreso=regreso_text
                )
                for email in guardian_emails:
                    if email.strip(): send_email(email.strip(), subject, body)

            # Identify which sessions to notify
            sessions_to_notify = []
            
            # 1. Current session
            current_sess_name, current_sess_idx = get_current_session_info()
            if current_sess_name:
                sessions_to_notify.append(current_sess_name)

            # 2. Selected future sessions
            if vuelve and horas:
                # 'horas' comes as "1ª, 2ª"
                for h in horas.split(','):
                    mapped = SESSION_MAPPING.get(h.strip())
                    if mapped and mapped not in sessions_to_notify:
                        sessions_to_notify.append(mapped)
            
            # 3. Rest of the day if not returning
            elif not vuelve and current_sess_idx != -1:
                for _, _, s_name in SESSIONS_TIMES[current_sess_idx + 1:]:
                    if "Sesión" in s_name and s_name not in sessions_to_notify:
                        sessions_to_notify.append(s_name)

            # Send emails to teachers
            notified_emails = set()
            notified_teacher_names = []
            student_group = data.get('group', '')
            
            for session_name in sessions_to_notify:
                teacher = get_teacher_for_group(student_group, session_name)
                if teacher and teacher.get('email'):
                    t_email = teacher['email'].strip()
                    t_name = teacher.get('nombre', 'Profesor')
                    if t_email and t_email not in notified_emails:
                        msg_subject = teacher_subject_tpl.format(periodo=session_name)
                        msg_body = teacher_body_tpl.format(
                            alumno=data.get('studentName'),
                            grupo=student_group,
                            motivo=data.get('motive'),
                            periodo=session_name,
                            regreso=regreso_text
                        )
                        
                        if send_email(t_email, msg_subject, msg_body):
                            notified_emails.add(t_email)
                            if t_name not in notified_teacher_names:
                                notified_teacher_names.append(t_name)
                        
        except Exception as e:
            log_error(f"Error in notification logic: {e}")
            notified_teacher_names = []
            # We don't return 500 here to let the operation succeed even if email fails

        return jsonify({"status": "success", "pdf": pdf_filename, "notified": notified_teacher_names})
        
    except Exception as e:
        log_error(f"General error in register_exit: {e}")
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

@app.route('/api/upload-students', methods=['POST'])
@admin_required
def upload_students():
    if 'file' not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nombre de archivo vacío"}), 400
    
    # Validate extension
    if not file.filename.lower().endswith('.xlsx'):
        return jsonify({"error": "Solo se permiten archivos .xlsx"}), 400

    # Secure temp storage
    temp_dir = tempfile.mkdtemp()
    filename = secure_filename(file.filename)
    temp_path = os.path.join(temp_dir, filename)
    
    try:
        file.save(temp_path)
        
        # Check file size (5MB limit redundant with config but safe)
        if os.path.getsize(temp_path) > 5 * 1024 * 1024:
            raise ValueError("El archivo es demasiado grande (máximo 5MB)")

        df = pd.read_excel(temp_path, header=4)
        df.columns = [str(c).strip() for c in df.columns]
        new_students = []
        for _, row in df.iterrows():
            s_name = str(row.get('Alumno/a', '')).strip()
            if not s_name or s_name == 'nan': continue
            new_students.append({
                "id": str(row.get('Nº Id. Escolar', '')).strip(),
                "name": s_name,
                "group": str(row.get('Unidad', '')).strip(),
                "dni": str(row.get('DNI/Pasaporte', '')).strip(),
                "tutor1": { "name": f"{row.get('Nombre Primer tutor', '')} {row.get('Primer apellido Primer tutor', '')}".strip() }
            })
        
        students_file = os.path.join(DATA_DIR, "students.json")
        save_secure_json(students_file, new_students)
        
        return jsonify({"status": "success", "count": len(new_students)})
    
    except Exception as e:
        log_error(f"Error en carga de alumnos: {str(e)}")
        return jsonify({"error": "Error interno al procesar el archivo Excel"}), 500
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

@app.route('/pdfs/<path:filename>')
@admin_required
def serve_pdf(filename):
    filename = secure_filename(filename)
    return send_from_directory(PDF_DIR, filename)

@app.route('/data/<path:filename>')
@admin_required
def serve_data(filename):
    # Allow students.json and images in subdirectories (like photos/)
    if not filename.lower().endswith(('.gif', '.png', '.jpg', '.jpeg', '.json')):
        return "Acceso Denegado", 403
    
    # Use safe path joining to prevent directory traversal
    safe_path = os.path.normpath(filename).lstrip(os.sep)
    if safe_path.startswith('..') or os.path.isabs(safe_path):
        return "Acceso Denegado", 403
        
    # If students.json is requested, return decrypted content
    if filename.lower() == 'students.json':
        students_data = load_secure_json(os.path.join(DATA_DIR, filename))
        return jsonify(students_data)
        
    return send_from_directory(DATA_DIR, safe_path)

# --- SECURITY HEADERS ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self';"
    return response

if __name__ == '__main__':
    # For local testing only. Production uses Gunicorn.
    port = int(os.environ.get('PORT', 40050))
    app.run(host='127.0.0.1', port=port)
