# process_checker.py
import subprocess
import os
import sys

# Configuração
SCRIPT_NAME = "identidade_rejeitada.py" 
DAEMON_FLAG = "--daemon"

def get_daemon_path():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()
    return os.path.join(base_dir, SCRIPT_NAME)

def is_daemon_running():
    """Verifica se o daemon já está rodando."""
    # Usa wmic para buscar a linha de comando exata, evitando falsos positivos
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
    
    if os.name == 'nt': # Windows
        # pythonw inicia sem janela preta
        # DETACHED_PROCESS (0x00000008) garante que o daemon não morra se este script morrer
        subprocess.Popen(["pythonw", script_path, DAEMON_FLAG], 
                         creationflags=subprocess.CREATE_NO_WINDOW | 0x00000008)
    else:
        subprocess.Popen(["python", script_path, DAEMON_FLAG])

if __name__ == "__main__":
    if not is_daemon_running():
        resurrect_daemon()
    # Se estiver rodando, o script simplesmente termina aqui