import http.server
import socketserver
import json
import csv
import os
from datetime import datetime
import urllib.parse
from fpdf import FPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import glob
import pandas as pd

PORT = 8081
# Use the directory where the script is located as the base
# Use the directory where the script is located as the base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Prioritize local file for Docker/Self-contained, fallback to parent
TIMETABLE_FILE = os.path.join(BASE_DIR, "horarios_profesores_limpio.json")
if not os.path.exists(TIMETABLE_FILE):
    TIMETABLE_FILE = os.path.join(os.path.dirname(BASE_DIR), "horarios_profesores_limpio.json")

def load_env():
    """Simple .env loader to avoid extra dependencies."""
    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
            print(f"Configuración cargada desde {env_file}")
        except Exception as e:
            print(f"Error cargando .env: {e}")

# Load environment variables from .env file
load_env()

# Email Configuration (Should be provided by environment variables or a config file)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '') # Use App Password for Gmail
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', SMTP_USER)
GUARDIAN_EMAILS = os.environ.get('GUARDIAN_EMAILS', '').split(',') # Comma-separated list in .env

# Ensure PDF directory exists
# Ensure directories exist
# Ensure directories exist
# Allow external data path configuration for security
default_data = os.path.join(BASE_DIR, "data")
default_pdfs = os.path.join(BASE_DIR, "pdfs")

DATA_DIR = os.environ.get('DATA_PATH', default_data)
PDF_DIR = os.environ.get('PDF_PATH', default_pdfs)

# Ensure absolute paths if relative paths were provided in env
if not os.path.isabs(DATA_DIR):
    DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, DATA_DIR))
if not os.path.isabs(PDF_DIR):
    PDF_DIR = os.path.abspath(os.path.join(BASE_DIR, PDF_DIR))

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
if not os.path.exists(PDF_DIR):
    os.makedirs(PDF_DIR)

# Update file references based on new directories
CSV_FILE = os.path.join(DATA_DIR, "salidas.csv")
LOG_FILE = os.path.join(DATA_DIR, "server_error.log")

# CSV Headers
CSV_HEADERS = ["Fecha", "Hora", "ID Alumno", "Nombre", "Grupo", 
               "DNI Alumno", "Motivo", "Acompañante", "Detalle Acompañante", 
               "PDF", "Vuelve", "Horas", "TicketID", "HaVuelto"]

# Check for Docker directory issue
if os.path.exists(CSV_FILE) and os.path.isdir(CSV_FILE):
    print("CRITICAL ERROR: 'salidas.csv' is a directory!")
    print("This often happens in Docker if the file didn't exist on the host before mounting.")
    print("Please delete the directory 'salidas.csv' on your host machine and create an empty file instead.")
    # We cannot proceed safely
    exit(1)

# Ensure CSV header exists or update it if needed
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
else:
    # Check if headers match, if not, we might need to migrate (simple append check)
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, [])
            if len(header) < len(CSV_HEADERS):
                # Simple migration: Read all, rewrite with new header
                # This handles adding new columns
                rows = list(reader)
                
        if len(header) < len(CSV_HEADERS):
            print("Migrating CSV to new format...")
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
                for row in rows:
                    # Pad row with empty strings for new columns
                    while len(row) < len(CSV_HEADERS):
                        row.append("")
                    writer.writerow(row)
    except Exception as e:
        print(f"Error checking CSV headers: {e}")

# Load Timetable Data
TIMETABLE = []
if os.path.exists(TIMETABLE_FILE):
    try:
        with open(TIMETABLE_FILE, 'r', encoding='utf-8') as f:
            TIMETABLE = json.load(f)
        print(f"Timetable loaded: {len(TIMETABLE)} teachers.")
    except Exception as e:
        print(f"Error loading timetable: {e}")
else:
    print(f"TIMETABLE NOT FOUND at {TIMETABLE_FILE}")

def get_current_session():
    """Maps current time to school session tramo name."""
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    
# Session ranges based on horarios_profesores_limpio.json
SESSIONS = [
    ("07:35", "08:30", "Sesión 1"),
    ("08:30", "09:25", "Sesión 2"),
    ("09:25", "10:20", "Sesión 3"),
    ("10:20", "11:15", "Sesión 4"),
    ("11:15", "11:45", "Recreo 1"),
    ("11:45", "12:40", "Sesión 5"),
    ("12:40", "13:35", "Sesión 6"),
    ("13:35", "14:30", "Sesión 7"),
    ("14:30", "15:25", "Sesión 8"),
    ("16:00", "16:55", "Sesión 9"),
    ("16:55", "17:50", "Sesión 10"),
    ("17:50", "18:45", "Sesión 11"),
    ("18:45", "19:00", "Recreo 2"),
    ("19:00", "19:55", "Sesión 12"),
    ("19:55", "20:50", "Sesión 13"),
    ("20:50", "21:45", "Sesión 14"),
]

def get_current_session_info():
    """Returns (session_name, session_index) for the current time."""
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    
    for i, (start, end, name) in enumerate(SESSIONS):
        if start <= time_str < end:
            return name, i
    return None, -1

def get_teacher_for_group(group_name, session_name):
    """Finds the teacher who has class with the given group at the current session."""
    if not session_name or not group_name:
        return None
    
    day_name = datetime.now().strftime("%A")
    # Map Python day names to Spanish day names in JSON
    days_map = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miércoles",
        "Thursday": "Jueves",
        "Friday": "Viernes"
    }
    spanish_day = days_map.get(day_name)
    if not spanish_day:
        return None # Weekend or error

    # Normalize group name (e.g., "1º ESO A" -> "E_1A")
    # This mapping might need refinement depending on how groups are named in both files
    # For now, let's try to match if the group_name is contained in the timetable group
    
    for teacher in TIMETABLE:
        for tramo in teacher.get('horario', []):
            if session_name in tramo.get('tramo', ''):
                class_info = tramo.get(spanish_day, {})
                teacher_group = class_info.get('grupo', '')
                
                if not teacher_group:
                    continue
                    
                # teacher_group can be a string or a list of strings
                if isinstance(teacher_group, list):
                    if group_name in teacher_group:
                        return teacher
                elif isinstance(teacher_group, str):
                    if group_name == teacher_group or (group_name in teacher_group and "_" in teacher_group):
                        return teacher
    return None

def print_group_schedule(group_name):
    """Prints the complete schedule for a group for the current day to the console."""
    day_name = datetime.now().strftime("%A")
    days_map = {"Monday":"Lunes", "Tuesday":"Martes", "Wednesday":"Miércoles", "Thursday":"Jueves", "Friday":"Viernes"}
    spanish_day = days_map.get(day_name)
    if not spanish_day: return

    print(f"\n--- HORARIO DEL GRUPO {group_name} PARA EL {spanish_day.upper()} ---")
    
    # We'll iterate through all sessions and find what the group is doing
    for _, _, s_name in SESSIONS:
        if "Recreo" in s_name:
            print(f"{s_name:10} | [RECREO]")
            continue
            
        found = False
        for teacher in TIMETABLE:
            for tramo in teacher.get('horario', []):
                if s_name in tramo.get('tramo', ''):
                    class_info = tramo.get(spanish_day, {})
                    teacher_group = class_info.get('grupo', '')
                    
                    match = False
                    if isinstance(teacher_group, list):
                        if group_name in teacher_group: match = True
                    elif isinstance(teacher_group, str):
                        if group_name == teacher_group or (group_name in teacher_group and "_" in teacher_group):
                            match = True
                    
                    if match:
                        materia = class_info.get('materia', '---')
                        aula = class_info.get('aula', '---')
                        teacher_name = teacher.get('nombre', 'Desconocido')
                        print(f"{s_name:10} | {materia:10} | Aula: {aula:5} | Prof: {teacher_name}")
                        found = True
                        break # Found the teacher for this session
            if found: break
        
        if not found:
            print(f"{s_name:10} | Sin clase programada")
    print("----------------------------------------------------------\n")

def send_teacher_email(teacher, student_name, group, motive):
    """Sends an email notification to the teacher."""
    if not teacher or not teacher.get('email'):
        print("No teacher email found to send notification.")
        return False
    
    if not SMTP_USER or not SMTP_PASS:
        print("SMTP Credentials not configured. Skipping email.")
        return False

    # For debugging, you might want to redirect all emails to a single address
    # debug_email_override = os.environ.get('DEBUG_EMAIL_OVERRIDE')
    # if debug_email_override:
    #     dest_email = debug_email_override
    #     print(f"DEBUG: Redirecting email from {teacher.get('email')} to {dest_email}")
    # else:
    dest_email = teacher['email']

    try:
        msg = MIMEMultipart()
        # Explicit name and sender
        msg['From'] = f"Partes de Salida <{SENDER_EMAIL}>"
        msg['To'] = dest_email
        msg['Reply-To'] = "no-atender@iesleopoldoqueipo.com"
        msg['Subject'] = f"Aviso de salida de alumno: {student_name} ({group})"
        
        body = f"""
Estimado/a {teacher['nombre']},

Le informamos que el alumno/a {student_name} del grupo {group} ha registrado una salida del centro en este momento.

Motivo: {motive}
Hora de registro: {datetime.now().strftime('%H:%M')}

Este es un mensaje automático generado por el sistema de Partes de Salida.
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Email sent to {teacher['nombre']} ({teacher['email']})")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_guardian_notification(student_name, group, motive, vuelve, horas):
    """Sends a summary notification to the school guardians."""
    valid_guardians = [e.strip() for e in GUARDIAN_EMAILS if e.strip()]
    if not valid_guardians:
        print("No guardian emails configured. Skipping guardian notification.")
        return False

    if not SMTP_USER or not SMTP_PASS:
        print("SMTP Credentials not configured. Skipping guardian notification.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Sistema Partes de Salida <{SENDER_EMAIL}>"
        msg['To'] = ", ".join(valid_guardians)
        msg['Subject'] = f"AVISO GUARDIA: Salida de alumno - {student_name} ({group})"
        
        vuelve_str = f"SÍ (Horas: {horas})" if vuelve else "NO"
        
        body = f"""
Se ha registrado una nueva salida de alumno:

Alumno: {student_name}
Grupo: {group}
Motivo: {motive}
¿Regresa?: {vuelve_str}
Hora: {datetime.now().strftime('%H:%M')}

Este correo se envía automáticamente a los profesores de guardia configurados.
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        print(f"Guardian notification sent to: {', '.join(valid_guardians)}")
        return True
    except Exception as e:
        print(f"Error sending guardian notification: {e}")
        return False

# Admin Password configuration
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')
if ADMIN_PASSWORD == 'admin':
    print("WARNING: Using default password 'admin'. Please set ADMIN_PASSWORD environment variable.")

# Simple in-memory session storage
SESSIONS = set()

class Handler(http.server.SimpleHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def check_auth(self):
        """Checks for valid session cookie. Returns True if authorized."""
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            cookies = cookie_header.split(';')
            for cookie in cookies:
                if 'session_id=' in cookie:
                    token = cookie.split('session_id=')[1].strip()
                    if token in SESSIONS:
                        return True
        return False

    def do_GET(self):
        # Public routes
        if self.path == '/login.html' or self.path == '/style.css':
            self.directory = os.path.join(BASE_DIR, 'static')
            super().do_GET()
            return
        
        # Authentication Check
        if not self.check_auth():
            # If requesting API, return 401
            if self.path.startswith('/api/'):
                self.send_error(401, "Unauthorized")
                return
            # Otherwise redirect to login
            self.send_response(302)
            self.send_header('Location', '/login.html')
            self.end_headers()
            return

        # 1. API Handling
        if self.path.startswith('/api/'):
            if self.path.startswith('/api/student-history'):
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                student_id = params.get('id', [''])[0]
                
                total_count = 0
                monthly_count = 0
                current_month = datetime.now().strftime("%Y-%m")
                
                if os.path.exists(CSV_FILE):
                    with open(CSV_FILE, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('ID Alumno') == student_id:
                                total_count += 1
                                if row.get('Fecha', '').startswith(current_month):
                                    monthly_count += 1
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "count": total_count,
                    "monthlyCount": monthly_count
                }).encode('utf-8'))
                return

            elif self.path == '/api/history':
                try:
                    exits = []
                    if os.path.exists(CSV_FILE):
                        with open(CSV_FILE, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                exits.append(row)
                    
                    # Reverse to show newest first
                    exits.reverse()
                    
                    self._set_headers()
                    self.wfile.write(json.dumps(exits).encode('utf-8'))
                except Exception as e:
                    error_msg = f"Error fetching history: {e}"
                    print(error_msg)
                    with open(LOG_FILE, "a") as log:
                        log.write(f"{datetime.now()}: {error_msg}\n")
                    self.send_response(500)
                    self.end_headers()
                return 

        # 2. PDF Handling 
        elif self.path.startswith('/pdfs/'):
            self.directory = BASE_DIR
            super().do_GET()
            return

        # 3. Data Handling (Authenticated)
        elif self.path.startswith('/data/'):
            # Serve from the configured DATA_DIR
            self.path = self.path.replace('/data/', '/', 1)
            self.directory = DATA_DIR
            super().do_GET()
            return
            
        # 4. Static File Serving (Authenticated)
        if self.path == '/' or self.path == '':
            self.path = '/index.html'
            
        self.directory = os.path.join(BASE_DIR, 'static')
        super().do_GET()
            
    def do_DELETE(self):
        if not self.check_auth():
            self.send_error(401, "Unauthorized")
            return

        # Format: /api/history/<pdf_filename>
        if self.path.startswith('/api/history/'):
            try:
                pdf_filename = self.path.split('/')[-1]
                if not pdf_filename:
                    raise ValueError("No ID provided")
                
                rows = []
                deleted = False
                if os.path.exists(CSV_FILE):
                    with open(CSV_FILE, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('PDF') == pdf_filename:
                                deleted = True
                                pdf_path = os.path.join(PDF_DIR, pdf_filename)
                                if os.path.exists(pdf_path):
                                    try:
                                        os.remove(pdf_path)
                                    except Exception as e:
                                        print(f"Error deleting PDF file: {e}")
                            else:
                                rows.append(row)
                
                if deleted:
                    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                        writer.writeheader()
                        writer.writerows(rows)
                        
                    self._set_headers()
                    self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
                else:
                    self.send_error(404, "Record not found")
                    
            except Exception as e:
                print(f"Error deleting record: {e}")
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def do_POST(self):
        # Login Endpoint (Public)
        if self.path == '/api/login':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                if data.get('password') == ADMIN_PASSWORD:
                    # Generate Session
                    import uuid
                    session_id = str(uuid.uuid4())
                    SESSIONS.add(session_id)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Set-Cookie', f'session_id={session_id}; Path=/; HttpOnly')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
                else:
                    self.send_error(401, "Invalid password")
            except Exception as e:
                self.send_error(500, str(e))
            return

        # Enforce Auth for all other POSTs
        if not self.check_auth():
            self.send_error(401, "Unauthorized")
            return

        if self.path == '/api/exit':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                
                # Extract fields
                timestamp = datetime.now()
                date_str = timestamp.strftime("%Y-%m-%d")
                time_str = timestamp.strftime("%H:%M:%S")
                
                # New Fields
                vuelve = data.get('vuelve', False)
                horas = data.get('horas', '') if vuelve else ''
                
                print(f"Processing Exit Request for {data.get('studentName')}...")

                # Helper for FPDF Latin-1 compatibility
                def safe_text(text):
                    if not text: return ""
                    # FPDF standard fonts are Latin-1. Replace unsupported chars.
                    # normalize unicode characters to closest latin-1 equivalent if possible
                    return str(text).encode('latin-1', 'replace').decode('latin-1')

                # Generate PDF Filename
                pdf_filename = f"ticket_{timestamp.strftime('%Y%m%d_%H%M%S')}_{data.get('studentId', 'unknown')}.pdf"
                pdf_path = os.path.join(PDF_DIR, pdf_filename)
                
                # Generar PDF
                pdf = FPDF()
                pdf.set_auto_page_break(auto=False, margin=0) 
                pdf.add_page()
                
                # Ticket Width Simulation (approx 80mm width typical for thermal, but on A4 we center it)
                # Actually user wants A4 page likely but short.
                # Let's just make it look like the receipt.
                
                # Header
                # Logo Logic
                logo_path = os.path.join(BASE_DIR, 'data', 'logo.gif')
                if os.path.exists(logo_path):
                    try:
                        # Centered logo
                        # Page width ~210mm. Center ~105. Logo width 25. X ~ 92.
                        pdf.image(logo_path, x=92, y=10, w=25)
                    except Exception as img_err:
                        print(f"Warning: Could not load logo: {img_err}")

                pdf.set_y(38) # Move down after logo
                pdf.set_font('Arial', 'B', 14)
                pdf.cell(0, 8, safe_text('PARTE DE SALIDA'), 0, 1, 'C')
                
                pdf.set_font('Arial', '', 12)
                pdf.cell(0, 8, safe_text('I.E.S. Leopoldo Queipo'), 0, 1, 'C')
                
                pdf.ln(5)

                # Info
                pdf.set_font("Arial", size=11)
                
                # Helper for rows
                def ticket_row(label, value, bold_label=True):
                    if bold_label: pdf.set_font("Arial", 'B', 11)
                    else: pdf.set_font("Arial", '', 11)
                    
                    pdf.cell(90, 8, safe_text(label), 0, 0, 'R') # Right align label to center
                    
                    pdf.set_font("Arial", '', 11)
                    # Value starts a bit after center
                    pdf.cell(5) 
                    pdf.cell(0, 8, safe_text(value), 0, 1, 'L')

                # Date/Time
                # In HTML ticket it is separate lines: "Fecha: ...", "Hora: ..."
                ticket_row("Fecha:", date_str)
                ticket_row("Hora:", time_str)
                
                pdf.ln(2)
                # Divider line
                pdf.line(50, pdf.get_y(), 160, pdf.get_y()) # Centered line
                pdf.ln(4)
                
                # Student Info
                # "Alumno:" (Break) "Name"
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 6, safe_text("Alumno:"), 0, 1, 'C')
                pdf.set_font("Arial", '', 12)
                pdf.cell(0, 8, safe_text(data.get('studentName', '')), 0, 1, 'C')
                
                pdf.ln(2)
                ticket_row("Grupo:", data.get('group', ''))
                ticket_row("DNI:", data.get('dni', ''))
                
                pdf.ln(4)
                pdf.line(50, pdf.get_y(), 160, pdf.get_y())
                pdf.ln(4)
                
                # Details
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 6, safe_text("Motivo:"), 0, 1, 'C')
                pdf.set_font("Arial", '', 11)
                pdf.cell(0, 8, safe_text(data.get('motive', '')), 0, 1, 'C') # Centered motive
                
                pdf.ln(2)
                
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 6, safe_text("Acompañado por:"), 0, 1, 'C')
                pdf.set_font("Arial", '', 11)
                
                accomp = data.get('accompaniedBy', '')
                detail = data.get('tutorName', '')
                accomp_text = accomp
                if accomp in ['Tutor1', 'Tutor2', 'Otro']:
                     accomp_text = f"{accomp} ({detail})"
                
                pdf.cell(0, 8, safe_text(accomp_text), 0, 1, 'C')

                if vuelve:
                    pdf.ln(3)
                    ticket_row("Regreso:", f"SÍ - Horas: {horas}")
                
                # Footer
                pdf.set_y(-25)
                pdf.set_font('Arial', 'I', 9)
                pdf.cell(0, 10, safe_text('Documento oficial de control'), 0, 1, 'C')
                
                # Verify directory write access
                if not os.access(PDF_DIR, os.W_OK):
                     raise PermissionError(f"Cannot write to {PDF_DIR}")

                pdf.output(pdf_path)

                # Unique Ticket ID
                ticket_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{data.get('studentId', '0')}"

                # Append to CSV
                with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        date_str,
                        time_str,
                        data.get('studentId', ''),
                        data.get('studentName', ''),
                        data.get('group', ''),
                        data.get('dni', ''),
                        data.get('motive', ''),
                        data.get('accompaniedBy', ''),
                        data.get('tutorName', ''),
                        pdf_filename,
                        'Sí' if vuelve else 'No',
                        horas,
                        ticket_id,
                        'No' # Initial ha_vuelto status
                    ])
                
                # --- Send Guardian Notification ---
                send_guardian_notification(data.get('studentName', ''), data.get('group', ''), data.get('motive', ''), vuelve, horas)
                
                # --- Teacher Notification Logic ---
                try:
                    session_name, session_idx = get_current_session_info()
                    if session_name:
                        print(f"Current session identified: {session_name}")
                        
                        # Print the group's full schedule for manual verification
                        print_group_schedule(data.get('group', ''))
                        
                        affected_sessions = []
                        if not vuelve:
                            # Not returning: Notify all subsequent sessions for the day
                            print(f"Student NOT returning. Notifying all subsequent teachers.")
                            affected_sessions = SESSIONS[session_idx:]
                        else:
                            # Returning in X hours: Notify current session + X-1 subsequent sessions
                            # If horas is "1ª, 2ª", we count how many items are there
                            num_hours = len([h for h in horas.split(',') if h.strip()]) if horas else 1
                            print(f"Student returning. Identified {num_hours} affected sessions based on selection: {horas}")
                            affected_sessions = SESSIONS[session_idx:session_idx + num_hours]
                        
                        notified_teachers = set() # Avoid notifying the same teacher multiple times if they have consecutive hours
                        for _, _, s_name in affected_sessions:
                            if "Recreo" in s_name:
                                continue
                                
                            teacher = get_teacher_for_group(data.get('group', ''), s_name)
                            if teacher and teacher['email']:
                                print(f"[+] Found: {s_name} -> {teacher['nombre']} ({teacher['email']})")
                                if teacher['email'] not in notified_teachers:
                                    send_teacher_email(teacher, data.get('studentName', ''), data.get('group', ''), data.get('motive', ''))
                                    notified_teachers.add(teacher['email'])
                            else:
                                print(f"[-] No teacher found for {s_name} for group {data.get('group', '')}")
                    else:
                        print("Current time is outside school session hours.")
                except Exception as e:
                    print(f"Error in teacher notification flow: {e}")
                # ----------------------------------

                # Send response
                print("Exit registered successfully.")
                self._set_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Exit registered", "pdf": pdf_filename}).encode('utf-8'))
                
            except Exception as e:
                error_msg = f"Error saving data: {str(e)}"
                print(error_msg)
                with open(LOG_FILE, "a") as log:
                    log.write(f"{datetime.now()}: {error_msg}\n")
                
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(error_msg.encode('utf-8'))
        elif self.path == '/api/upload-students':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                file_content = self.rfile.read(content_length)
                
                # Save to temporary file
                temp_excel = os.path.join(DATA_DIR, "temp_upload.xlsx")
                with open(temp_excel, 'wb') as f:
                    f.write(file_content)
                
                print("Processing uploaded Excel file...")
                
                # Process with Pandas
                # User confirmed header is at row 5 (index 4)
                df = pd.read_excel(temp_excel, header=4)
                
                # Basic normalization of column names to lowercase for easier matching
                df.columns = [str(c).strip() for c in df.columns]
                
                # Helper to find column safely
                def get_col_val(row, col_name, default=""):
                    if col_name in row and pd.notna(row[col_name]):
                        return str(row[col_name]).strip()
                    return default

                new_students = []
                
                for index, row in df.iterrows():
                    # Extract basics using exact names found in RegAlum.xls
                    
                    # 'Alumno/a' -> Name
                    # 'Unidad' -> Group
                    # 'DNI/Pasaporte' -> DNI
                    
                    s_name = get_col_val(row, 'Alumno/a', "Sin Nombre")
                    s_group = get_col_val(row, 'Unidad', "Sin Grupo")
                    s_dni = get_col_val(row, 'DNI/Pasaporte', "")
                    
                    # Skip empty rows (sometimes Excel has trailing empty rows)
                    if s_name == "Sin Nombre" and s_group == "Sin Grupo":
                        continue

                    # ID: 'Nº Id. Escolar'
                    s_id = get_col_val(row, 'Nº Id. Escolar', "")
                    if not s_id:
                         s_id = str(abs(hash(s_name + s_dni)))[:8]
                    
                    # Tutors
                    # 'Nombre Primer tutor' + 'Primer apellido Primer tutor' ...
                    t1_name = get_col_val(row, 'Nombre Primer tutor', "") + " " + \
                              get_col_val(row, 'Primer apellido Primer tutor', "") + " " + \
                              get_col_val(row, 'Segundo apellido Primer tutor', "")
                    t1_name = t1_name.strip()
                    t1_dni = get_col_val(row, 'DNI/Pasaporte Primer tutor', "")

                    t2_name = get_col_val(row, 'Nombre Segundo tutor', "") + " " + \
                              get_col_val(row, 'Primer apellido Segundo tutor', "") + " " + \
                              get_col_val(row, 'Segundo apellido Segundo tutor', "")
                    t2_name = t2_name.strip()
                    t2_dni = get_col_val(row, 'DNI/Pasaporte Segundo tutor', "")

                    
                    # Phones
                    phones = []
                    
                    # Prioritize distinct columns
                    p_main = get_col_val(row, 'Teléfono')
                    p_urgency = get_col_val(row, 'Teléfono de urgencia')
                    p_personal = get_col_val(row, 'Teléfono personal alumno/a')
                    p_tutor1 = get_col_val(row, 'Teléfono Primer tutor')
                    p_tutor2 = get_col_val(row, 'Teléfono Segundo tutor')

                    if p_main: phones.append({"label": "Principal", "number": p_main})
                    if p_urgency: phones.append({"label": "Urgencia", "number": p_urgency, "urgent": True})
                    if p_tutor1: phones.append({"label": "Tutor 1", "number": p_tutor1})
                    if p_tutor2: phones.append({"label": "Tutor 2", "number": p_tutor2})
                    if p_personal: phones.append({"label": "Alumno", "number": p_personal})

                    # Email
                    s_email = get_col_val(row, 'Correo electrónico personal alumno/a')
                    if not s_email:
                        s_email = get_col_val(row, 'Correo Electrónico')
                    
                    # Construct Student Object
                    student = {
                        "id": s_id,
                        "name": s_name,
                        "group": s_group,
                        "dni": s_dni,
                        "course": get_col_val(row, 'Curso', s_group), 
                        "email": s_email,
                        "photo": f"data/photos/{s_id}.jpg", 
                        "tutor1": {"name": t1_name, "dni": t1_dni},
                        "tutor2": {"name": t2_name, "dni": t2_dni},
                        "phones": phones
                    }
                    new_students.append(student)
                
                # Save to JSON
                students_file = os.path.join(DATA_DIR, "students.json")
                
                # Backup existing
                if os.path.exists(students_file):
                    os.rename(students_file, students_file + ".bak")
                
                with open(students_file, 'w', encoding='utf-8') as f:
                    json.dump(new_students, f, indent=2, ensure_ascii=False)
                
                print(f"Successfully processed {len(new_students)} students from Excel.")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "count": len(new_students)}).encode('utf-8'))

            except Exception as e:
                print(f"Error processing Excel: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_error(404)

print(f"Server started at http://localhost:{PORT}")
print(f"Data file: {CSV_FILE}")
print(f"PDFs directory: {PDF_DIR}")
print("Press Ctrl+C to stop.")

# Change working directory to script directory to ensure index.html is served correctly
os.chdir(BASE_DIR)

# Use ThreadingTCPServer for concurrent connections
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
    httpd.serve_forever()
