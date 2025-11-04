#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MODO ESTUDO/TRABALHO (v1)
- Janela transparente e minimalista
- Controla os popups de verificação
"""

import os
import sys
import random
import time
import json
import threading
import subprocess
import platform
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# --- Configurações Básicas e Helpers (Copiados do script principal) ---

IS_WINDOWS = platform.system() == "Windows"
APP_NAME = "IdentidadeRejeitada"
APP_DIR_NAME = "IdentidadeRejeitadaApp"

def get_app_data_dir():
    if IS_WINDOWS:
        app_data_path = os.path.join(os.getenv('APPDATA'), APP_DIR_NAME)
    else:
        app_data_path = os.path.join(Path.home(), '.config', APP_DIR_NAME)
    Path(app_data_path).mkdir(parents=True, exist_ok=True)
    return app_data_path

APP_DATA_DIR = get_app_data_dir()
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
LOG_FILE = os.path.join(APP_DATA_DIR, "logging.json")

def load_config_data():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass # Retorna default abaixo
    
    # Fallback se o arquivo não existir ou estiver corrompido
    return {'study_mode': False, 'tts_speed': 2} 

def save_config_data(data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar config (study_mode): {e}")

def log_event(event_type, details):
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                try: logs = json.load(f)
                except json.JSONDecodeError: logs = []
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().date().isoformat(),
            "type": event_type,
            "details": details
        }
        logs.append(log_entry)
        
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao logar evento (study_mode): {e}")

def center_window(win, width, height):
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f'{width}x{height}+{x}+{y}')

# --- Classe Principal do Modo Estudo ---

class StudyModeApp:
    def __init__(self, root):
        self.root = root
        self.root.config(bg="#212121")
        
        window_width = 600
        window_height = 150
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Posição: Canto inferior esquerdo
        x = 25
        y = screen_height - window_height - 25 # 55px de folga para a barra de tarefas
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.attributes('-transparentcolor', '#212121')
        self.root.attributes('-alpha', 0.6) 
        
        self.accountability_running = True
        self.create_widgets()
        
        # Inicia a verificação
        threading.Thread(target=self.run_accountability_check, daemon=True).start()
        
        # Bind para arrastar a janela
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)
        self.root.bind("<B1-Motion>", self.do_move)

    def create_widgets(self):
        style = ttk.Style()        
        TRANSPARENT_BG = '#212121' 
        
        # --- Configuração dos Estilos ---
        style.configure('TFrame', background=TRANSPARENT_BG)        
        style.configure('TLabel', background=TRANSPARENT_BG)        
        style.configure('TCheckbutton', 
                        background=TRANSPARENT_BG, 
                        foreground='#E0E0E0')
                        
        style.map('TCheckbutton',
                  background=[('active', TRANSPARENT_BG)],
                  indicatorcolor=[('selected', '#ff4444'), ('!selected', '#424242')], 
                  foreground=[('active', '#FFFFFF')]) 

        # --- Criação dos Widgets ---
        main_frame = ttk.Frame(self.root, style="TFrame", padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.completed_var = tk.StringVar(value="0")
        self.completed_checkbox = ttk.Checkbutton(main_frame, text="Voltar ao Gerenciador",
                                                  variable=self.completed_var, 
                                                  command=self.on_checkbox_toggle,
                                                  style='TCheckbutton')
        self.completed_checkbox.pack(pady=(5, 5)) # Adicionado pady

        label = ttk.Label(main_frame, text="MODO ESTUDO/TRABALHO", 
                          font=("Segoe UI", 30, "bold"),
                          foreground="#FF0000", 
                          style="TLabel")
        label.pack(pady=(5, 5))

    def on_checkbox_toggle(self):
        """Volta para o gerenciador principal."""
        if self.completed_var.get() == "1":
            self.accountability_running = False
            
            # 1. Atualiza o config
            config = load_config_data()
            config['study_mode'] = False
            save_config_data(config)
            log_event("study_mode_off", "Modo Estudo/Trabalho desativado.")
            
            # 2. Encontra e executa o script principal
            try:
                main_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "identidade_rejeitada.py")
                if not os.path.exists(main_script_path):
                    main_script_path = "identidade_rejeitada.py" # Tenta no CWD
                
                subprocess.Popen(["pythonw", main_script_path])
            except Exception as e:
                print(f"Erro ao reabrir gerenciador: {e}")
                
            # 3. Fecha esta janela
            self.root.after(100, self.root.destroy)

    def run_accountability_check(self):
        """Thread de verificação que roda DENTRO do modo estudo."""
        while self.accountability_running:
            interval = random.randint(15 * 60, 45 * 60)
            
            slept_time = 0
            while slept_time < interval and self.accountability_running:
                time.sleep(1)
                slept_time += 1
            
            if self.accountability_running:
                # Precisa agendar a messagebox na thread principal
                self.root.after(0, self.ask_accountability)

    def ask_accountability(self):
        """Mostra o popup de verificação."""
        if not self.accountability_running:
            return
            
        # Traz a janela (invisível) para o topo para ser "dona" da messagebox
        self.root.attributes("-topmost", True)
        answer = messagebox.askyesno("Verificação de Foco",
                                       "Você ainda está fazendo o que disse que faria?",
                                       parent=self.root)
        if not answer:
            log_event("accountability_check_failed", "Usuário respondeu 'Não'.")
            # Marca o checkbox programaticamente para sair
            self.completed_var.set("1")
            self.on_checkbox_toggle()
        else:
            log_event("accountability_check_ok", "Usuário respondeu 'Sim'.")

    # --- Funções para arrastar a janela ---
    def start_move(self, event):
        self.root.x = event.x
        self.root.y = event.y

    def stop_move(self, event):
        self.root.x = None
        self.root.y = None

    def do_move(self, event):
        deltax = event.x - self.root.x
        deltay = event.y - self.root.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

# --- Ponto de Entrada ---
if __name__ == "__main__":
    root = tk.Tk()
    app = StudyModeApp(root)
    root.mainloop()