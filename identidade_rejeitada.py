# main.py
import sys
import os
import winreg
import tkinter as tk
from tkinter import messagebox
from core import APP_NAME, IS_WINDOWS

def setup_persistence():
    if not IS_WINDOWS: return True
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bat_path = os.path.join(script_dir, "IRS_background.bat")
        
        if not os.path.exists(bat_path):
            # Cria o bat automaticamente se não existir
            with open(bat_path, "w") as f:
                # pythonw roda sem janela preta
                f.write(f'@echo off\nstart "" pythonw "{os.path.join(script_dir, "main.py")}" --daemon')
        
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, f"{APP_NAME}_Daemon", 0, winreg.REG_SZ, bat_path)
        return True
    except Exception as e:
        print(f"Erro persistencia: {e}")
        return True

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        # Modo Invisível (Background)
        from daemon import run_daemon_process
        run_daemon_process()
    else:
        # Modo Janela (Gerenciador)
        if setup_persistence():
            from gui import App
            root = tk.Tk()
            app = App(root)
            root.mainloop()