#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MODO ESTUDO/TRABALHO (v2 - O Contrato)
- Interface de Configuração Inicial (Input + Tempo)
- Overlay Transparente com Fiscalização Aleatória
- Loop de Renovação Obrigatória
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
from bank_manager import get_balances, spend_minutes

# --- Configurações Básicas e Helpers ---

IS_WINDOWS = platform.system() == "Windows"
APP_NAME = "IdentidadeRejeitada"
APP_DIR_NAME = "IdentidadeRejeitadaApp"

def get_base_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()

APP_DATA_DIR = os.path.join(get_base_dir(), "config")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
LOG_FILE = os.path.join(APP_DATA_DIR, "logging.json")
def load_config_data():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {'study_mode': False, 'tts_speed': 3} 

def save_config_data(data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")

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
        print(f"Erro ao logar evento: {e}")

def return_to_main_app():
    try:
        config = load_config_data()
        config['study_mode'] = False
        save_config_data(config)
        log_event("study_mode_off", "Retornando ao app principal.")

        base_dir = get_base_dir()
        main_script = os.path.join(base_dir, "identidade_rejeitada.py")
        
        if not os.path.exists(main_script):
             main_script = "identidade_rejeitada.py"
        
        interpreter = sys.executable
        
        if IS_WINDOWS:
            # pythonw.exe para não abrir terminal preto
            if "python.exe" in interpreter:
                interpreter = interpreter.replace("python.exe", "pythonw.exe")
            subprocess.Popen([interpreter, main_script], cwd=base_dir)
        else:
            subprocess.Popen([interpreter, main_script], cwd=base_dir)
            
    except Exception as e:
        print(f"Erro fatal ao voltar: {e}")
    
    sys.exit()

# --- GERENCIAMENTO DE INTERVALOS DIÁRIOS ---

def get_daily_stats(config):
    """Retorna as estatísticas de hoje, resetando se mudou o dia."""
    today_str = datetime.now().date().isoformat()
    stats = config.get('daily_break_stats', {})
    
    # Se não existe ou é de outro dia, reseta
    if stats.get('date') != today_str:
        stats = {
            'date': today_str,
            'focus_minutes': 0,
            'used_10': 0,
            'used_20': 0
        }
    return stats

def save_focus_progress(minutes_done):
    """Soma o tempo trabalhado ao contador diário."""
    cfg = load_config_data()
    stats = get_daily_stats(cfg)
    
    stats['focus_minutes'] += minutes_done
    
    cfg['daily_break_stats'] = stats
    save_config_data(cfg)

def use_break_credit(break_type):
    """Consome um crédito de intervalo (10 ou 20)."""
    cfg = load_config_data()
    stats = get_daily_stats(cfg)
    
    if break_type == 10:
        stats['used_10'] += 1
    elif break_type == 20:
        stats['used_20'] += 1
        
    cfg['daily_break_stats'] = stats
    save_config_data(cfg)

# --- CLASSE DO SETUP (A Negociação) ---

class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Contrato de Silêncio")
        self.center_window(400, 380)
        self.root.config(bg="#1A1A1A")
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.root.attributes("-topmost", True)
        
        self.setup_ui()
        
    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", background="#1A1A1A", foreground="#FFFFFF", font=("Segoe UI", 10))
        style.configure("TButton", background="#333333", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TButton", background=[('active', '#555555')])
        
        frame = tk.Frame(self.root, bg="#1A1A1A", padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Logar evento de Setup
        log_event("setup", "Usuário iniciou o Setup.")

        # 1. Título
        lbl_title = tk.Label(frame, text="CONTRATO DE SILÊNCIO", font=("Impact", 18), bg="#1A1A1A", fg="#FF4444")
        lbl_title.pack(pady=(0, 20))

        # 2. Tempo
        ttk.Label(frame, text="Defina a sessão de trabalho/estudo?", background="#1A1A1A", foreground="#E0E0E0").pack(anchor=tk.W)
        self.combo_time = ttk.Combobox(frame, values=["30 Minutos", "60 Minutos"], state="readonly", font=("Segoe UI", 11))
        self.combo_time.current(0) # Default 30 min
        self.combo_time.pack(fill=tk.X, pady=(5, 15))

        # 3. Input Tarefa
        ttk.Label(frame, text="O que EXATAMENTE você vai fazer?", background="#1A1A1A", foreground="#E0E0E0").pack(anchor=tk.W)
        self.entry_task = tk.Entry(frame, font=("Segoe UI", 11), bg="#333333", fg="white", insertbackground="white")
        self.entry_task.pack(fill=tk.X, pady=(5, 20), ipady=3)
        self.entry_task.focus()
        log_event("entry_task", f"Usuário definiu a tarefa: {self.entry_task.get()}")

        # [NOVO] Botão de Lazer (Banco de Horas)
        # Só aparece se tiver saldo disponível suficiente (30m)
        locked, available = get_balances()
        if available >= 30: 
            # Calcula cor baseada no saldo (verde escuro = rico)
            btn_leisure = tk.Button(frame, text=f"Entrar em modo Standby ({available}min disponíveis)", 
                                    font=("Segoe UI", 10, "bold"), 
                                    bg="#2E7D32", fg="white", activebackground="#1B5E20", activeforeground="white",
                                    command=self.on_leisure_start, relief=tk.FLAT, cursor="hand2")
            btn_leisure.pack(fill=tk.X, pady=(10, 5), ipady=5)

        # --- ÁREA DE INTERVALOS (NOVO) ---
        
        # 1. Carrega dados
        config = load_config_data()
        stats = get_daily_stats(config)
        total_min = stats['focus_minutes']
        
        # 2. Cálculos de Direito
        # A cada 80min (1h20) ganha um de 10m
        earned_10 = total_min // 80
        avail_10 = max(0, earned_10 - stats['used_10'])
        next_10 = 80 - (total_min % 80)
        
        # A cada 180min (3h) ganha um de 20m
        earned_20 = total_min // 180
        avail_20 = max(0, earned_20 - stats['used_20'])
        next_20 = 180 - (total_min % 180)
        
        lbl_info = tk.Label(frame, text=f"Foco Hoje: {total_min} min", font=("Segoe UI", 8), bg="#1A1A1A", fg="#666")
        lbl_info.pack(pady=(10, 0))

        # BOTÃO INTERVALO 10 MIN
        txt_10 = f"☕ Intervalo 10m [{avail_10}]"
        if avail_10 == 0:
            txt_10 += f" (Faltam {next_10}min)"
            state_10 = tk.DISABLED
            bg_10 = "#333333"
            fg_10 = "#666666"
        else:
            state_10 = tk.NORMAL
            bg_10 = "#009688" # Teal
            fg_10 = "white"

        btn_break_10 = tk.Button(frame, text=txt_10, font=("Segoe UI", 9),
                                 bg=bg_10, fg=fg_10, state=state_10, relief=tk.FLAT,
                                 command=lambda: self.start_break_session(10))
        btn_break_10.pack(fill=tk.X, pady=2)

        # BOTÃO LANCHE 20 MIN
        txt_20 = f"🥪 Lanche 20m [{avail_20}]"
        if avail_20 == 0:
            txt_20 += f" (Faltam {next_20}min)"
            state_20 = tk.DISABLED
            bg_20 = "#333333"
            fg_20 = "#666666"
        else:
            state_20 = tk.NORMAL
            bg_20 = "#FF9800" # Laranja
            fg_20 = "black"

        btn_break_20 = tk.Button(frame, text=txt_20, font=("Segoe UI", 9),
                                 bg=bg_20, fg=fg_20, state=state_20, relief=tk.FLAT,
                                 command=lambda: self.start_break_session(20))
        btn_break_20.pack(fill=tk.X, pady=(2, 10))
        
        # ---------------------------------
        
        # 4. Botões
        btn_start = tk.Button(frame, text="ASSINAR E INICIAR", font=("Segoe UI", 11, "bold"), 
                              bg="#007ACC", fg="white", activebackground="#005A9E", activeforeground="white",
                              command=self.on_start, relief=tk.FLAT, cursor="hand2")        
        btn_start.pack(fill=tk.X, pady=5, ipady=5)

        '''
        btn_cancel = tk.Button(frame, text="Cancelar", font=("Segoe UI", 10), 
                               bg="#333333", fg="#AAAAAA", activebackground="#444444", activeforeground="white",
                               command=self.on_cancel, relief=tk.FLAT, cursor="hand2")
        btn_cancel.pack(fill=tk.X, pady=5)
        '''

    def _activate_study_mode_config(self):
        """Ativa o modo estudo no arquivo de configuração."""
        config = load_config_data()
        config['study_mode'] = True
        config['session_type'] = 'focus' 
        save_config_data(config)
        log_event("study_mode_on", "Modo Estudo/Trabalho ativado (via GUI).")

    def start_break_session(self, duration):
        """Inicia uma sessão de intervalo."""
        if not messagebox.askyesno("Intervalo", f"Iniciar pausa de {duration} minutos?\nO computador será liberado."):
            return
            
        use_break_credit(duration)
        
        # Configura sessão como 'break'
        config = load_config_data()
        config['study_mode'] = True
        config['session_type'] = f'break_{duration}' # break_10 ou break_20
        save_config_data(config)
        
        log_event("break_start", f"Intervalo de {duration}m iniciado.")
        
        self.root.destroy()
        start_overlay(duration, f"Intervalo ({duration} min)")

    def on_start(self):
        task = self.entry_task.get().strip()
        time_str = self.combo_time.get()
        minutes = 30 if "30" in time_str else 60

        num_checks = 4 if minutes == 60 else 3
        message = f"Nessa sessão você será perguntado {num_checks}x de forma aleatória se ainda está fazendo o que escreveu no contrato."
        messagebox.showinfo("Aviso Importante", message, parent=self.root)
        
        if not task:
            messagebox.showwarning("Sem Foco", "Escreva o que vai fazer para ativar o contrato.\nSem contrato, sem silêncio.", parent=self.root)
            return

        self._activate_study_mode_config()
        
        # Fecha esta janela e inicia o overlay
        self.root.destroy()
        start_overlay(minutes, task)

    def on_cancel(self):
        self.root.destroy()
        return_to_main_app()

    def run(self):
        self.root.mainloop()

    def on_leisure_start(self):
        time_str = self.combo_time.get()
        minutes = 30 if "30" in time_str else 60
        
        locked, available = get_balances()
        
        if available < minutes:
            messagebox.showerror("Saldo Insuficiente", f"Você quer {minutes}m, mas só tem {available}m desbloqueados.")
            return

        # Confirmação do Gasto
        if not messagebox.askyesno("Confirmar Standby", 
            f"Isso vai descontar {minutes} minutos do seu Banco de Horas.\n\n"
            "O IRS não vai te fiscalizar durante esse tempo.\n"
            "Deseja iniciar?"):
            return

        # Efetua o débito
        success, msg = spend_minutes(minutes)
        if not success:
            messagebox.showerror("Erro", msg)
            return

        # Ativa modo estudo, mas com flag de lazer
        config = load_config_data()
        config['study_mode'] = True
        config['session_type'] = 'standby'
        save_config_data(config)
        
        log_event("standby_mode_on", f"Sessão de Standby iniciada: -{minutes}m")
        
        self.root.destroy()
        # Inicia o overlay com título diferente
        start_overlay(minutes, "Sessão de Standby")

# --- CLASSE DO OVERLAY (A Execução) ---

class OverlayWindow:
    def __init__(self, minutes, task_name):
        self.root = tk.Tk()
        self.minutes = minutes
        self.task_name = task_name
        self.running = True
        
        # Configuração da Janela Transparente
        self.root.config(bg="#212121")
        window_width = 600
        window_height = 150
        screen_height = self.root.winfo_screenheight()
        
        x = 25
        y = screen_height - window_height - 55
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        
        if IS_WINDOWS:
            self.root.attributes('-transparentcolor', '#212121')
            self.root.attributes('-alpha', 0.6)
        
        # Configura o estilo do checkbox escuro
        self.setup_styles()
        self.create_widgets()
        
        # Loga o início
        log_event("study_mode_start", f"{minutes} min. Foco: {task_name}")
        
        # Inicia a Thread de Lógica (Timer + Popups)
        threading.Thread(target=self.run_logic, daemon=True).start()
        
        # Bind para mover
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)
        self.root.bind("<B1-Motion>", self.do_move)

        # Variável para rastrear o início real
        self.start_time = None

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam') # Clam permite mais customização de cor
        
        # Estilo para o Checkbox no fundo escuro
        style.configure("Overlay.TCheckbutton", 
                        background="#212121", 
                        foreground="#888888", 
                        font=("Segoe UI", 9),
                        indicatorcolor="#444444", # Cor da caixinha vazia
                        indicatorbackground="#212121")
        
        # Mapeamento para quando passar o mouse ou clicar
        style.map("Overlay.TCheckbutton",
                  background=[('active', '#212121')],
                  foreground=[('active', '#FFFFFF')], # Texto fica branco no hover
                  indicatorcolor=[('selected', '#FF0000'), ('active', '#666666')])

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg="#212121")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Label Vermelho
        lbl_mode = tk.Label(main_frame, text="CONTRATO ATIVO", 
                            font=("Impact", 28), bg="#212121", fg="#FF0000")
        lbl_mode.pack()
        
        # Label da Tarefa
        self.lbl_task = tk.Label(main_frame, text=f"Atividade: {self.task_name}", 
                                 font=("Segoe UI", 12, "bold"), bg="#212121", fg="#FFFFFF")
        self.lbl_task.pack(pady=(0, 10))

        # Checkbox de Desistir (Substituindo o Botão)
        self.giveup_var = tk.BooleanVar(value=False)
        self.chk_giveup = ttk.Checkbutton(main_frame, 
                                          text="Encerrar / Voltar ao App", 
                                          variable=self.giveup_var,
                                          command=self.on_checkbox_click,
                                          style="Overlay.TCheckbutton",
                                          cursor="hand2")
        self.chk_giveup.pack()

    def on_checkbox_click(self):
        """Chamado quando o checkbox é marcado."""
        if self.giveup_var.get():
            self.on_give_up()

    def run_logic(self):
        # 1. Carrega a configuração e define a variável CRÍTICA
        config = load_config_data()
        session_type = config.get('session_type', 'focus')
        is_standby = (session_type == 'standby')

        # 2. LÓGICA DE INTERVALO (Visual e Comportamento)
        if session_type and 'break' in session_type:
            try:
                self.lbl_task.config(text=f"RECARREGANDO ENERGIA... ({self.minutes}m)", fg="#03A9F4")
            except: pass
            
            total_seconds = self.minutes * 60
            self.start_time = time.time() # [ALTERADO] Usa self
            while self.running:
                elapsed = time.time() - self.start_time # [ALTERADO] Usa self
                if elapsed >= total_seconds:
                    self.running = False
                    self.root.after(0, self.time_expired)
                    break
                time.sleep(1)
            return

        total_seconds = self.minutes * 60
        
        # 3. LÓGICA DE STANDBY (Lazer)
        if is_standby:
            try:
                self.root.after(0, lambda: self.lbl_task.config(text="MODO STANDBY: AGUARDANDO RETORNO", fg="#4CAF50"))
            except: pass
            
            self.start_time = time.time() # [ALTERADO] Usa self
            while self.running:
                elapsed = time.time() - self.start_time # [ALTERADO] Usa self
                if elapsed >= total_seconds:
                    self.running = False
                    self.root.after(0, self.time_expired)
                    break
                time.sleep(1)
            return 

        # 4. LÓGICA PADRÃO (MODO ESTUDO COM FISCALIZAÇÃO)
        num_popups = 3 if self.minutes == 30 else 4
        slot_size = total_seconds // num_popups
        popup_times = []
        for i in range(num_popups):
            min_sec = i * slot_size
            max_sec = (i + 1) * slot_size - 60 
            if max_sec <= min_sec: max_sec = min_sec + 10
            trigger_at = random.randint(min_sec + 60, max_sec)
            popup_times.append(trigger_at)
        
        self.start_time = time.time() # [ALTERADO] Usa self
        while self.running:
            elapsed = time.time() - self.start_time # [ALTERADO] Usa self
            if elapsed >= total_seconds:
                self.running = False
                self.root.after(0, self.time_expired)
                break
            
            for pt in popup_times:
                if abs(elapsed - pt) < 1.5:
                    self.root.after(0, self.trigger_popup)
                    popup_times.remove(pt)
                    break
            time.sleep(1)

    def trigger_popup(self):
        """Dispara o popup de fiscalização."""
        if not self.running: return
        
        self.root.attributes("-topmost", True)
        # Toca um som de aviso do sistema (beep simples)
        try: self.root.bell() 
        except: pass

        response = messagebox.askyesno("FISCALIZAÇÃO", 
                                       f"Você ainda está focado em:\n\n'{self.task_name}'?\n\nSeja honesto.",
                                       parent=self.root)
        
        if not response:
            log_event("check_failed", "Usuário admitiu distração.")
            messagebox.showinfo("Falha", "Distração detectada.\nO Modo Estudo será cancelado.")
            self.on_give_up()
        else:
            log_event("check_passed", "Usuário confirmou foco.")

    def time_expired(self):
        """O tempo acabou. Fecha overlay e reabre setup."""
        # [NOVO] Se for sessão de trabalho, computa os créditos
        config = load_config_data()
        session_type = config.get('session_type', 'focus')
        
        if 'break' not in session_type and session_type != 'standby':
            save_focus_progress(self.minutes)
            log_event("progress_saved", f"+{self.minutes} min para intervalos.")

        messagebox.showinfo("TEMPO ESGOTADO", "O seu tempo de silêncio acabou.\nRenove o contrato ou volte ao gerenciador.")
        log_event("study_mode_expired", "Usuário atingiu o tempo definido.")
        self.root.destroy()
        # Reabre o Setup (Ciclo)
        setup = SetupWindow()
        setup.run()

    def on_give_up(self):
        # [NOVO] Calcula o tempo proporcional trabalhado antes de sair
        if self.start_time:
            elapsed_seconds = time.time() - self.start_time
            minutes_done = int(elapsed_seconds / 60)
            
            # Só salva se tiver feito pelo menos 1 minuto
            if minutes_done > 0:
                config = load_config_data()
                session_type = config.get('session_type', 'focus')
                
                # Garante que só ganha crédito se for sessão de foco (não break/standby)
                if 'break' not in session_type and session_type != 'standby':
                    save_focus_progress(minutes_done)
                    log_event("progress_saved_partial", f"+{minutes_done} min (Encerrado Manualmente).")

        self.running = False
        self.root.destroy()
        return_to_main_app()

    # Movimentação
    def start_move(self, event):
        self.root.x = event.x
        self.root.y = event.y
    def stop_move(self, event):
        self.root.x = None
        self.root.y = None
    def do_move(self, event):
        try:
            deltax = event.x - self.root.x
            deltay = event.y - self.root.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")
        except: pass

def start_overlay(minutes, task):
    app = OverlayWindow(minutes, task)
    app.root.mainloop()

# --- MAIN ---

if __name__ == "__main__":
    # Ao iniciar o script, abre a janela de negociação primeiro
    setup = SetupWindow()
    setup.run()