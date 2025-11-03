#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GERENCIADOR DE IDENTIDADE REJEITADA v2.0
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
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        VOLUME_CONTROL = cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        VOLUME_CONTROL = None
else:
    VOLUME_CONTROL = None

# --- Constantes ---
APP_NAME = "IdentidadeRejeitada"
APP_DIR_NAME = "IdentidadeRejeitadaApp"

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
Path(PROOFS_DIR).mkdir(parents=True, exist_ok=True)


class IdentityRejectionSystem:
    def __init__(self, app_instance):
        self.app = app_instance 
        self.config = {}
        self.tasks = {}
        self.load_config()
        self.running = False
        self.study_mode = False
        self.rejection_thread = None
        self.accountability_thread = None
        self.last_played = None
        self.reset_tasks_if_new_day()

    def log_event(self, event_type, details):
        try:
            logs = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            
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

    def load_config(self):
        default_config = {
            'rejections': [
                "Eu não quero emagrecer", "Eu não quero falar inglês fluentemente",
                "Eu não quero ser rico", "Eu não quero poder ajudar minha mãe",
                "Eu não quero liderar minha família", "Eu quero continuar sozinho pro resto da minha vida",
                "Eu não quero realizar meus sonhos", "Eu não quero ter disciplina",
                "Eu não quero ser respeitado", "Eu não quero ter controle da minha vida"
            ],
            'tasks': {},
            'tts_speed': 2,
            'consecutive_completion_days': 0,
            'last_completion_date': None
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                
                for key, value in default_config.items():
                    if key not in self.config:
                        self.config[key] = value
                        
            except json.JSONDecodeError:
                self.config = default_config
        else:
            self.config = default_config
            
        self.tasks = self.config.get('tasks', {})
        self.save_config()

    def save_config(self):
        self.config['tasks'] = self.tasks
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar config: {e}")
            
    def reset_tasks_if_new_day(self):
        today_str = date.today().isoformat()
        last_completion = self.config.get('last_completion_date')
        
        if last_completion != today_str:
            all_tasks_completed_yesterday = True
            if not self.tasks:
                all_tasks_completed_yesterday = False
                
            for task_id, task in self.tasks.items():
                if not task.get('completed_on'):
                    all_tasks_completed_yesterday = False
                    break
                if task.get('completed_on') != last_completion:
                    all_tasks_completed_yesterday = False
                    break
            
            if last_completion:
                yesterday = (date.today() - timedelta(days=1)).isoformat()
                if last_completion == yesterday and all_tasks_completed_yesterday:
                    self.config['consecutive_completion_days'] += 1
                elif not all_tasks_completed_yesterday and last_completion:
                    self.config['consecutive_completion_days'] = 0
                    self.log_event("reset_frequencia", "Atividades não concluídas no dia anterior.")

            for task_id, task in self.tasks.items():
                task['completed_on'] = None
                task['proof'] = None
            
            self.save_config()

    def set_volume(self, level_percent):
        if IS_WINDOWS and VOLUME_CONTROL:
            try:
                scalar_level = level_percent / 100.0
                VOLUME_CONTROL.SetMasterVolumeLevelScalar(scalar_level, None)
                self.log_event("volume_set", f"{level_percent}%")
            except Exception as e:
                print(f"Erro ao setar volume: {e}")
        else:
            print("Controle de volume não disponível neste SO.")

    def speak_text(self, text):
        speed = self.config.get('tts_speed', 2)
        try:
            if IS_WINDOWS:
                subprocess.run([
                    'powershell', '-Command',
                    f'Add-Type -AssemblyName System.Speech; '
                    f'$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$speak.Rate = {speed}; '
                    f'$speak.Volume = 100; '
                    f'$speak.Speak("{text}")'
                ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            elif IS_MACOS:
                rate = int(120 + (speed * 15)) 
                subprocess.run(['say', '-r', str(rate), text], check=True)
            
            elif IS_LINUX:
                rate = int(140 + (speed * 10))
                try:
                    subprocess.run(['espeak', '-s', str(rate), text], check=True)
                except FileNotFoundError:
                    print("Instale 'espeak' para TTS no Linux")
                    self.app.show_popup_message("TTS Error", "Instale 'espeak' para TTS no Linux.")

        except Exception as e:
            print(f"Erro ao reproduzir áudio: {e}")
            self.log_event("error_tts", str(e))

    def all_tasks_completed(self):
        if not self.tasks:
            return False 
        for task in self.tasks.values():
            if not task.get('completed_on') == date.today().isoformat():
                return False
        
        today_str = date.today().isoformat()
        if self.config.get('last_completion_date') != today_str:
            self.config['last_completion_date'] = today_str
            self.log_event("all_tasks_completed", "Todas as atividades do dia foram concluídas.")
            self.save_config()
            
        return True

    def get_next_interval(self):
        consecutive_days = self.config.get('consecutive_completion_days', 0)
        
        # Bônus de adaptação: a cada dia consecutivo, o intervalo aumenta
        # Aumenta 5 min no mínimo e 10 min no máximo por dia
        bonus_min = consecutive_days * 5
        bonus_max = consecutive_days * 10
        
        # Nova base de intervalo: 20 a 90 minutos
        base_min_int = 20
        base_max_int = 90
        
        min_int = base_min_int + bonus_min
        max_int = base_max_int + bonus_max
        
        # Garante que o mínimo nunca ultrapasse o máximo
        if min_int > max_int:
            min_int = max_int - 10 
        
        return random.randint(min_int, max_int)

    def play_rejection(self):
        if not self.config['rejections']:
            print("Sem rejeições configuradas.")
            return

        rejection = random.choice(self.config['rejections'])
        
        self.log_event("rejection_played", rejection)
        
        self.app.root.after(0, self.app.show_rejection_popup, rejection)
        
        self.set_volume(80)
        
        for _ in range(3):
            if not self.running: break
            self.speak_text(rejection)
            time.sleep(0.5) 
            
    def run_rejection_loop(self):
        while self.running:
            try:
                if self.study_mode or self.all_tasks_completed():
                    time.sleep(60) 
                    continue

                interval_minutes = self.get_next_interval()
                interval_seconds = interval_minutes * 60
                
                print(f"Próxima rejeição em {interval_minutes} minutos.")
                
                for _ in range(interval_seconds):
                    if not self.running or self.study_mode or self.all_tasks_completed():
                        break 
                    time.sleep(1)
                
                if self.running and not self.study_mode and not self.all_tasks_completed():
                    self.play_rejection()
            
            except Exception as e:
                print(f"Erro no loop de rejeição: {e}")
                self.log_event("error_loop", str(e))
                time.sleep(60)
            
            except Exception as e:
                print(f"Erro no loop de rejeição: {e}")
                self.log_event("error_loop", str(e))
                time.sleep(60)

    def run_accountability_check(self):
        while self.running and self.study_mode:
            interval = random.randint(15 * 60, 45 * 60)
            time.sleep(interval)
            
            if self.running and self.study_mode:
                self.app.root.after(0, self.app.ask_accountability)

    def start(self):
        self.running = True
        self.rejection_thread = threading.Thread(target=self.run_rejection_loop, daemon=True)
        self.rejection_thread.start()
        self.log_event("system_start", "Sistema iniciado.")
        
    def stop(self):
        self.running = False
        self.study_mode = False
        self.log_event("system_stop", "Sistema parado.")
        if self.rejection_thread:
            self.rejection_thread.join(timeout=2)
        if self.accountability_thread:
            self.accountability_thread.join(timeout=2)

    def toggle_study_mode(self, state):
        self.study_mode = state
        if state:
            self.log_event("study_mode_on", "Modo Estudo/Trabalho ativado.")
            self.accountability_thread = threading.Thread(target=self.run_accountability_check, daemon=True)
            self.accountability_thread.start()
        else:
            self.log_event("study_mode_off", "Modo Estudo/Trabalho desativado.")


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("600x500")
        
        self.system = IdentityRejectionSystem(self)
        
        self.setup_style()
        self.create_main_widgets()
        self.setup_tray_icon()
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.system.start()
        self.update_task_list()

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
        
        self.study_mode_overlay = tk.Label(self.root, text="MODO ESTUDO/TRABALHO",
                                           font=("Segoe UI", 14, "bold"),
                                           fg="#FFD700", bg="#1A1A1A",
                                           relief=tk.SOLID, borderwidth=1)

        task_header_frame = ttk.Frame(self.main_frame)
        task_header_frame.pack(fill=tk.X, pady=(10, 2))
        ttk.Label(task_header_frame, text="Atividades Diárias:", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        canvas_frame = ttk.Frame(self.main_frame)
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

    def update_task_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.task_widgets = {}
        today_str = date.today().isoformat()
        
        if not self.system.tasks:
            ttk.Label(self.scrollable_frame, text="Nenhuma atividade cadastrada.\nVá em Menu > Gerenciar Atividades.",
                      font=("Segoe UI", 10, "italic")).pack(pady=20, padx=10)
            return

        for task_id, task in self.system.tasks.items():
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

    def on_task_check(self, var, task_id):
        if var.get(): 
            task = self.system.tasks[task_id]
            proof_type, proof_data = self.get_proof(task['name'])
            
            if proof_data:
                task['completed_on'] = date.today().isoformat()
                task['proof'] = proof_data
                task['proof_type'] = proof_type
                self.system.save_config()
                self.system.log_event("task_completed", f"{task_id}: {task['name']}")
                self.update_task_list()
                
                if self.system.all_tasks_completed():
                    messagebox.showinfo("Parabéns!", "Todas as atividades de hoje foram concluídas! Os áudios estão desativados por hoje.")
            else:
                var.set(False) 
        else:
            pass

    def get_proof(self, task_name):
        proof_win = tk.Toplevel(self.root)
        proof_win.title(f"Prova de Conclusão: {task_name}")
        proof_win.geometry("400x300")
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
        menu_win.geometry("300x250")
        menu_win.transient(self.root)
        menu_win.grab_set()
        
        frame = ttk.Frame(menu_win, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(frame, text="Gerenciar Atividades", command=self.open_task_manager).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Gerenciar Rejeições", command=self.open_rejection_manager).pack(fill=tk.X, pady=5)
        #ttk.Button(frame, text="Configurações", command=self.open_settings).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Testar Áudio", command=self.system.play_rejection).pack(fill=tk.X, pady=5)
        ttk.Button(frame, text="Sair do App", command=self.quit_app).pack(fill=tk.X, pady=(15, 5))

    def manage_list_items(self, title, item_list_key):
        manager_win = tk.Toplevel(self.root)
        manager_win.title(title)
        manager_win.geometry("400x350")
        manager_win.transient(self.root)
        manager_win.grab_set()
        
        item_list = self.system.config.get(item_list_key, [])
        
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
                self.system.save_config()

        def remove_item():
            selected_indices = listbox.curselection()
            if not selected_indices:
                return
            selected_item = listbox.get(selected_indices[0])
            if selected_item in item_list:
                item_list.remove(selected_item)
                listbox.delete(selected_indices[0])
                self.system.save_config()

        ttk.Button(btn_frame, text="Add", command=add_item).pack(side=tk.LEFT)
        ttk.Button(frame, text="Remover Selecionado", command=remove_item).pack(fill=tk.X, pady=5)

    def open_task_manager(self):
        manager_win = tk.Toplevel(self.root)
        manager_win.title("Gerenciar Atividades")
        manager_win.geometry("400x350")
        manager_win.transient(self.root)
        manager_win.grab_set()
        
        frame = ttk.Frame(manager_win, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, bg="#F0F0F0", selectbackground="#007ACC")
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        for task_id, task in self.system.tasks.items():
            listbox.insert(tk.END, f"{task['name']} (ID: {task_id})")
            
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        entry = ttk.Entry(btn_frame)
        entry.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 5))

        def add_item():
            task_name = entry.get()
            if task_name:
                task_id = str(int(time.time())) 
                self.system.tasks[task_id] = {
                    "name": task_name,
                    "created_on": date.today().isoformat(),
                    "completed_on": None,
                    "proof": None
                }
                listbox.insert(tk.END, f"{task_name} (ID: {task_id})")
                entry.delete(0, tk.END)
                self.system.save_config()
                self.update_task_list()

        def remove_item():
            selected_indices = listbox.curselection()
            if not selected_indices:
                return
            selected_text = listbox.get(selected_indices[0])
            task_id = selected_text.split(" (ID: ")[1].replace(")", "")
            
            if task_id in self.system.tasks:
                del self.system.tasks[task_id]
                listbox.delete(selected_indices[0])
                self.system.save_config()
                self.update_task_list()

        ttk.Button(btn_frame, text="Add", command=add_item).pack(side=tk.LEFT)
        ttk.Button(frame, text="Remover Selecionada", command=remove_item).pack(fill=tk.X, pady=5)

    def open_rejection_manager(self):
        self.manage_list_items("Gerenciar Rejeições", "rejections")

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Configurações")
        settings_win.transient(self.root)
        settings_win.grab_set()
        
        frame = ttk.Frame(settings_win, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        def add_spinbox(label, key, from_, to):
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=label).pack(side=tk.LEFT, padx=5)
            var = tk.IntVar(value=self.system.config[key])
            spin = ttk.Spinbox(row, from_=from_, to=to, textvariable=var, width=5)
            spin.pack(side=tk.RIGHT, padx=5)
            return var

        tts_var = add_spinbox("Velocidade Fala (TTS):", "tts_speed", -5, 10)
        
        def save_settings():
            self.system.config['tts_speed'] = tts_var.get()
            self.system.save_config()
            self.system.log_event("settings_updated", self.system.config)
            settings_win.destroy()

        ttk.Button(frame, text="Salvar", command=save_settings).pack(pady=15)

    def toggle_study_mode(self):
        state = self.study_mode_var.get()
        self.system.toggle_study_mode(state)
        
        if state:
            self.study_mode_overlay.place(relx=0, rely=1.0, anchor='sw')
        else:
            self.study_mode_overlay.place_forget()
            
    def ask_accountability(self):
        self.root.deiconify() 
        answer = messagebox.askyesno("Verificação de Foco",
                                       "Você ainda está fazendo o que disse que faria?",
                                       parent=self.root)
        if not answer:
            self.study_mode_var.set(False)
            self.toggle_study_mode()
            self.system.log_event("accountability_check_failed", "Usuário respondeu 'Não'.")
        else:
            self.system.log_event("accountability_check_ok", "Usuário respondeu 'Sim'.")

    def show_rejection_popup(self, text):
        popup = tk.Toplevel(self.root)
        popup.title("IDENTIDADE REJEITADA")
        popup.geometry("500x200")
        popup.attributes("-topmost", True)
        popup.configure(bg="#1A0000")
        
        label = tk.Label(popup, text=text, font=("Impact", 20),
                         fg="#FF0000", bg="#1A0000",
                         wraplength=480, justify=tk.CENTER)
        label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.root.deiconify() 
        popup.after(8000, popup.destroy) 
        
    def show_popup_message(self, title, message):
        messagebox.showinfo(title, message)

    def setup_tray_icon(self):
        if pystray is None or Image is None:
            print("pystray ou Pillow não encontrados. Ícone de bandeja desativado.")
            return

        image = Image.new('RGB', (64, 64), (255, 0, 0))
        d = ImageDraw.Draw(image)
        d.text((10, 10), "IR", fill=(255, 255, 255))
        
        menu = (
            item('Abrir Gerenciador', self.show_window, default=True),
            item('Sair', self.quit_app)
        )
        self.tray_icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self):
        self.root.withdraw()
        self.system.log_event("window_hide", "Janela minimizada para bandeja.")

    def show_window(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False))

    def quit_app(self):
        self.system.log_event("app_quit", "Aplicação encerrada.")
        self.system.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.quit()
        sys.exit()

def setup_persistence():
    if not IS_WINDOWS:
        return True # Não é Windows, apenas continue

    try:
        # 1. Encontrar o caminho absoluto do script .py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. Montar o caminho para o IRS.bat
        bat_path = os.path.join(script_dir, "IRS.bat")
        
        if not os.path.exists(bat_path):
            print("Aviso: IRS.bat não encontrado. A inicialização automática não será configurada.")
            return True # .bat não existe, apenas rode o app

        # 3. Definir o caminho e nome da chave no registro
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = APP_NAME

        # 4. Verificar se a chave já está correta
        try:
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_READ) as reg_key:
                current_value, _ = winreg.QueryValueEx(reg_key, value_name)
                if current_value == bat_path:
                    return True # Já está configurado, apenas rode
        except FileNotFoundError:
            pass # Chave não existe, vamos criar

        # 5. Se não estiver correta ou não existir, escreve a chave
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.SetValueEx(reg_key, value_name, 0, winreg.REG_SZ, bat_path)
            print(f"Sucesso: {bat_path} registrado para iniciar com o Windows.")
    
    except Exception as e:
        print(f"Erro ao configurar persistência com .bat: {e}")
        # Se falhar, apenas rode o app
    
    return True

def main():
    if setup_persistence():
        root = tk.Tk()
        app = App(root)
        root.mainloop()
    else:
        sys.exit()

if __name__ == "__main__":
    main()