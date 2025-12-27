# daemon.py
import threading
import time
import random
import subprocess
import os
import tkinter as tk
from datetime import date, timedelta, datetime
from core import (
    load_config_data, save_config_data, log_event, run_backup_system,
    set_system_volume, get_tasks_for_today, center_window,
    IS_WINDOWS, IS_MACOS, IS_LINUX, get_random_rejections,
    verify_and_get_date
)

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
            return # Já está mostrando
            
        self.active_task_name = task_name
        self.window = tk.Toplevel(self.root)
        self.window.title("ALERTA DE DISCIPLINA")
        self.window.attributes("-topmost", True)
        self.window.overrideredirect(True) # Sem bordas
        self.window.configure(bg="#FFCC00") # Amarelo Alerta
        
        # Tamanho e posição (Canto superior esquerdo ou centro)
        w, h = 400, 260
        screen_w = self.window.winfo_screenwidth()
        x = screen_w - w - 20 # Canto direito
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
            self.shutdown_time = None # Reseta o timer de desligamento

    def check_shutdown(self):
        """Verifica se deve desligar o PC."""
        if not self.window: return # Sem alerta, sem perigo
        
        # Se ainda não definiu hora da morte, define agora (Random 0 a 15 min)
        if self.shutdown_time is None:
            delay = random.randint(120, 900) # Entre 2min e 15min
            self.shutdown_time = time.time() + delay
            print(f"DESLIGAMENTO AGENDADO PARA: {datetime.fromtimestamp(self.shutdown_time)}")
            
        # Tchau querido
        if time.time() > self.shutdown_time:
            log_event("system_shutdown", f"Usuário ignorou horário fixo da tarefa: {self.active_task_name}")
            if IS_WINDOWS:
                os.system("shutdown /s /t 0")
            else:
                os.system("shutdown -h now")

# -------------------------------------

class IdentityRejectionSystem:
    def __init__(self, popup_callback_func, yellow_manager):
        self.popup_callback = popup_callback_func
        self.yellow_manager = yellow_manager # Referência ao gerenciador amarelo
        self.config = load_config_data()
        threading.Thread(target=run_backup_system, daemon=True).start()
        self.tasks = self.config.get('tasks', {})
        self.running = False
        self.rejection_thread = None
        self.start_time = None 
        self.run_new_day_check()

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
                    log_event("reset_frequencia", "Falha dia anterior.")

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
                log_event("all_tasks_completed", "Todas as rotinas concluídas.")
                self.save_config()
            return True
        return False

    def check_fixed_schedule_violations(self):
        """Verifica se há tarefas de horário fixo atrasadas."""
        # Se estiver em modo estudo, perdoa tudo (Assume que está fazendo a tarefa certa)
        if self.config.get('study_mode', False):
            self.yellow_manager.root.after(0, self.yellow_manager.hide)
            return

        tasks_today = get_tasks_for_today()
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        
        violation_found = False
        target_task_name = ""
        target_task_time = ""

        for task in tasks_today.values():
            # Pula tarefas concluídas
            raw_comp = task.get('completed_on')
            if verify_and_get_date(raw_comp) == date.today().isoformat():
                continue

            fixed_time = task.get('fixed_start_time')
            if fixed_time:
                # Compara hora
                try:
                    ft_hour, ft_min = map(int, fixed_time.split(':'))
                    fixed_dt = now.replace(hour=ft_hour, minute=ft_min, second=0, microsecond=0)
                    
                    # Se agora é maior ou igual ao horário fixo (e não foi feito)
                    if now >= fixed_dt:
                        violation_found = True
                        target_task_name = task['name']
                        target_task_time = fixed_time
                        break # Pega a primeira violação
                except: pass

        if violation_found:
            # Invoca o alerta amarelo na thread principal
            self.yellow_manager.root.after(0, lambda: self.yellow_manager.show(target_task_name, target_task_time))
            # Checa roleta russa do desligamento
            self.yellow_manager.check_shutdown()
        else:
            # Tudo limpo, remove alerta
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
                
                # --- CHECAGEM DE HORÁRIO FIXO (NOVA) ---
                # Roda a cada ciclo do loop para ser responsivo
                self.check_fixed_schedule_violations()
                # ---------------------------------------

                if self.config.get('study_mode', False) or self.all_tasks_completed():
                    time.sleep(30)
                    continue

                interval = self.get_next_interval()
                # Loop de espera com check rápido
                for i in range(interval * 60):
                    if not self.running: break
                    
                    # Checa horário fixo a cada segundo também (para o desligamento ser preciso)
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
        self.running = True
        self.rejection_thread = threading.Thread(target=self.run_rejection_loop, daemon=True)
        self.rejection_thread.start()
        log_event("system_start", "Daemon iniciado.")
            
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
    
    # Inicializa o gerenciador amarelo na thread principal
    yellow_manager = YellowAlertManager(root)
    
    system = IdentityRejectionSystem(
        popup_callback_func=lambda text, is_severe=False: show_standalone_popup(root, text, is_severe),
        yellow_manager=yellow_manager
    )
    system.start()
    try: root.mainloop()
    except KeyboardInterrupt: system.stop()