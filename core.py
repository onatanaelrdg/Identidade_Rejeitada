# core.py
import os
import sys
import json
import shutil
import hashlib
import random
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

# Sistema de logs
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

FILES_MAP = {
    "security": os.path.join(LOG_DIR, "security_log.json"),
    "history": os.path.join(LOG_DIR, "history_log.json"),
    "system": os.path.join(LOG_DIR, "system_trace.json")
}

SECURITY_LOG_FILE = FILES_MAP["security"]
HISTORY_LOG_FILE = FILES_MAP["history"]

# --- Sistema de backup ---
def run_backup_system(arquivo_alterado=None):
    """
    Realiza o backup.
    Se arquivo_alterado for fornecido, faz backup APENAS dele (modo rápido).
    Se for None, faz backup de tudo e cria snapshot (modo boot).
    """
    try:
        local_config_dir = get_app_data_dir()
        
        if IS_WINDOWS:
            appdata_base = os.path.join(os.getenv('APPDATA'), APP_DIR_NAME, 'Backups')
        else:
            appdata_base = os.path.join(Path.home(), '.local', 'share', APP_DIR_NAME, 'Backups')
            
        today_str = date.today().strftime('%Y-%m-%d')
        daily_backup_dir = os.path.join(appdata_base, today_str)
        os.makedirs(daily_backup_dir, exist_ok=True)

        # --- 1. SNAPSHOT (Apenas no Boot/Primeira execução) ---
        # Se estamos rodando um backup cirúrgico (arquivo_alterado not None), 
        # pulamos a verificação de snapshot para ganhar velocidade, 
        # assumindo que o boot já cuidou disso.
        if arquivo_alterado is None:
            snapshot_dir = os.path.join(daily_backup_dir, "Start_of_Day_Snapshot")
            if not os.path.exists(snapshot_dir) and os.path.exists(local_config_dir):
                try: shutil.copytree(local_config_dir, snapshot_dir)
                except: pass

        # --- 2. ROTAÇÃO INTELIGENTE ---
        files_to_rotate = []
        
        if arquivo_alterado:
            # MODO CIRÚRGICO: O sistema avisou exatamente o que mudou
            if os.path.exists(arquivo_alterado):
                files_to_rotate.append(arquivo_alterado)
        else:
            # MODO COMPLETO (Boot): Varre tudo
            if os.path.exists(CONFIG_FILE):
                files_to_rotate.append(CONFIG_FILE)
            
            if os.path.exists(LOG_DIR):
                for f in os.listdir(LOG_DIR):
                    if f.endswith(".json"):
                        files_to_rotate.append(os.path.join(LOG_DIR, f))

        # Executa a rotação apenas para os arquivos selecionados
        for source_path in files_to_rotate:
            if not os.path.exists(source_path): continue
            
            filename = os.path.basename(source_path)
            name_only, ext = os.path.splitext(filename)
            
            path_recente = os.path.join(daily_backup_dir, f"{name_only}_recente{ext}")
            path_anterior = os.path.join(daily_backup_dir, f"{name_only}_anterior{ext}")

            try:
                if os.path.exists(path_recente):
                    if os.path.exists(path_anterior): 
                        os.remove(path_anterior)
                    try: 
                        os.rename(path_recente, path_anterior)
                    except: 
                        # Fallback para Windows (arquivo em uso)
                        shutil.copy2(path_recente, path_anterior)
                        os.remove(path_recente)
                
                shutil.copy2(source_path, path_recente)
            except: pass
                
    except Exception as e:
        log_event("system_error", f"Erro backup: {e}", category="system")

def create_blockchain_block(last_entry, event_type, details, timestamp_iso, today_iso):
    """
    Gera um dicionário (bloco) com assinatura criptográfica baseada no bloco anterior.
    """
    
    if last_entry:
        prev_hash = last_entry.get('hash', 'GENESIS_MIGRATION_HASH')
    else:
        prev_hash = str(0 * 64)
        
    details_str = str(details)
    payload = f"{timestamp_iso}{event_type}{details_str}{prev_hash}{SECRET_SALT}".encode('utf-8')
    
    current_hash = hashlib.sha256(payload).hexdigest()
    
    return {
        "timestamp": timestamp_iso,
        "date": today_iso,
        "type": event_type,
        "details": details,
        "previous_hash": prev_hash,
        "hash": current_hash
    }

def log_event(event_type, details, category="system"):
    """
    Grava logs. Padrões: system, security, history.
    Se category for 'security' ou 'history', usa a função auxiliar de Blockchain.
    """
    target_file = FILES_MAP.get(category, FILES_MAP["system"])
    
    now = datetime.now()
    timestamp_iso = now.isoformat()
    today_iso = date.today().isoformat()
    
    # Leitura Inicial (IO)
    logs = []
    if os.path.exists(target_file):
        with open(target_file, 'r', encoding='utf-8') as f:
            try: logs = json.load(f)
            except: logs = []

    # --- GERAÇÃO DO REGISTRO ---
    if category in ["security", "history"]:
        # Pega o último registro para encadear (ou None se estiver vazio)
        last_entry = logs[-1] if logs else None
        
        # Chama a função especialista
        entry = create_blockchain_block(last_entry, event_type, details, timestamp_iso, today_iso)
        
    else:
        entry = {
            "timestamp": timestamp_iso,
            "date": today_iso,
            "type": event_type,
            "details": details
        }

    # --- PERSISTÊNCIA E BACKUP ---
    try:
        logs.append(entry)

        # Gravação Atômica
        temp_file = f"{target_file}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(temp_file, target_file)
        
        # Backup Cirúrgico
        run_backup_system(arquivo_alterado=target_file)

    except Exception as e:
        try:
            error_log_path = os.path.join(LOG_DIR, "error_log_event.json")
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} | ERROR: {e} | TYPE: {event_type}\n")
        except: pass
        print(f"Erro ao logar em {category}: {e}")

# --- Funções de Configuração ---
def load_config_data():
    default_config = {
        'rejections': [
            "Eu não quero emagrecer",
            "Eu não quero ser rico", "Eu não quero poder ajudar minha mãe",
            "Eu quero continuar sozinho pro resto da minha vida",
            "Eu não quero realizar meus sonhos", "Eu não quero ter disciplina",
            "Eu não quero ser respeitado", "Eu não quero ter controle da minha vida"
        ],
        'celebrations': [
            "Você está mais perto da vida que quer. Parabéns!",
            "Seu eu do futuro agradece pelas escolhas de hoje. Parabéns!",
            "Disciplina é liberdade. Você venceu o dia de hoje. Parabéns!",
            "Orgulhe-se do que construiu hoje. Você merece. Parabéns!",
            "Aprecie sua vitória de hoje. Ela foi merecida. Parabéns!"
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
        run_backup_system(arquivo_alterado=CONFIG_FILE)
    except Exception as e:
        log_event("system_error", f"Erro save config: {e}", category="system")

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
        log_event("system_error", "Volume control only implemented for Windows nircmd so far.", category="system")

def center_window(win, width, height):
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f'{width}x{height}+{x}+{y}')

# --- SEGURANÇA ANTI-TRAPAÇA ---
SECRET_SALT = "DISCIPLINA_NAO_VEM_DE_FORÇA_DE_VONTADE_MAS_DA_AUSENCIA_DE_ESCOLHA"

def sign_date(date_str):
    """Gera uma string: 'YYYY-MM-DD|HASH_DE_VERIFICACAO'."""
    if not date_str: return None
    # Cria uma assinatura única usando a data + o segredo
    data_to_hash = f"{date_str}{SECRET_SALT}".encode('utf-8')
    signature = hashlib.sha256(data_to_hash).hexdigest()
    return f"{date_str}|{signature}"

def verify_and_get_date(signed_date_str):
    """
    Verifica se a data foi adulterada.
    Retorna a data (string) se for válida.
    Retorna False se foi adulterada ou inválida.
    """
    if not signed_date_str or "|" not in signed_date_str:
        return False # Formato inválido ou antigo (tratar como inválido)
    
    date_part, signature_part = signed_date_str.split("|")
    
    # Recalcula o hash esperado
    expected_data = f"{date_part}{SECRET_SALT}".encode('utf-8')
    expected_signature = hashlib.sha256(expected_data).hexdigest()
    
    if signature_part == expected_signature:
        return date_part # É legítimo
    else:
        return False # PEGO NO FLAGRA!

def get_random_rejections(count=3):
    """Retorna uma lista de 'count' rejeições únicas aleatórias."""
    config = load_config_data()
    rejections = config.get('rejections', [])
    
    if not rejections:
        return ["Você não configurou rejeições."]
    
    # Se pedir mais do que existe, embaralha e retorna tudo o que tem
    if count >= len(rejections):
        random.shuffle(rejections)
        return rejections
    
    return random.sample(rejections, k=count)