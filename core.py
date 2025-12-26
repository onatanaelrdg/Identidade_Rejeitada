# core.py
import os
import sys
import json
import shutil
import platform
import subprocess
from datetime import datetime, date
from pathlib import Path

# --- Configurações de Ambiente ---
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
APP_NAME = "IdentidadeRejeitada"
APP_DIR_NAME = "IdentidadeRejeitadaApp"

# --- Setup do Nircmd (Windows) ---
VOLUME_CONTROL = None
if IS_WINDOWS:
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        nircmd_path = os.path.join(script_dir, "complemento", "nircmd.exe")
    except NameError:
        script_dir = os.getcwd()
        nircmd_path = os.path.join(script_dir, "complemento", "nircmd.exe")

    if os.path.exists(nircmd_path):
         VOLUME_CONTROL = nircmd_path

# --- Caminhos e Diretórios ---
def get_app_data_dir():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()
    app_data_path = os.path.join(base_dir, "config")
    Path(app_data_path).mkdir(parents=True, exist_ok=True)
    return app_data_path

APP_DATA_DIR = get_app_data_dir()
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
LOG_FILE = os.path.join(APP_DATA_DIR, "logging.json")
PROOFS_DIR = os.path.join(APP_DATA_DIR, "provas")
Path(PROOFS_DIR).mkdir(parents=True, exist_ok=True)

# --- Funções de Backup e Log ---
def run_backup_system():
    try:
        local_config_dir = get_app_data_dir()
        if IS_WINDOWS:
            appdata_base = os.path.join(os.getenv('APPDATA'), APP_DIR_NAME, 'Backups')
        else:
            appdata_base = os.path.join(Path.home(), '.local', 'share', APP_DIR_NAME, 'Backups')
            
        today_str = date.today().strftime('%Y-%m-%d')
        daily_backup_dir = os.path.join(appdata_base, today_str)
        os.makedirs(daily_backup_dir, exist_ok=True)

        # Snapshot
        snapshot_dir = os.path.join(daily_backup_dir, "Start_of_Day_Snapshot")
        if not os.path.exists(snapshot_dir) and os.path.exists(local_config_dir):
            try: shutil.copytree(local_config_dir, snapshot_dir)
            except: pass

        # Rotação
        for filename in ["config.json", "logging.json"]:
            source_file = os.path.join(local_config_dir, filename)
            if not os.path.exists(source_file): continue
            
            name_only, ext = os.path.splitext(filename)
            path_recente = os.path.join(daily_backup_dir, f"{name_only}_recente{ext}")
            path_anterior = os.path.join(daily_backup_dir, f"{name_only}_anterior{ext}")

            try:
                if os.path.exists(path_recente):
                    if os.path.exists(path_anterior): os.remove(path_anterior)
                    try: os.rename(path_recente, path_anterior)
                    except: 
                        shutil.copy2(path_recente, path_anterior)
                        os.remove(path_recente)
                shutil.copy2(source_file, path_recente)
            except: pass
    except Exception as e:
        print(f"Erro backup: {e}")

def log_event(event_type, details):
    temp_file = f"{LOG_FILE}.tmp"
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                try: logs = json.load(f)
                except: logs = []
        
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "date": date.today().isoformat(),
            "type": event_type,
            "details": details
        })
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, LOG_FILE)
        run_backup_system()
    except Exception as e:
        print(f"Erro log: {e}")

# --- Funções de Configuração ---
def load_config_data():
    default_config = {
        'rejections': [
            "Eu não quero emagrecer", "Eu não quero falar inglês fluentemente",
            "Eu não quero ser rico", "Eu não quero poder ajudar minha mãe",
            "Eu quero continuar sozinho pro resto da minha vida",
            "Eu não quero realizar meus sonhos", "Eu não quero ter disciplina",
            "Eu não quero ser respeitado", "Eu não quero ter controle da minha vida"
        ],
        'tasks': {},
        'tts_speed': 3,
        'consecutive_completion_days': 0,
        'last_completion_date': None,
        'study_mode': False
    }
    config = default_config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for key, value in default_config.items():
                if key not in config: config[key] = value
        except: config = default_config
    
    # Migração simples de tasks antigas
    migrated = False
    for task in config.get('tasks', {}).values():
        if 'schedule_type' not in task:
            task['schedule_type'] = 'daily'; task['schedule_days'] = [0,1,2,3,4,5,6]; migrated = True
        if 'status' not in task:
            task['status'] = 'em progresso'; migrated = True
    
    if migrated or not os.path.exists(CONFIG_FILE):
        save_config_data(config)
    return config

def save_config_data(data):
    temp_file = f"{CONFIG_FILE}.tmp"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, CONFIG_FILE)
        run_backup_system()
    except Exception as e:
        print(f"Erro save config: {e}")

def get_tasks_for_today():
    config = load_config_data()
    routine_tasks = config.get('tasks', {})
    today_weekday = datetime.now().weekday()
    tasks_for_today = {}
    for task_id, task in routine_tasks.items():
        if task.get('status', 'em progresso') != 'em progresso': continue
        schedule_type = task.get('schedule_type', 'daily')
        if schedule_type == 'daily':
            tasks_for_today[task_id] = task
        elif schedule_type == 'custom':
            if today_weekday in task.get('schedule_days', []):
                tasks_for_today[task_id] = task
    return tasks_for_today

def set_system_volume(level_percent):
    if IS_WINDOWS and VOLUME_CONTROL:
        try:
            volume_nircmd = int((level_percent / 100) * 65535)
            subprocess.run([VOLUME_CONTROL, 'mutesysvolume', '0'], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.run([VOLUME_CONTROL, 'setsysvolume', str(volume_nircmd)], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            log_event("volume_set", f"{level_percent}%")
        except: pass
    elif not IS_WINDOWS:
        print("Volume control only implemented for Windows nircmd so far.")

def center_window(win, width, height):
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f'{width}x{height}+{x}+{y}')