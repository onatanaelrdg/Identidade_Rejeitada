# main.py
import sys
import os
import winreg
import subprocess
import tkinter as tk
from tkinter import messagebox
from core import APP_NAME, IS_WINDOWS

def setup_persistence():
    if not IS_WINDOWS: return True
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bat_daemon = os.path.join(script_dir, "IRS_background.bat")
        
        with open(bat_daemon, "w") as f:
            f.write(f'@echo off\nstart "" pythonw "{os.path.join(script_dir, "identidade_rejeitada.py")}" --daemon')
            
        bat_interface = os.path.join(script_dir, "IRS_task_manager.bat")
        
        with open(bat_interface, "w") as f:
            f.write(f'@echo off\nstart "" pythonw "{os.path.join(script_dir, "identidade_rejeitada.py")}"')

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, f"{APP_NAME}_Daemon", 0, winreg.REG_SZ, bat_daemon)
            winreg.SetValueEx(key, f"{APP_NAME}_Visual", 0, winreg.REG_SZ, bat_interface)
            
        return True
    except Exception as e:
        print(f"Erro persistencia: {e}")
        return True

def setup_scheduler_watchdog():
    """
    Configura o Agendador de Tarefas do Windows para rodar o
    logic.py a cada 5 minutos.
    """
    if not IS_WINDOWS: return
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        checker_script = os.path.join(script_dir, "logic.py")
        
        # Nome da Tarefa no Agendador
        task_name = f"{APP_NAME}_Scheduler"
        
        # Comando: pythonw.exe rodando o checker
        action_cmd = f'pythonw.exe "{checker_script}"'
        
        # Cria a tarefa para rodar a cada 5 minutos (/mo 5)
        cmd = f'schtasks /create /sc minute /mo 5 /tn "{task_name}" /tr "{action_cmd}" /f'
        
        # Executa silenciosamente
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Erro ao configurar Agendador: {e}")

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        # Modo Invisível (Background)
        setup_scheduler_watchdog()
        from daemon import run_daemon_process
        run_daemon_process()
    else:
        # Modo Janela (Gerenciador)
        if setup_persistence():
            setup_scheduler_watchdog()
            
            from gui import App
            root = tk.Tk()
            app = App(root)
            root.mainloop()