# daemon.py
import threading
import time
import random
import subprocess
import tkinter as tk
from datetime import date, timedelta, datetime
from core import (
    load_config_data, save_config_data, log_event, run_backup_system,
    set_system_volume, get_tasks_for_today, center_window,
    IS_WINDOWS, IS_MACOS, IS_LINUX, get_random_rejections
)

class IdentityRejectionSystem:
    def __init__(self, popup_callback_func):
        self.popup_callback = popup_callback_func
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
                if task.get('completed_on') != last_completion:
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
            elif IS_LINUX:
                subprocess.run(['espeak', '-s', str(int(140+(tts_speed*10))), text], check=True)
        except Exception as e:
            log_event("error_tts", str(e))

    def all_tasks_completed(self):
        tasks_for_today = get_tasks_for_today()
        # Se não tem tarefas para hoje, considera "completo" para não punir à toa? 
        # Ou considera incompleto? Vou manter a lógica anterior: se vazio, não pune.
        if not tasks_for_today: return True 
        
        all_routine_completed = True
        for task in tasks_for_today.values():
            if not task.get('completed_on') == date.today().isoformat():
                all_routine_completed = False
                break
        
        if all_routine_completed:
            today_str = date.today().isoformat()
            if self.config.get('last_completion_date') != today_str:
                self.config['last_completion_date'] = today_str
                log_event("all_tasks_completed", "Todas as rotinas concluídas.")
                self.save_config()
            return True
        return False

    def get_next_interval(self):
        days = self.config.get('consecutive_completion_days', 0)
        min_int = 1 + (days * 5)
        max_int = 3 + (days * 10)
        if min_int > max_int: min_int = max_int - 10
        return random.randint(min_int, max_int)

    def play_rejection_sequence(self, is_severe_mode):
        """Toca 3 rejeições diferentes. Se severe_mode=True, usa popup gigante."""
        rejections = get_random_rejections(3) # Pega 3 frases diferentes
        tts_speed = self.config.get('tts_speed', 3)
        
        log_event("rejection_sequence", f"Severe: {is_severe_mode} | {rejections}")
        
        for rejection in rejections:
            if not self.running: break
            
            # Recarrega para ver se o usuário ativou o modo estudo no meio do desespero
            self.reload_config()
            if self.config.get('study_mode', False) or self.all_tasks_completed():
                break

            set_system_volume(100)
            
            # Chama o popup apropriado
            self.popup_callback(rejection, is_severe=is_severe_mode)
            
            self.speak_text(rejection, tts_speed)
            time.sleep(0.5) 

    def run_rejection_loop(self):
        self.start_time = time.time() # Marca hora de início

        while self.running:
            try:
                self.reload_config()
                
                # Se estiver em modo estudo ou tudo completo, reseta o timer de severidade?
                # Não, o tempo corre. Se ele sair do modo estudo depois de 2h, já volta no modo hard.
                # Mas enquanto está pausado, ele não pune.
                
                if self.config.get('study_mode', False) or self.all_tasks_completed():
                    time.sleep(30)
                    continue

                interval = self.get_next_interval()
                #print(f"Próxima rejeição em {interval} min.")
                
                # Aguarda o intervalo (checa status a cada 10s)
                for i in range(interval * 60):
                    if not self.running: break
                    if i % 10 == 0:
                        self.reload_config()
                        if self.config.get('study_mode', False) or self.all_tasks_completed(): break
                    time.sleep(1)
                
                if self.running and not self.config.get('study_mode', False) and not self.all_tasks_completed():
                    
                    # Verifica se já passaram 15 minutos (900 segundos) desde o início do daemon
                    elapsed_time = time.time() - self.start_time
                    is_severe = elapsed_time > 900
                    
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
    """Exibe o popup. Se severe=True, cobre 80% da tela."""
    try:
        popup = tk.Toplevel(root)
        popup.title("IDENTIDADE REJEITADA")
        popup.attributes("-topmost", True)
        popup.overrideredirect(True) 
        popup.configure(bg="#1A0000")
        
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        if is_severe:
            # 80% da tela
            w = int(screen_width * 0.8)
            h = int(screen_height * 0.8)
            x = (screen_width - w) // 2
            y = (screen_height - h) // 2
            font_size = 40 # Fonte gigante
        else:
            # Popup "discreto" (padrão antigo)
            w, h = 500, 200
            x = (screen_width - w) // 2
            y = (screen_height - h) // 2
            font_size = 20

        popup.geometry(f"{w}x{h}+{x}+{y}")
        
        label = tk.Label(popup, text=text, font=("Impact", font_size), 
                         fg="#FF0000", bg="#1A0000", 
                         wraplength=w-40, justify=tk.CENTER)
        label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Fecha automaticamente após 8 segundos (tempo médio de leitura/fala)
        popup.after(8000, popup.destroy)
        
        # Força update para garantir que apareça na hora
        popup.update()
        
    except Exception as e:
        print(f"Erro popup: {e}")

def run_daemon_process():
    root = tk.Tk()
    root.withdraw() # Janela principal oculta
    
    # Callback agora aceita o argumento is_severe
    system = IdentityRejectionSystem(
        popup_callback_func=lambda text, is_severe=False: show_standalone_popup(root, text, is_severe)
    )
    system.start()
    try: root.mainloop()
    except KeyboardInterrupt: system.stop()