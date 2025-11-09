#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GERENCIADOR DE IDENTIDADE REJEITADA v2.3
- Divisão entre tarefas persitentes e tarefas temporárias
- Mecânica dividida em Daemon (serviço) e Manager (GUI)
- Modo estudo/trabalho dedicado
"""

import os
import sys
import random
import time
import json
import threading
import subprocess
import platform
import shutil
import logging
from datetime import datetime, timedelta, date
from pathlib import Path

# --- Imports da GUI ---
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

# --- Imports de Dependências ---
try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow não instalado. 'pip install pillow'")
    Image = None

try:
    import pystray
    from pystray import MenuItem as item, Menu as menu
except ImportError:
    print("pystray não instalado. 'pip install pystray'")
    pystray = None

# --- Imports Específicos do SO ---
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    import winreg
    import ctypes
    
    # Descobre o caminho completo para o nircmd.exe
    try:
        # Onde o script .py está rodando
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Caminho para o executável na subpasta 'complemento'
        nircmd_path = os.path.join(script_dir, "complemento", "nircmd.exe")
    except NameError:
        # __file__ não é definido em alguns ambientes (ex: REPL)
        # Tenta o caminho de trabalho atual como fallback
        script_dir = os.getcwd()
        nircmd_path = os.path.join(script_dir, "complemento", "nircmd.exe")

    if not os.path.exists(nircmd_path):
         print("\n" + "="*60)
         print(" AVISO: nircmd.exe NÃO ENCONTRADO")
         print(f" O controle de volume não funcionará.")
         print(f" Esperava encontrá-lo em: {nircmd_path}")
         print("="*60 + "\n")
         VOLUME_CONTROL = None # Define como None para sabermos que falhou
    else:
         VOLUME_CONTROL = nircmd_path # Armazena o CAMINHO COMPLETO
else:
    VOLUME_CONTROL = None

# --- Constantes ---
APP_NAME = "IdentidadeRejeitada"
APP_DIR_NAME = "IdentidadeRejeitadaApp"

# --- Funções de Diretório e Config (Globais) ---
# Movidas para o escopo global para que tanto o Daemon quanto a GUI possam usá-las

def get_app_data_dir():
    if IS_WINDOWS:
        app_data_path = os.path.join(os.getenv('APPDATA'), APP_DIR_NAME)
    elif IS_MACOS:
        app_data_path = os.path.join(Path.home(), 'Library', 'Application Support', APP_DIR_NAME)
    else:
        app_data_path = os.path.join(Path.home(), '.config', APP_DIR_NAME)
    
    Path(app_data_path).mkdir(parents=True, exist_ok=True)
    return app_data_path

APP_DATA_DIR = get_app_data_dir()
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
LOG_FILE = os.path.join(APP_DATA_DIR, "logging.json")
PROOFS_DIR = os.path.join(APP_DATA_DIR, "provas")
TEMP_TASKS_FILE = os.path.join(APP_DATA_DIR, "temp_tasks.txt")
Path(PROOFS_DIR).mkdir(parents=True, exist_ok=True)


def load_config_data():
    """Carrega os dados de configuração do JSON e migra o formato antigo."""
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
        'study_mode': False # Chave de comunicação
    }
    
    config = default_config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            
        except json.JSONDecodeError:
            config = default_config
    
    # --- MIGRAÇÃO DE TAREFAS ---
    # Verifica se as tarefas estão no formato antigo e as atualiza
    migrated = False
    tasks = config.get('tasks', {})
    for task_id, task in tasks.items():
        if 'schedule_type' not in task:
            task['schedule_type'] = 'daily'
            task['schedule_days'] = [0, 1, 2, 3, 4, 5, 6] # Seg=0, Dom=6
            migrated = True
        
        # Adiciona o status 'em progresso' se não existir
        if 'status' not in task:
            task['status'] = 'em progresso'
            migrated = True
    
    if migrated:
        print("Migrando formato antigo de tarefas...")
        save_config_data(config)
    
    if not os.path.exists(CONFIG_FILE):
        save_config_data(config)
        
    return config

def save_config_data(data):
    """Salva os dados de configuração no JSON."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")

def log_event(event_type, details):
    """Salva um evento no log JSON."""
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "date": date.today().isoformat(),
            "type": event_type,
            "details": details
        }
        logs.append(log_entry)
        
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Erro ao logar evento: {e}")

def set_system_volume(level_percent):
    """Define o volume mestre do sistema usando nircmd."""
    # Agora verifica se VOLUME_CONTROL não é None (ou seja, se o caminho foi encontrado)
    if IS_WINDOWS and VOLUME_CONTROL:
        try:
            # O nircmd usa uma escala de 0 (mudo) a 65535 (100%)
            volume_nircmd = int((level_percent / 100) * 65535)
            
            # O creationflags=subprocess.CREATE_NO_WINDOW impede o "flash" do cmd
            subprocess.run(
                [VOLUME_CONTROL, 'setsysvolume', str(volume_nircmd)], # Usa o caminho completo
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            log_event("volume_set", f"{level_percent}% (via nircmd)")
        except FileNotFoundError:
             print(f"Erro: nircmd.exe não encontrado em {VOLUME_CONTROL}. O volume não foi alterado.")
        except Exception as e:
            print(f"Erro ao setar volume (nircmd): {e}")
    elif IS_WINDOWS:
        print("Controle de volume (nircmd.exe) não foi encontrado durante a inicialização.")
    else:
        print("Controle de volume não disponível neste SO.")

def load_temp_tasks():
    """Carrega as tarefas temporárias do .txt."""
    if not os.path.exists(TEMP_TASKS_FILE):
        return []
    try:
        with open(TEMP_TASKS_FILE, 'r', encoding='utf-8') as f:
            tasks = [line.strip() for line in f if line.strip()]
        return tasks
    except Exception as e:
        print(f"Erro ao carregar tarefas temporárias: {e}")
        return []

def center_window(win, width, height):
    """Centraliza uma janela tk.Tk ou tk.Toplevel no monitor."""
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f'{width}x{height}+{x}+{y}')

def get_tasks_for_today():
    """Filtra as tarefas de rotina e temp que são para hoje."""
    config = load_config_data()
    routine_tasks = config.get('tasks', {})
    
    today_weekday = datetime.now().weekday() # Segunda = 0, Domingo = 6
    
    tasks_for_today = {}
    for task_id, task in routine_tasks.items():
        
        # Pula tarefas que já estão 'encerradas'
        if task.get('status', 'em progresso') != 'em progresso':
            continue
            
        # Garante que funciona mesmo se uma tarefa for mal formatada
        schedule_type = task.get('schedule_type', 'daily')
        
        if schedule_type == 'daily':
            tasks_for_today[task_id] = task
        elif schedule_type == 'custom':
            if today_weekday in task.get('schedule_days', []):
                tasks_for_today[task_id] = task
                
    temp_tasks = load_temp_tasks()
    
    return tasks_for_today, temp_tasks

# ---
# MECÂNICA 1: O REPRODUTOR (DAEMON)
# ---

class IdentityRejectionSystem:
    """Classe de lógica pura (Daemon). Não tem GUI, apenas áudio e popups."""
    def __init__(self, popup_callback_func):
        self.popup_callback = popup_callback_func
        self.config = load_config_data()
        self.tasks = self.config.get('tasks', {})
        self.running = False
        self.rejection_thread = None
        self.reset_tasks_if_new_day()

    def reload_config(self):
        """Recarrega a configuração para verificar status (study_mode, tasks)."""
        self.config = load_config_data()
        self.tasks = self.config.get('tasks', {})
        self.reset_tasks_if_new_day()

    def save_config(self):
        """Salva o estado atual (usado para dias consecutivos, etc.)."""
        self.config['tasks'] = self.tasks
        save_config_data(self.config)
            
    def reset_tasks_if_new_day(self):
        today_str = date.today().isoformat()
        last_completion = self.config.get('last_completion_date')
        
        if last_completion != today_str:
            all_tasks_completed_yesterday = True
            if not self.tasks:
                all_tasks_completed_yesterday = False
                
            for task_id, task in self.tasks.items():
                if task.get('completed_on') != last_completion:
                    all_tasks_completed_yesterday = False
                    break
            
            if last_completion:
                yesterday = (date.today() - timedelta(days=1)).isoformat()
                if last_completion == yesterday and all_tasks_completed_yesterday:
                    self.config['consecutive_completion_days'] += 1
                elif not all_tasks_completed_yesterday and last_completion:
                    self.config['consecutive_completion_days'] = 0
                    log_event("reset_frequencia", "Atividades não concluídas no dia anterior.")

            # Reseta tarefas para o novo dia
            for task_id, task in self.tasks.items():
                task['completed_on'] = None
                task['proof'] = None
            
            # Garante que o modo estudo não fique "preso" se o PC for reiniciado
            self.config['study_mode'] = False
            self.config['last_completion_date'] = None # Permite que all_tasks_completed verifique hoje
            
            self.save_config()

    def set_volume(self, level_percent):
        set_system_volume(level_percent)

    def speak_text(self, text, tts_speed):
        try:
            if IS_WINDOWS:
                subprocess.run([
                    'powershell', '-Command',
                    f'Add-Type -AssemblyName System.Speech; '
                    f'$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$speak.Rate = {tts_speed}; '
                    f'$speak.Volume = 100; '
                    f'$speak.Speak("{text}")'
                ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            elif IS_MACOS:
                rate = int(120 + (tts_speed * 15)) 
                subprocess.run(['say', '-r', str(rate), text], check=True)
            
            elif IS_LINUX:
                rate = int(140 + (tts_speed * 10))
                try:
                    subprocess.run(['espeak', '-s', str(rate), text], check=True)
                except FileNotFoundError:
                    print("Instale 'espeak' para TTS no Linux")

        except Exception as e:
            print(f"Erro ao reproduzir áudio: {e}")
            log_event("error_tts", str(e))

    def all_tasks_completed(self):
        # 1. Carrega as tarefas filtradas para o dia de HOJE
        tasks_for_today, temp_tasks = get_tasks_for_today()

        # 2. Checa tarefas de rotina de hoje
        all_routine_completed = True
        if not tasks_for_today: # Se não há tarefas de rotina para hoje, não conta como "feito"
            all_routine_completed = False 
        
        for task in tasks_for_today.values():
            if not task.get('completed_on') == date.today().isoformat():
                all_routine_completed = False
                break
        
        # 3. Checa tarefas temporárias
        all_temp_completed = not bool(temp_tasks) # True se a lista estiver vazia

        if all_routine_completed and all_temp_completed:
            today_str = date.today().isoformat()
            if self.config.get('last_completion_date') != today_str:
                self.config['last_completion_date'] = today_str
                log_event("all_tasks_completed", "Todas as atividades (Rotina e Temp) foram concluídas.")
                self.save_config()
            return True
            
        return False

    def get_next_interval(self):
        consecutive_days = self.config.get('consecutive_completion_days', 0)
        bonus_min = consecutive_days * 5
        bonus_max = consecutive_days * 10
        base_min_int = 2
        base_max_int = 3
        min_int = base_min_int + bonus_min
        max_int = base_max_int + bonus_max
        if min_int > max_int:
            min_int = max_int - 10 
        return random.randint(min_int, max_int)

    def play_rejection(self):
        if not self.config['rejections']:
            print("Sem rejeições configuradas.")
            return

        rejection = random.choice(self.config['rejections'])
        tts_speed = self.config.get('tts_speed', 3)
        
        log_event("rejection_played", rejection)
        
        self.set_volume(80)
        
        for _ in range(3):
            if not self.running: break
            
            self.popup_callback(rejection) 
            self.speak_text(rejection, tts_speed)
            time.sleep(0.5) 
            
    def run_rejection_loop(self):
        while self.running:
            try:
                # Recarrega o config a cada ciclo para pegar comandos da GUI
                self.reload_config()
                
                if self.config.get('study_mode', False) or self.all_tasks_completed():
                    time.sleep(30) # Checa a cada 30s se o status mudou
                    continue

                interval_minutes = self.get_next_interval()
                interval_seconds = interval_minutes * 60
                
                print(f"Próxima rejeição em {interval_minutes} minutos.")
                
                for i in range(interval_seconds):
                    if not self.running:
                        break
                    
                    # Checa o status a cada 10 segundos
                    if i % 10 == 0:
                        self.reload_config()
                        if self.config.get('study_mode', False) or self.all_tasks_completed():
                            break # Interrompe a contagem se o modo estudo for ativado
                    
                    time.sleep(1)
                
                # Se a contagem terminou (e não foi interrompida)
                if self.running and not self.config.get('study_mode', False) and not self.all_tasks_completed():
                    self.play_rejection()
            
            except Exception as e:
                print(f"Erro no loop de rejeição: {e}")
                log_event("error_loop", str(e))
                time.sleep(60)

    def start(self):
        self.running = True
        self.rejection_thread = threading.Thread(target=self.run_rejection_loop, daemon=True)
        self.rejection_thread.start()
        log_event("system_start", "Daemon (Reprodutor) iniciado.")
            
    def stop(self):
        self.running = False
        log_event("system_stop", "Daemon (Reprodutor) parado.")
        if self.rejection_thread:
            self.rejection_thread.join(timeout=2)


def show_standalone_popup(root, text):
    """Função de popup que roda em qualquer root de tkinter."""
    try:
        popup = tk.Toplevel(root)
        popup.title("IDENTIDADE REJEITADA")
        center_window(popup, 500, 200)
        popup.attributes("-topmost", True)
        
        popup.overrideredirect(True) 
        popup.protocol("WM_DELETE_WINDOW", lambda: None) 
        
        popup.configure(bg="#1A0000")
        
        label = tk.Label(popup, text=text, font=("Impact", 20),
                         fg="#FF0000", bg="#1A0000",
                         wraplength=480, justify=tk.CENTER)
        label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        popup.after(8000, popup.destroy)
    except Exception as e:
        print(f"Erro ao mostrar popup: {e}")

def run_daemon():
    """Função principal do DAEMON. Roda em background."""
    # Cria uma janela root invisível, apenas para hospedar os popups
    daemon_root = tk.Tk()
    daemon_root.withdraw()
    
    # Passa a função de popup para o sistema
    system = IdentityRejectionSystem(
        popup_callback_func=lambda text: show_standalone_popup(daemon_root, text)
    )
    system.start()
    
    # Mantém o processo vivo (e capaz de mostrar popups)
    try:
        daemon_root.mainloop()
    except KeyboardInterrupt:
        system.stop()

# ---
# MECÂNICA 2: O GERENCIADOR (GUI)
# ---

class App:
    """Classe da Interface Gráfica (Gerenciador). Apenas edita o config.json."""
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        center_window(self.root, 600, 500)
        
        # Carrega os dados de config
        self.config_data = load_config_data()
        self.tasks = self.config_data.get('tasks', {})
        self.temp_tasks = load_temp_tasks()
        self.temp_task_widgets = {}
        
        self.setup_style()
        self.create_main_widgets()
        self.setup_tray_icon()
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.update_task_list()
        
        # Sincroniza o checkbox com o status do config
        # Se o app for aberto e o modo estudo já estiver ativo,
        # o usuário pode desativá-lo por aqui.
        self.study_mode_var.set(self.config_data.get('study_mode', False))

    def setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TFrame", background="#2E2E2E")
        self.style.configure("TLabel", background="#2E2E2E", foreground="#E0E0E0", font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#FFFFFF")
        self.style.configure("TButton", background="#4A4A4A", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"), borderwidth=0)
        self.style.map("TButton", background=[('active', '#6A6A6A')])
        self.style.configure("TCheckbutton", background="#2E2E2E", foreground="#E0E0E0", font=("Segoe UI", 11))
        self.style.map("TCheckbutton",
                       background=[('active', '#3E3E3E')],
                       indicatorcolor=[('selected', '#007ACC'), ('!selected', '#555555')],
                       indicatorbackground=[('selected', '#007ACC'), ('!selected', '#555555')])
        self.style.configure("Vertical.TScrollbar", background="#4A4A4A", troughcolor="#2E2E2E")

    def create_main_widgets(self):
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=5)
        
        title_label = ttk.Label(header_frame, text="GERENCIADOR DE ATIVIDADES", style="Header.TLabel")
        title_label.pack(side=tk.LEFT)

        menu_button = ttk.Button(header_frame, text="☰ Menu", command=self.open_menu)
        menu_button.pack(side=tk.RIGHT)

        self.study_mode_var = tk.BooleanVar(value=False)
        study_button = ttk.Checkbutton(self.main_frame, text="Modo Estudo/Trabalho", 
                                       variable=self.study_mode_var, command=self.toggle_study_mode)
        study_button.pack(anchor=tk.W, pady=5)
        
        # --- Frame Principal de Tarefas (agora um container) ---
        tasks_container_frame = ttk.Frame(self.main_frame)
        tasks_container_frame.pack(fill=tk.BOTH, expand=True)

        # --- Frame de Tarefas de Rotina (Esquerda) ---
        routine_frame = ttk.Frame(tasks_container_frame)
        routine_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        task_header_frame = ttk.Frame(routine_frame)
        task_header_frame.pack(fill=tk.X, pady=(10, 2))
        ttk.Label(task_header_frame, text="Tarefas de Rotina:", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        canvas_frame = ttk.Frame(routine_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.task_canvas = tk.Canvas(canvas_frame, bg="#2E2E2E", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.task_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.task_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.task_canvas.configure(
                scrollregion=self.task_canvas.bbox("all")
            )
        )

        self.task_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.task_canvas.configure(yscrollcommand=scrollbar.set)

        self.task_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.task_widgets = {}

        # --- Frame de Tarefas Temporárias (Direita) ---
        self.temp_task_frame = ttk.Frame(tasks_container_frame)
        # self.temp_task_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0)) # Será ativado pelo menu

        temp_header_frame = ttk.Frame(self.temp_task_frame)
        temp_header_frame.pack(fill=tk.X, pady=(10, 2))
        ttk.Label(temp_header_frame, text="Tarefas Temporárias:", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        
        ttk.Button(temp_header_frame, text="+ Tarefa Temporária", command=self.add_temp_task_input).pack(anchor=tk.W, pady=5)

        temp_canvas_frame = ttk.Frame(self.temp_task_frame)
        temp_canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.temp_task_canvas = tk.Canvas(temp_canvas_frame, bg="#2E2E2E", highlightthickness=0)
        temp_scrollbar = ttk.Scrollbar(temp_canvas_frame, orient="vertical", command=self.temp_task_canvas.yview)
        self.temp_scrollable_frame = ttk.Frame(self.temp_task_canvas)

        self.temp_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.temp_task_canvas.configure(
                scrollregion=self.temp_task_canvas.bbox("all")
            )
        )

        self.temp_task_canvas.create_window((0, 0), window=self.temp_scrollable_frame, anchor="nw")
        self.temp_task_canvas.configure(yscrollcommand=temp_scrollbar.set)

        self.temp_task_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        temp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.temp_task_frame.pack_forget() # Esconde o frame por padrão

    def update_task_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.task_widgets = {}
        today_str = date.today().isoformat()
        
        # Recarrega tasks de HOJE
        self.tasks_for_today, _ = get_tasks_for_today()
        
        if not self.tasks_for_today:
            ttk.Label(self.scrollable_frame, text="Nenhuma tarefa de rotina para hoje.",
                      font=("Segoe UI", 10, "italic")).pack(pady=20, padx=10)
            # Não retorne, para que o usuário ainda possa ver o painel temp
        else:
            for task_id, task in self.tasks_for_today.items():
                task_frame = ttk.Frame(self.scrollable_frame, padding=5)
                task_frame.pack(fill=tk.X, pady=2)
                
                var = tk.BooleanVar()
                var.set(task.get('completed_on') == today_str)
                
                cb = ttk.Checkbutton(task_frame, text=task['name'], variable=var,
                                     command=lambda v=var, tid=task_id: self.on_task_check(v, tid))
                cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                if task.get('completed_on') == today_str:
                    cb.config(state=tk.DISABLED)
                    proof_text = "Concluído"
                    if task.get('proof_type') == 'text':
                        proof_text = f"Concluído: '{task.get('proof', '')[:20]}...'"
                    elif task.get('proof_type') == 'image':
                        proof_text = f"Concluído: (Imagem)"
                    
                    ttk.Label(task_frame, text=proof_text, font=("Segoe UI", 9, "italic"), foreground="#00A000").pack(side=tk.RIGHT)
                
                self.task_widgets[task_id] = {'var': var, 'cb': cb}

        # Atualiza a lista de tarefas temporárias também, se estiver visível
        if self.temp_task_frame.winfo_ismapped():
            self.update_temp_task_list()

    def on_task_check(self, var, task_id):
        if var.get(): 
            # Carrega a config completa para achar a task
            self.config_data = load_config_data()
            self.tasks = self.config_data.get('tasks', {})
            
            if task_id not in self.tasks:
                print(f"Erro: Task ID {task_id} não encontrado no config.")
                return

            task = self.tasks[task_id] # Acessa a task pelo ID
            proof_type, proof_data = self.get_proof(task['name'])
            
            if proof_data:
                task['completed_on'] = date.today().isoformat()
                task['proof'] = proof_data
                task['proof_type'] = proof_type
                
                self.config_data['tasks'] = self.tasks
                save_config_data(self.config_data)
                
                log_event("task_completed", f"{task_id}: {task['name']}")
                self.update_task_list() # Atualiza a lista da home
                
                # Verifica se TODAS as tarefas (rotina de HOJE e temp) foram completas
                tasks_for_today, temp_tasks = get_tasks_for_today()

                all_routine_done = True
                if not tasks_for_today:
                     all_routine_done = False 
                for t in tasks_for_today.values():
                    if not t.get('completed_on') == date.today().isoformat():
                        all_routine_done = False
                        break
                
                all_temp_done = not bool(temp_tasks)

                if all_routine_done and all_temp_done:
                    messagebox.showinfo("Parabéns!", "Todas as atividades de hoje foram concluídas! Os áudios estão desativados por hoje.")
                    # Atualiza o config para o daemon saber
                    self.config_data['last_completion_date'] = date.today().isoformat()
                    save_config_data(self.config_data)

            else:
                var.set(False)

    def get_proof(self, task_name):
        proof_win = tk.Toplevel(self.root)
        proof_win.title(f"Prova de Conclusão: {task_name}")
        center_window(proof_win, 400, 300)
        proof_win.transient(self.root)
        proof_win.grab_set()
        
        ttk.Label(proof_win, text="Descreva o que foi feito ou anexe uma imagem.").pack(pady=10)
        
        text_entry = tk.Text(proof_win, height=10, width=50)
        text_entry.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        result = {"type": None, "data": None}
        
        def save_text():
            data = text_entry.get("1.0", tk.END).strip()
            if data:
                result["type"] = "text"
                result["data"] = data
                proof_win.destroy()
            else:
                messagebox.showwarning("Prova Vazia", "Por favor, insira uma descrição como prova.", parent=proof_win)

        def save_image():
            filepath = filedialog.askopenfilename(
                title="Selecione a imagem de prova",
                filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp"), ("Todos os arquivos", "*.*")],
                parent=proof_win
            )
            if filepath:
                try:
                    filename = f"proof_{date.today().isoformat()}_{os.path.basename(filepath)}"
                    new_path = os.path.join(PROOFS_DIR, filename)
                    shutil.copy(filepath, new_path)
                    result["type"] = "image"
                    result["data"] = new_path 
                    proof_win.destroy()
                except Exception as e:
                    messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar a imagem: {e}", parent=proof_win)

        btn_frame = ttk.Frame(proof_win)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Salvar Texto", command=save_text).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Anexar Imagem", command=save_image).pack(side=tk.LEFT, padx=5)
        
        self.root.wait_window(proof_win)
        return result["type"], result["data"]

    def open_menu(self):
        menu_win = tk.Toplevel(self.root)
        menu_win.title("Menu")
        center_window(menu_win, 300, 280) # Aumentei a altura
        menu_win.transient(self.root)
        menu_win.grab_set()
        
        frame = ttk.Frame(menu_win, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(frame, text="Gerenciar Tarefas de Rotina", command=self.open_task_manager).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Adicionar Tarefa Temporária", command=lambda: [self.show_temp_task_frame(), menu_win.destroy()]).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Gerenciar Rejeições", command=self.open_rejection_manager).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Configurações (Velocidade)", command=self.open_settings).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Testar Áudio", command=self.test_audio).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Sair do App", command=self.quit_app).pack(fill=tk.X, pady=(15, 5))

    def test_audio(self):
        """Cria um sistema temporário só para testar o áudio."""
        try:
            temp_config = load_config_data()
            if not temp_config['rejections']:
                messagebox.showinfo("Teste de Áudio", "Nenhuma rejeição cadastrada para testar.")
                return
                
            rejection = random.choice(temp_config['rejections'])
            tts_speed = temp_config.get('tts_speed', 2)
            
            set_system_volume(80) # Chama a função global  
            
            # Re-usa a lógica de 'speak_text'
            if IS_WINDOWS:
                show_standalone_popup(self.root, rejection)   
                subprocess.run([
                    'powershell', '-Command',
                    f'Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$speak.Rate = {tts_speed}; $speak.Speak("{rejection}")'
                ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            elif IS_MACOS:
                rate = int(120 + (tts_speed * 15)) 
                subprocess.run(['say', '-r', str(rate), rejection], check=True)
            elif IS_LINUX:
                rate = int(140 + (tts_speed * 10))
                subprocess.run(['espeak', '-s', str(rate), rejection], check=True)
                
        except Exception as e:
            messagebox.showerror("Erro no Teste", f"Não foi possível tocar o áudio: {e}")

    def manage_list_items(self, title, item_list_key):
        manager_win = tk.Toplevel(self.root)
        manager_win.title(title)
        center_window(manager_win, 400, 350)
        manager_win.transient(self.root)
        manager_win.grab_set()
        
        # Carrega os dados mais recentes
        current_config = load_config_data()
        item_list = current_config.get(item_list_key, [])
        
        frame = ttk.Frame(manager_win, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, bg="#F0F0F0", selectbackground="#007ACC")
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        for item in item_list:
            listbox.insert(tk.END, item)
            
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        entry = ttk.Entry(btn_frame)
        entry.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 5))

        def add_item():
            new_item = entry.get()
            if new_item and new_item not in item_list:
                item_list.append(new_item)
                listbox.insert(tk.END, new_item)
                entry.delete(0, tk.END)
                current_config[item_list_key] = item_list
                save_config_data(current_config)

        def remove_item():
            selected_indices = listbox.curselection()
            if not selected_indices:
                return
            selected_item = listbox.get(selected_indices[0])
            if selected_item in item_list:
                item_list.remove(selected_item)
                listbox.delete(selected_indices[0])
                current_config[item_list_key] = item_list
                save_config_data(current_config)

        ttk.Button(btn_frame, text="Add", command=add_item).pack(side=tk.LEFT)
        ttk.Button(frame, text="Remover Selecionado", command=remove_item).pack(fill=tk.X, pady=5)

    def open_task_manager(self):
        manager_win = tk.Toplevel(self.root)
        manager_win.title("Gerenciar Tarefas de Rotina") # Título alterado
        center_window(manager_win, 500, 400) # Ligeiramente maior
        manager_win.transient(self.root)
        manager_win.grab_set()
        
        frame = ttk.Frame(manager_win, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # --- Treeview (Lista de Tarefas) ---
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        task_tree = ttk.Treeview(tree_frame, columns=("Nome", "Agenda"), show="headings", yscrollcommand=tree_scroll.set)
        task_tree.heading("Nome", text="Nome da Tarefa")
        task_tree.heading("Agenda", text="Agenda")
        task_tree.column("Nome", width=250)
        task_tree.column("Agenda", width=100)
        
        task_tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=task_tree.yview)

        # --- Botões ---
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        def populate_tree():
            # Limpa a árvore
            for item in task_tree.get_children():
                task_tree.delete(item)
                
            current_config = load_config_data()
            current_tasks = current_config.get('tasks', {})
            
            dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

            for task_id, task in current_tasks.items():
                
                # Só mostra tarefas 'em progresso'
                if task.get('status', 'em progresso') != 'em progresso':
                    continue
                    
                nome = task.get('name')
                agenda_tipo = task.get('schedule_type', 'daily')
                
                if agenda_tipo == 'daily':
                    agenda_str = "Todos os dias"
                else:
                    dias = task.get('schedule_days', [])
                    agenda_str = ", ".join([dias_semana[i] for i in dias])
                    if not agenda_str: agenda_str = "Nunca"
                
                # O ID é armazenado internamente (iid) para o botão de remover
                task_tree.insert("", tk.END, iid=task_id, values=(nome, agenda_str))

        def open_add_task_window():
            # Abre a janela de adicionar/editar
            self.show_add_task_window()
            # Atualiza a árvore depois que a janela de add fechar
            populate_tree() 
            # Atualiza a home
            self.update_task_list() 

        def end_task(): # Renomeado de remove_item
            selected_items = task_tree.selection()
            if not selected_items:
                return
            
            task_id = selected_items[0] # Pega o iid que salvamos
            
            current_config = load_config_data()
            current_tasks = current_config.get('tasks', {})
            
            if task_id in current_tasks:
                task_name = current_tasks[task_id]['name']
                if messagebox.askyesno("Confirmar Encerramento", 
                                        f"Tem certeza que quer 'Encerrar' a tarefa:\n\n{task_name}\n\n(Ela não será excluída, apenas ocultada)", 
                                        parent=manager_win):
                    
                    # Altera o status em vez de deletar
                    current_tasks[task_id]['status'] = 'encerrado' 
                    
                    current_config['tasks'] = current_tasks
                    save_config_data(current_config)
                    log_event("task_ended", f"{task_id}: {task_name}")
                    populate_tree() # Atualiza a lista do gerenciador
                    self.update_task_list() # Atualiza a lista da home

        ttk.Button(btn_frame, text="Adicionar Nova Tarefa", command=open_add_task_window).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Encerrar Atividade", command=end_task).pack(side=tk.RIGHT) # Texto e comando atualizados
        
        populate_tree() # Popula a árvore ao abrir
        
        manager_win.protocol("WM_DELETE_WINDOW", lambda: [manager_win.destroy(), self.update_task_list()])

    def open_rejection_manager(self):
        self.manage_list_items("Gerenciar Rejeições", "rejections")

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Configurações")
        settings_win.transient(self.root)
        settings_win.grab_set()
        
        current_config = load_config_data()
        
        frame = ttk.Frame(settings_win, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text="Velocidade Fala (TTS):").pack(side=tk.LEFT, padx=5)
        tts_var = tk.IntVar(value=current_config.get('tts_speed', 2))
        spin = ttk.Spinbox(row, from_=-5, to=10, textvariable=tts_var, width=5)
        spin.pack(side=tk.RIGHT, padx=5)

        def save_settings():
            current_config['tts_speed'] = tts_var.get()
            save_config_data(current_config)
            log_event("settings_updated", f"TTS Speed: {tts_var.get()}")
            settings_win.destroy()

        ttk.Button(frame, text="Salvar", command=save_settings).pack(pady=15)
        
        # Centraliza a janela após ela ser desenhada
        settings_win.update_idletasks()
        width = settings_win.winfo_reqwidth()
        height = settings_win.winfo_reqheight()
        center_window(settings_win, width, height)

    def toggle_study_mode(self):
        state = self.study_mode_var.get()
        
        # Salva o estado no config para o daemon ler
        self.config_data = load_config_data()
        self.config_data['study_mode'] = state
        save_config_data(self.config_data)
        
        if state:
            # --- INICIA MODO ESTUDO ---
            log_event("study_mode_on", "Modo Estudo/Trabalho ativado (via GUI).")
            
            # 1. Encontra e executa o script de modo estudo
            try:
                # Tenta encontrar o script 'study_mode.py' na mesma pasta do script principal
                script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "study_mode.py")
                if not os.path.exists(script_path):
                    script_path = "study_mode.py" # Tenta no CWD como fallback
                
                subprocess.Popen(["pythonw", script_path])
                
                # 2. Fecha o gerenciador
                self.quit_app() 
                
            except Exception as e:
                print(f"Erro ao iniciar o modo estudo: {e}")
                messagebox.showerror("Erro", "Não foi possível iniciar o 'study_mode.py'. Verifique se o arquivo está na pasta.")
                # Desmarca o botão se falhar
                self.study_mode_var.set(False)
                self.config_data['study_mode'] = False
                save_config_data(self.config_data)
        
        else:
            # --- DESATIVA MODO ESTUDO (se foi desmarcado na GUI) ---
            log_event("study_mode_off", "Modo Estudo/Trabalho desativado (via GUI).")
            
    def show_popup_message(self, title, message):
        messagebox.showinfo(title, message)

    def setup_tray_icon(self):
        if pystray is None or Image is None:
            print("pystray ou Pillow não encontrados. Ícone de bandeja desativado.")
            return

        image = Image.new('RGB', (64, 64), (0, 100, 200)) # Azul para o Gerenciador
        d = ImageDraw.Draw(image)
        d.text((10, 10), "IRS-M", fill=(255, 255, 255))
        
        menu = (
            item('Abrir Gerenciador', self.show_window, default=True),
            item('Sair', self.quit_app)
        )
        self.tray_icon = pystray.Icon(APP_NAME, image, f"{APP_NAME} (Gerenciador)", menu)
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self):
        self.root.withdraw()
        log_event("window_hide", "Gerenciador minimizado para bandeja.")

    def show_window(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.update_task_list() # Atualiza a lista ao mostrar
        self.root.after(100, lambda: self.root.attributes("-topmost", False))

    def quit_app(self):
        log_event("app_quit", "Gerenciador encerrado.")
        self.accountability_running = False # Para a thread de verificação
        
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.quit()
        sys.exit()

    def save_temp_tasks(self, tasks_list):
        """Salva a lista de tarefas temporárias no .txt."""
        try:
            with open(TEMP_TASKS_FILE, 'w', encoding='utf-8') as f:
                for task in tasks_list:
                    f.write(task + '\n')
        except Exception as e:
            print(f"Erro ao salvar tarefas temporárias: {e}")

    def show_temp_task_frame(self):
        """Expande a janela e mostra o frame de tarefas temporárias."""
        center_window(self.root, 900, 500)
        self.temp_task_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        self.update_temp_task_list()

    def update_temp_task_list(self):
        """Atualiza a lista de checkboxes de tarefas temporárias."""
        for widget in self.temp_scrollable_frame.winfo_children():
            widget.destroy()
        
        self.temp_task_widgets = {}
        self.temp_tasks = load_temp_tasks()

        if not self.temp_tasks:
            ttk.Label(self.temp_scrollable_frame, text="Nenhuma tarefa temporária.",
                        font=("Segoe UI", 10, "italic")).pack(pady=20, padx=10)
            return

        for task_name in self.temp_tasks:
            task_frame = ttk.Frame(self.temp_scrollable_frame, padding=5)
            task_frame.pack(fill=tk.X, pady=2)
            
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(task_frame, text=task_name, variable=var,
                                    command=lambda v=var, name=task_name: self.on_temp_task_check(name, v))
            cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.temp_task_widgets[task_name] = {'var': var, 'cb': cb}

    def add_temp_task_input(self):
        """Adiciona um campo de entrada para nova tarefa temp."""
        # Remove labels de "nenhuma tarefa" se existirem
        for widget in self.temp_scrollable_frame.winfo_children():
            if isinstance(widget, ttk.Label):
                widget.destroy()
                
        entry_frame = ttk.Frame(self.temp_scrollable_frame, padding=5)
        entry_frame.pack(fill=tk.X, pady=2)
        
        entry = ttk.Entry(entry_frame, font=("Segoe UI", 11))
        entry.pack(fill=tk.X, expand=True)
        entry.focus()
        
        entry.bind("<Return>", lambda event: self.save_new_temp_task(event, entry_frame))
        entry.bind("<Escape>", lambda event: entry_frame.destroy())

    def save_new_temp_task(self, event, entry_frame):
        """Salva a nova tarefa temporária do input."""
        entry = event.widget
        task_name = entry.get().strip()
        
        if task_name:
            tasks = load_temp_tasks()
            if task_name not in tasks:
                tasks.append(task_name)
                self.save_temp_tasks(tasks)
                log_event("temp_task_added", task_name)
                entry_frame.destroy()
                self.update_temp_task_list()
        else:
            entry_frame.destroy()

    def on_temp_task_check(self, task_name, var):
        """Chamado ao completar uma tarefa temporária."""
        if var.get():
            proof_type, proof_data = self.get_proof(task_name)
            
            if proof_data:
                # Tarefa concluída, removê-la do arquivo
                tasks = load_temp_tasks()
                if task_name in tasks:
                    tasks.remove(task_name)
                self.save_temp_tasks(tasks)
                
                log_event("temp_task_completed", task_name)
                self.update_temp_task_list() # Atualiza a lista da GUI
                
                # Verifica se TUDO foi concluído
                tasks_for_today, temp_tasks_remaining = get_tasks_for_today()
                
                all_routine_done = True
                if not tasks_for_today:
                    all_routine_done = False
                for t in tasks_for_today.values():
                    if not t.get('completed_on') == date.today().isoformat():
                        all_routine_done = False
                        break
                
                all_temp_done = not bool(temp_tasks_remaining) # Checa a lista que acabamos de carregar

                if all_routine_done and all_temp_done:
                    messagebox.showinfo("Parabéns!", "Todas as atividades de hoje foram concluídas! Os áudios estão desativados por hoje.")
                    self.config_data = load_config_data() # Recarrega
                    self.config_data['last_completion_date'] = date.today().isoformat()
                    save_config_data(self.config_data)
            else:
                var.set(False) # Prova foi cancelada, desmarca o checkbox

    def show_add_task_window(self):
        """Mostra o popup para adicionar uma nova tarefa de rotina."""
        
        add_win = tk.Toplevel(self.root)
        add_win.title("Adicionar Tarefa de Rotina")
        add_win.transient(self.root)
        add_win.grab_set()
        
        frame = ttk.Frame(add_win, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Nome da Tarefa ---
        name_frame = ttk.Frame(frame)
        name_frame.pack(fill=tk.X, pady=5)
        ttk.Label(name_frame, text="Nome da Tarefa:").pack(side=tk.LEFT, padx=(0, 10))
        name_entry = ttk.Entry(name_frame)
        name_entry.pack(fill=tk.X, expand=True)
        name_entry.focus()
        
        # --- Tipo de Agenda ---
        ttk.Label(frame, text="Agenda:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))
        
        schedule_type = tk.StringVar(value="daily")
        
        radio_daily = ttk.Radiobutton(frame, text="Todos os dias", variable=schedule_type, value="daily")
        radio_daily.pack(anchor=tk.W)
        
        radio_custom = ttk.Radiobutton(frame, text="Personalizar dias:", variable=schedule_type, value="custom")
        radio_custom.pack(anchor=tk.W)

        # --- Checkboxes dos Dias ---
        days_frame = ttk.Frame(frame, padding=(10, 5))
        days_frame.pack(fill=tk.X)
        
        days_vars = []
        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        for i, dia in enumerate(dias_semana):
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(days_frame, text=dia, variable=var, state="disabled")
            chk.pack(side=tk.LEFT, padx=5, expand=True)
            days_vars.append(var)
            
        def toggle_days_state(*args):
            if schedule_type.get() == "daily":
                for i, var in enumerate(days_vars):
                    var.set(True)
                    chk = days_frame.winfo_children()[i]
                    chk.config(state="disabled")
            else:
                for i, var in enumerate(days_vars):
                    # var.set(False) # Descomente se quiser que comecem desmarcados
                    chk = days_frame.winfo_children()[i]
                    chk.config(state="normal")
        
        schedule_type.trace_add("write", toggle_days_state)

        # --- Botão Salvar ---
        def save_new_task():
            task_name = name_entry.get().strip()
            if not task_name:
                messagebox.showerror("Erro", "O nome da tarefa não pode estar vazio.", parent=add_win)
                return

            sched_type = schedule_type.get()
            sched_days = []
            if sched_type == 'daily':
                sched_days = [0, 1, 2, 3, 4, 5, 6]
            else: # custom
                sched_days = [i for i, var in enumerate(days_vars) if var.get()]

            if sched_type == 'custom' and not sched_days:
                if not messagebox.askyesno("Confirmar", "Você não selecionou nenhum dia.\nA tarefa não aparecerá a menos que seja editada.\n\nSalvar mesmo assim?", parent=add_win):
                    return

            task_id = str(int(time.time()))
            new_task = {
                "name": task_name,
                "created_on": date.today().isoformat(),
                "completed_on": None,
                "proof": None,
                "schedule_type": sched_type,
                "schedule_days": sched_days,
                "status": "em progresso" # <<< ADICIONADO AQUI
            }
            
            current_config = load_config_data()
            current_config['tasks'][task_id] = new_task
            save_config_data(current_config)
            
            add_win.destroy()

        ttk.Button(frame, text="Salvar", command=save_new_task).pack(pady=(15, 0))
        
        # Centraliza a janela
        add_win.update_idletasks()
        width = add_win.winfo_reqwidth()
        height = add_win.winfo_reqheight()
        center_window(add_win, width, height)

        self.root.wait_window(add_win)

# ---
# INICIALIZAÇÃO E REGISTRO
# ---

def setup_persistence():
    """Registra o DAEMON (.bat) para iniciar com o Windows."""
    if not IS_WINDOWS:
        return True 

    try:
        # 1. Encontrar o caminho absoluto do script .py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Montar o caminho para o IRS.bat (que deve rodar o --daemon)
        bat_path = os.path.join(script_dir, "IRS_background.bat")
        
        if not os.path.exists(bat_path):
            messagebox.showwarning("Arquivo Ausente", "Aviso: IRS.bat não encontrado.\nA inicialização automática não será configurada.")
            return True 

        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = f"{APP_NAME}_Daemon"

        try:
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_READ) as reg_key:
                current_value, _ = winreg.QueryValueEx(reg_key, value_name)
                if current_value == bat_path:
                    return True # Já está configurado
        except FileNotFoundError:
            pass 

        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.SetValueEx(reg_key, value_name, 0, winreg.REG_SZ, bat_path)
            print(f"Sucesso: {bat_path} registrado para iniciar com o Windows.")
    
    except Exception as e:
        print(f"Erro ao configurar persistência com .bat: {e}")
    
    return True

def main():
    # Verifica se deve rodar como Daemon (background) ou GUI (gerenciador)
    if "--daemon" in sys.argv:
        run_daemon()
    else:
        # Roda como GUI
        if setup_persistence():
            root = tk.Tk()
            app = App(root)
            root.mainloop()
        else:
            sys.exit()

if __name__ == "__main__":
    main()