import json
import os
from datetime import datetime

# Paths
BASE_DIR = "/Users/jose/Library/CloudStorage/OneDrive-DirecciónProvincialdeMelilla/Proyectos/Partes de salida/student-finder"
TIMETABLE_FILE = "/Users/jose/Library/CloudStorage/OneDrive-DirecciónProvincialdeMelilla/Proyectos/Partes de salida/horarios_profesores_limpio.json"

# Load Timetable
with open(TIMETABLE_FILE, 'r', encoding='utf-8') as f:
    TIMETABLE = json.load(f)

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

def get_session_info_for_time(time_str):
    for i, (start, end, name) in enumerate(SESSIONS):
        if start <= time_str < end:
            return name, i
    return None, -1

def get_teacher_for_group(group_name, session_name, spanish_day):
    # (Same implementation as in server.py)
    for teacher in TIMETABLE:
        for tramo in teacher.get('horario', []):
            if session_name in tramo.get('tramo', ''):
                class_info = tramo.get(spanish_day, {})
                teacher_group = class_info.get('grupo', '')
                if not teacher_group: continue
                if isinstance(teacher_group, list):
                    if group_name in teacher_group: return teacher
                elif isinstance(teacher_group, str):
                    if group_name == teacher_group or (group_name in teacher_group and "_" in teacher_group):
                        return teacher
    return None

# Test Cases
test_cases = [
    {"time": "08:45", "day": "Martes", "group": "E_3B", "vuelve": False, "horas": 0}, 
    {"time": "08:45", "day": "Martes", "group": "E_3B", "vuelve": True, "horas": 2},
    {"time": "12:53", "day": "Viernes", "group": "E_1C", "vuelve": False, "horas": 0},
]

for test in test_cases:
    print(f"\n--- Testing: Time={test['time']}, Day={test['day']}, Group={test['group']}, Vuelve={test['vuelve']}, Horas={test['horas']} ---")
    s_name, s_idx = get_session_info_for_time(test['time'])
    if s_name:
        if not test['vuelve']:
            affected = SESSIONS[s_idx:s_idx+5] # Test with 5 subsequent sessions
        else:
            affected = SESSIONS[s_idx:s_idx + test['horas']]
        
        for _, _, name in affected:
            if "Recreo" in name: continue
            teacher = get_teacher_for_group(test['group'], name, test['day'])
            teacher_name = teacher['nombre'] if teacher else "None"
            print(f"  Session {name}: {teacher_name}")
    else:
        print(" Outside school hours")
