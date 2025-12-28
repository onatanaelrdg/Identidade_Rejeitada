# daemon.py
import threading
import time
import random
import subprocess
import os
import json
import tkinter as tk
from datetime import date, timedelta, datetime
from core import (
    load_config_data, save_config_data, log_event, run_backup_system,
    set_system_volume, get_tasks_for_today, center_window,
    IS_WINDOWS, IS_MACOS, IS_LINUX, get_random_rejections,
    verify_and_get_date, SECURITY_LOG_FILE
)

LOG_FILE = SECURITY_LOG_FILE

# --- CHECKPOINT DE CONSCIÊNCIA ---
class FocusCheckSession:
    """Popup Bege Pastel: Iniciar ou Descansar?"""
    @staticmethod
    def show_check(root):
        win = tk.Toplevel(root)
        win.title("CHECKPOINT DE ENERGIA")
        
        # Cores Pastel (Bege Calmante)
        bg_color = "#F5F5DC" # Bege clássico
        fg_color = "#4A3B2F" # Marrom café suave (contraste legível)
        btn_start_color = "#8FBC8F" # Verde pastel (DarkSeaGreen)
        btn_rest_color = "#CD5C5C"  # Vermelho pastel (IndianRed)
        
        win.configure(bg=bg_color)
        win.attributes("-fullscreen", True) # Tela Cheia
        win.attributes("-topmost", True)
        
        # Frame Centralizado
        frame = tk.Frame(win, bg=bg_color)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Texto
        tk.Label(frame, text="CÓRTEX PRÉ-FRONTAL", font=("Segoe UI", 24, "bold"), 
                 bg=bg_color, fg=fg_color).pack(pady=(0, 30))
        
        msg = ("Caso esteja cansado, de verdade, descanse longe do computador e celular.\n"
               "Depois volte aqui.")
        
        tk.Label(frame, text=msg, font=("Segoe UI", 16), 
                 bg=bg_color, fg=fg_color, justify=tk.CENTER).pack(pady=(0, 50))
        
        # Ações
        def on_start():
            win.destroy() # Libera o Daemon para iniciar
            
        def on_rest():
            log_event("system_shutdown", "Usuário optou por descansar no Checkpoint.", category="security")
            if IS_WINDOWS:
                os.system("shutdown /s /t 0")
            else:
                os.system("shutdown -h now")
            win.destroy() 

        btn_frame = tk.Frame(frame, bg=bg_color)
        btn_frame.pack()

        # Botão Iniciar
        tk.Button(btn_frame, text="ESTOU PRONTO PARA INICIAR", font=("Segoe UI", 14, "bold"),
                  bg=btn_start_color, fg="white", relief=tk.FLAT, padx=30, pady=15, cursor="hand2",
                  command=on_start).pack(side=tk.LEFT, padx=20)
                  
        # Botão Descansar
        tk.Button(btn_frame, text="DESCANSAR AGORA", font=("Segoe UI", 14, "bold"),
                  bg=btn_rest_color, fg="white", relief=tk.FLAT, padx=30, pady=15, cursor="hand2",
                  command=on_rest).pack(side=tk.LEFT, padx=20)
        
        # Trava tudo
        win.grab_set()
        root.wait_window(win)

# --- GERENCIADOR DE ALERTA AMARELO ---
class YellowAlertManager:
    """Gerencia a janela amarela e o desligamento."""
    def __init__(self, root):
        self.root = root
        self.window = None
        self.shutdown_time = None
        self.active_task_name = None
        
    def show(self, task_name, task_time):
        if self.window and self.window.winfo_exists():
            return 
            
        self.active_task_name = task_name
        self.window = tk.Toplevel(self.root)
        self.window.title("ALERTA DE DISCIPLINA")
        self.window.attributes("-topmost", True)
        self.window.overrideredirect(True) 
        self.window.configure(bg="#FFCC00") 
        
        w, h = 400, 260
        screen_w = self.window.winfo_screenwidth()
        x = screen_w - w - 20 
        y = 20
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        
        frame = tk.Frame(self.window, bg="#FFCC00", padx=15, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="⚠️ ATENÇÃO IMEDIATA", font=("Impact", 18), 
                 bg="#FFCC00", fg="#000000").pack(pady=(0, 10))
        
        msg = (f"Atividade: {task_name}\nHorário Marcado: {task_time}\n\n"
               f"Inicie o 'Modo Estudo' AGORA e coloque exatamente esse nome: \"{task_name}\" ou complete a atividade no gerenciador.\n\n"
               "Caso contrário, o computador será desligado a qualquer momento nos próximos 15 minutos.")
               
        tk.Label(frame, text=msg, font=("Segoe UI", 11, "bold"), 
                 bg="#FFCC00", fg="#000000", wraplength=360, justify=tk.LEFT).pack()
                 
    def hide(self):
        if self.window:
            try: self.window.destroy()
            except: pass
            self.window = None
            self.shutdown_time = None 

    def check_shutdown(self):
        if not self.window: return 
        
        if self.shutdown_time is None:
            delay = random.randint(120, 900) 
            self.shutdown_time = time.time() + delay
            print(f"DESLIGAMENTO AGENDADO PARA: {datetime.fromtimestamp(self.shutdown_time)}")
            
        if time.time() > self.shutdown_time:
            log_event("system_shutdown", f"Usuário ignorou horário fixo da tarefa: {self.active_task_name}", category="security")
            if IS_WINDOWS:
                os.system("shutdown /s /t 0")
            else:
                os.system("shutdown -h now")

# --- SESSÃO PSICOLÓGICA ---
class PsychologicalSession:
    """Popup roxo para sabotadores."""
    @staticmethod
    def show_punishment(root):
        win = tk.Toplevel(root)
        win.title("QUE PORRA QUE VOCÊ TÁ FAZENDO?")
        
        # Cor Roxa
        bg_color = "#4B0082" 
        fg_color = "#FFFFFF"
        
        win.configure(bg=bg_color)
        win.attributes("-topmost", True)
        
        # Centraliza
        w, h = 550, 320
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        
        frame = tk.Frame(win, bg=bg_color, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="SE SENTIU ESPERTO?", font=("Impact", 18), 
                 bg=bg_color, fg="#DA70D6").pack(pady=(0, 15))
        
        msg = ("Você pode se achar inteligente, achando que encontrou uma forma de burlar o IRS. "
               "Mas isso só mostra o quão patético você é.\n\n"
               "Não faça mais isso. Você está se auto-destruindo com essa atitude.\n\n"
               "Excluir o app ou matar o processo no gerenciador de tarefas... é a mesma coisa. "
               "Faça logo o que tem que ser feito.")
        
        tk.Label(frame, text=msg, font=("Segoe UI", 11), 
                 bg=bg_color, fg=fg_color, wraplength=500, justify=tk.CENTER).pack(pady=(0, 25))
        
        def on_close():
            # Marca como revisado ao clicar no botão
            log_event("SABOTAGE_REVIEWED", "Usuário recebeu revisão do DAEMON_DEAD.", category="security")
            win.destroy()

        tk.Button(frame, text="ENTENDI", font=("Segoe UI", 10, "bold"),
                  bg="#800080", fg="white", relief=tk.FLAT, padx=20, pady=10, cursor="hand2",
                  command=on_close).pack()
        
        # Trava o programa até o usuário aceitar a humilhação
        win.grab_set()
        root.wait_window(win)

# -------------------------------------

class IdentityRejectionSystem:
    def __init__(self, popup_callback_func, yellow_manager):
        self.popup_callback = popup_callback_func
        self.yellow_manager = yellow_manager 
        self.config = load_config_data()
        
        # --- VERIFICAÇÃO DE SABOTAGEM ---
        self.check_sabotage_on_startup()
        # --------------------------------

        threading.Thread(target=run_backup_system, daemon=True).start()
        self.tasks = self.config.get('tasks', {})
        self.running = False
        self.rejection_thread = None
        self.start_time = None 
        self.run_new_day_check()

    def check_sabotage_on_startup(self):
        """Verifica no JSON se houve DAEMON_DEAD hoje sem revisão posterior."""
        try:
            if not os.path.exists(LOG_FILE): return

            today_str = date.today().isoformat()
            
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            
            # Filtra logs de hoje
            today_logs = [l for l in logs if l.get('date') == today_str]
            
            last_dead_time = None
            last_reviewed_time = None
            
            for entry in today_logs:
                etype = entry.get('type')
                ts = entry.get('timestamp')
                
                if etype == "DAEMON_DEAD":
                    last_dead_time = ts
                elif etype == "SABOTAGE_REVIEWED":
                    last_reviewed_time = ts
            
            # Lógica: Se houve morte, e (não foi revisada OU a revisão é mais antiga que a morte)
            if last_dead_time:
                needs_punishment = False
                if not last_reviewed_time:
                    needs_punishment = True
                elif last_dead_time > last_reviewed_time:
                    needs_punishment = True
                
                if needs_punishment:
                    # Usa o root do gerenciador amarelo para mostrar o popup
                    PsychologicalSession.show_punishment(self.yellow_manager.root)

        except Exception as e:
            print(f"Erro ao checar sabotagem: {e}")

    def check_initial_focus_popup(self):
        """Exibe o popup de descanso se for a primeira vez rodando hoje."""
        try:
            # 1. Se já completou tudo, não perturba
            if self.all_tasks_completed(): return

            # 2. Verifica se o Daemon já rodou hoje (evita popup em restart do watchdog)
            already_started_today = False
            if os.path.exists(SECURITY_LOG_FILE):
                today_str = date.today().isoformat()
                with open(SECURITY_LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                    for entry in logs:
                        if entry.get('date') == today_str and entry.get('type') == 'system_start':
                            already_started_today = True
                            break
            
            # Se NÃO rodou hoje ainda (started = False) -> Mostra o Popup
            if not already_started_today:
                FocusCheckSession.show_check(self.yellow_manager.root)
                
        except Exception as e:
            log_event("focus_popup_error", f"Erro ao mostrar popup de descanso: {e}", category="system")

    def reload_config(self):
        self.config = load_config_data()
        self.tasks = self.config.get('tasks', {})

    def save_config(self):
        self.config['tasks'] = self.tasks
        save_config_data(self.config)
            
    def run_new_day_check(self):
        today_str = date.today().isoformat()
        last_completion = self.config.get('last_completion_date')
        
        if last_completion != today_str:
            all_tasks_completed_yesterday = True
            if not self.tasks: all_tasks_completed_yesterday = False
            for task in self.tasks.values():
                raw_comp = task.get('completed_on')
                valid_date = verify_and_get_date(raw_comp)
                if valid_date != last_completion:
                    all_tasks_completed_yesterday = False
                    break
            
            if last_completion:
                yesterday = (date.today() - timedelta(days=1)).isoformat()
                if last_completion == yesterday and all_tasks_completed_yesterday:
                    self.config['consecutive_completion_days'] += 1
                elif not all_tasks_completed_yesterday:
                    self.config['consecutive_completion_days'] = 0
                    log_event("reset_frequencia", "Falha dia anterior.", category="history")

            for task in self.tasks.values():
                task['completed_on'] = None
                task['proof'] = None
            
            self.config['study_mode'] = False
            self.config['last_completion_date'] = None
            self.save_config()

    def speak_text(self, text, tts_speed):
        try:
            if IS_WINDOWS:
                subprocess.run([
                    'powershell', '-Command',
                    f'Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate={tts_speed}; $s.Volume=100; $s.Speak("{text}")'
                ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            elif IS_MACOS:
                subprocess.run(['say', '-r', str(int(120+(tts_speed*15))), text], check=True)
        except: pass

    def all_tasks_completed(self):
        tasks_for_today = get_tasks_for_today()
        if not tasks_for_today: return True 
        all_routine_completed = True
        for task in tasks_for_today.values():
            raw_comp = task.get('completed_on')
            valid_date = verify_and_get_date(raw_comp)
            if valid_date != date.today().isoformat():
                all_routine_completed = False; break
        
        if all_routine_completed:
            today_str = date.today().isoformat()
            if self.config.get('last_completion_date') != today_str:
                self.config['last_completion_date'] = today_str
                log_event("all_tasks_completed", "Todas as rotinas concluídas.", category="history")
                self.save_config()
            return True
        return False

    def check_fixed_schedule_violations(self):
        """Verifica se há tarefas de horário fixo atrasadas."""
        if self.config.get('study_mode', False):
            self.yellow_manager.root.after(0, self.yellow_manager.hide)
            return

        tasks_today = get_tasks_for_today()
        now = datetime.now()
        
        violation_found = False
        target_task_name = ""
        target_task_time = ""

        for task in tasks_today.values():
            raw_comp = task.get('completed_on')
            if verify_and_get_date(raw_comp) == date.today().isoformat():
                continue

            fixed_time = task.get('fixed_start_time')
            if fixed_time:
                try:
                    ft_hour, ft_min = map(int, fixed_time.split(':'))
                    fixed_dt = now.replace(hour=ft_hour, minute=ft_min, second=0, microsecond=0)
                    if now >= fixed_dt:
                        violation_found = True
                        target_task_name = task['name']
                        target_task_time = fixed_time
                        break 
                except: pass

        if violation_found:
            self.yellow_manager.root.after(0, lambda: self.yellow_manager.show(target_task_name, target_task_time))
            self.yellow_manager.check_shutdown()
        else:
            self.yellow_manager.root.after(0, self.yellow_manager.hide)

    def play_rejection_sequence(self, is_severe_mode):
        rejections = get_random_rejections(3)
        tts_speed = self.config.get('tts_speed', 3)
        for rejection in rejections:
            if not self.running: break
            self.reload_config()
            if self.config.get('study_mode', False) or self.all_tasks_completed(): break
            set_system_volume(100)
            self.popup_callback(rejection, is_severe=is_severe_mode)
            self.speak_text(rejection, tts_speed)
            time.sleep(0.5) 

    def get_next_interval(self):
        days = self.config.get('consecutive_completion_days', 0)
        min_int = 1 + (days * 5)
        max_int = 3 + (days * 10)
        if min_int > max_int: min_int = max_int - 10
        return random.randint(min_int, max_int)

    def run_rejection_loop(self):
        self.start_time = time.time()
        while self.running:
            try:
                self.reload_config()
                
                self.check_fixed_schedule_violations()

                if self.config.get('study_mode', False) or self.all_tasks_completed():
                    time.sleep(30)
                    continue

                interval = self.get_next_interval()
                for i in range(interval * 60):
                    if not self.running: break
                    
                    if i % 5 == 0: 
                        self.reload_config()
                        self.check_fixed_schedule_violations()
                        if self.config.get('study_mode', False) or self.all_tasks_completed(): break
                    
                    time.sleep(1)
                
                if self.running and not self.config.get('study_mode', False) and not self.all_tasks_completed():
                    elapsed = time.time() - self.start_time
                    is_severe = elapsed > 900
                    self.play_rejection_sequence(is_severe_mode=is_severe)

            except Exception as e:
                print(f"Erro loop: {e}")
                time.sleep(60)

    def start(self):
        self.check_initial_focus_popup()

        self.running = True
        self.rejection_thread = threading.Thread(target=self.run_rejection_loop, daemon=True)
        self.rejection_thread.start()
        log_event("system_start", "Daemon iniciado.", category="security")
        log_event("system_start", "Daemon iniciado.", category="system")
            
    def stop(self):
        self.running = False
        if self.rejection_thread: self.rejection_thread.join(timeout=2)

# --- SISTEMA DE POPUPS ---

def show_standalone_popup(root, text, is_severe=False):
    """Exibe o popup vermelho de rejeição."""
    try:
        popup = tk.Toplevel(root)
        popup.title("IDENTIDADE REJEITADA")
        popup.attributes("-topmost", True)
        popup.overrideredirect(True) 
        popup.configure(bg="#1A0000")
        
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        if is_severe:
            w, h = int(screen_width * 0.8), int(screen_height * 0.8)
            x, y = (screen_width - w) // 2, (screen_height - h) // 2
            font_size = 40
        else:
            w, h = 500, 200
            x, y = (screen_width - w) // 2, (screen_height - h) // 2
            font_size = 20

        popup.geometry(f"{w}x{h}+{x}+{y}")
        label = tk.Label(popup, text=text, font=("Impact", font_size), fg="#FF0000", bg="#1A0000", wraplength=w-40, justify=tk.CENTER)
        label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        popup.after(8000, popup.destroy)
        popup.update()
    except: pass

def run_daemon_process():
    root = tk.Tk()
    root.withdraw() 
    
    yellow_manager = YellowAlertManager(root)
    
    system = IdentityRejectionSystem(
        popup_callback_func=lambda text, is_severe=False: show_standalone_popup(root, text, is_severe),
        yellow_manager=yellow_manager
    )
    system.start()
    try: root.mainloop()
    except KeyboardInterrupt: system.stop()