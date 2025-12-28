# logic.py
import subprocess
import os
import sys
import time
import json
from datetime import date

try:
    from core import (
        log_event, SECURITY_LOG_FILE, get_tasks_for_today, 
        verify_and_get_date
    )
except ImportError:
    # Fallback de segurança
    def log_event(t, m, category="system"): print(f"LOG [{category}][{t}]: {m}")
    SECURITY_LOG_FILE = "config/logs/security_log.json"
    def get_tasks_for_today(): return {}
    def verify_and_get_date(d): return d

# Configuração
SCRIPT_NAME = "identidade_rejeitada.py" 
DAEMON_FLAG = "--daemon"
LOG_FILE = SECURITY_LOG_FILE

def get_daemon_path():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()
    return os.path.join(base_dir, SCRIPT_NAME)

def is_daemon_running():
    """Verifica se o daemon já está rodando."""
    cmd = 'wmic process get commandline'
    try:
        output = subprocess.check_output(cmd, shell=True).decode(errors='ignore')
        if f"{SCRIPT_NAME}\" {DAEMON_FLAG}" in output or f"{SCRIPT_NAME} {DAEMON_FLAG}" in output:
            return True
    except:
        pass
    return False

def resurrect_daemon():
    script_path = get_daemon_path()
    if os.name == 'nt':
        subprocess.Popen(["pythonw", script_path, DAEMON_FLAG], 
                         creationflags=subprocess.CREATE_NO_WINDOW | 0x00000008)
    else:
        subprocess.Popen(["python", script_path, DAEMON_FLAG])

def check_if_tasks_completed():
    """
    Retorna True se TODAS as tarefas de hoje já estiverem concluídas/validadas.
    Nesse caso, o Daemon não é obrigado a estar rodando.
    """
    tasks = get_tasks_for_today()
    if not tasks: return False # Se não tem tarefas, assume que precisa rodar
    
    today_str = date.today().isoformat()
    all_done = True
    
    for task in tasks.values():
        raw_comp = task.get('completed_on')
        valid_date = verify_and_get_date(raw_comp)
        if valid_date != today_str:
            all_done = False
            break
            
    return all_done

def has_daemon_started_today():
    """
    Verifica no log se existe um evento 'system_start' com a data de hoje.
    Retorna True se o Daemon já rodou pelo menos uma vez hoje.
    """
    try:
        if not os.path.exists(LOG_FILE): return False
        
        today_str = date.today().isoformat()
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
            
        # Procura por system_start na data de hoje
        for entry in logs:
            if entry.get('date') == today_str and entry.get('type') == 'system_start':
                return True
    except:
        pass
    return False

if __name__ == "__main__":
    if not is_daemon_running():
        
        # --- INTELIGÊNCIA ---
        
        # 1. Se já acabou tudo por hoje, deixa o usuário em paz.
        if check_if_tasks_completed():
            sys.exit()

        # 2. Se as tarefas NÃO estão feitas, precisamos saber se é Boot ou Sabotagem.
        started_today = has_daemon_started_today()
        
        if started_today:
            # CENÁRIO: SABOTAGEM
            # O Daemon já tinha iniciado hoje, e agora sumiu. O usuário matou.
            try:
                log_event("DAEMON_DEAD", "ALERTA: Daemon iniciado hoje mas processo sumiu (Sabotagem).", category="security")
            except: pass
            resurrect_daemon()
            
        else:
            # CENÁRIO: BOOT / LOGIN
            # O Daemon ainda não registrou presença hoje. Provavelmente o PC acabou de ligar.
            # Apenas ressuscita (inicia) sem gerar log de morte.
            log_event("WATCHDOG_SYSTEM", "Primeiro boot do dia ou delay de registro. Iniciando silenciosamente.", category="security")
            resurrect_daemon()

    # Se já estiver rodando, tudo ok.