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
    verify_and_get_date, SECURITY_LOG_FILE, verify_blockchain_integrity
)

LOG_FILE = SECURITY_LOG_FILE

# --- CHECKPOINT DE CONSCIÊNCIA ---
class FocusCheckSession:
    """Popup Bege Pastel: Iniciar ou Descansar?"""
    @staticmethod
    def show_check(root):
        # FASE 1: REFLEXÃO
        win = tk.Toplevel(root)
        win.title("CHECKPOINT DE ENERGIA")
        
        # Cores Pastel (Bege Calmante)
        bg_color = "#F5F5DC" # Bege clássico
        fg_color = "#4A3B2F" # Marrom café suave (contraste legível)
        btn_start_color = "#4CAF50" # (Verde Foco/Ação)
        btn_rest_color = "#6495ED"  # (CornflowerBlue - Azul Suave
        
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
        
        # Variável para rastrear a escolha do usuário
        decision = {"proceed": False}
        
        def on_start():
            decision["proceed"] = True
            win.destroy() # Fecha o Bege para abrir o Verde depois
            
        def on_rest():
            decision["proceed"] = False
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

        # --- FASE 2: HYPE (VERDE) ---
        # Só executa se o usuário escolheu iniciar
        if decision["proceed"]:
            FocusCheckSession.show_hype(root)

    @staticmethod
    def show_hype(root):
        win_hype = tk.Toplevel(root)
        win_hype.title("MODO DE AÇÃO")
        
        # Cores de Ação Pura
        bg_action = "#4CAF50" # Verde Vibrante
        fg_action = "#FFFFFF" # Branco
        
        win_hype.configure(bg=bg_action)
        win_hype.attributes("-fullscreen", True)
        win_hype.attributes("-topmost", True)
        
        frame = tk.Frame(win_hype, bg=bg_action)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Texto Gigante
        tk.Label(frame, text="ENTÃO VAMOS NESSA 🚀", font=("Impact", 45), 
                 bg=bg_action, fg=fg_action).pack(pady=(0, 40))
        
        def on_go():
            win_hype.destroy() # Libera o Daemon
            
        # Botão BOOOOOORA (Branco para contraste máximo no fundo verde)
        tk.Button(frame, text="BOOOOOORA!", font=("Segoe UI", 20, "bold"),
                  bg="#FFFFFF", fg="#2E7D32", relief=tk.FLAT, 
                  padx=50, pady=20, cursor="hand2",
                  command=on_go).pack()
                  
        win_hype.grab_set()
        root.wait_window(win_hype) # Trava aqui até o BOORA

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
        w, h = 550, 370
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        
        frame = tk.Frame(win, bg=bg_color, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="SE SENTIU ESPERTO?", font=("Impact", 18), 
                 bg=bg_color, fg="#DA70D6").pack(pady=(0, 15))
        
        msg = ("Detectamos um fechamento forçado do IRS. Possivelmente atráves do gerenciador de tarefas. "
               "Amigo, por que você fez isso?\n\n"

               "Se estiver muito difícil, basta excluir o programa.\n"
               "Ninguém vai te julgar. As pessoas vão te entender.\n"
               "Você pode voltar ao seu eu normal, que toooodos amam.\n\n"

               "Agora, se você deseja continuar. Não faça mais isso. Você está se auto-destruindo com essa atitude.\n"
               "Abra o programa e faça logo o que tem que ser feito.")
        
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
            if self.config.get('study_mode', False): 
                return
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
            
    # No daemon.py (dentro da classe IdentityRejectionSystem)

    def run_new_day_check(self):
        """
        Verificação Robusta: Só cobra o que estava agendado para ONTEM.
        Ignora tarefas de outros dias e tarefas arquivadas.
        """
        today_str = date.today().isoformat()
        yesterday_date_obj = date.today() - timedelta(days=1)
        yesterday_str = yesterday_date_obj.isoformat()
        yesterday_weekday = yesterday_date_obj.weekday() # 0=Seg, 6=Dom
        
        # 1. Manutenção Econômica
        self.process_economy_daily_check()
        
        econ = self.config.get('economy', {})
        last_rewarded = econ.get('last_rewarded_date')
        
        # --- VERIFICAÇÃO DE CONTINUIDADE (CORRIGIDA) ---
        
        all_tasks_ok = True
        tasks_checked_count = 0
        
        if not self.tasks: 
            # Se não tem tarefas ativas, não consideramos falha, mas também não ganha streak
            all_tasks_ok = False 
        
        for task in self.tasks.values():
            # A. Ignora tarefas Arquivadas
            if task.get('status') == 'encerrado':
                continue

            # B. Verifica se a tarefa era OBRIGATÓRIA ONTEM
            sched_type = task.get('schedule_type', 'daily')
            is_required_yesterday = False
            
            if sched_type == 'daily':
                is_required_yesterday = True
            elif sched_type == 'custom':
                if yesterday_weekday in task.get('schedule_days', []):
                    is_required_yesterday = True
            
            # Se não era pra fazer ontem, pula a validação
            if not is_required_yesterday:
                continue

            tasks_checked_count += 1
            
            # C. Validação da Data (Hash)
            raw = task.get('completed_on')
            v_date = verify_and_get_date(raw)
            
            # Se era obrigatória e (não foi feita ontem E nem adiantada hoje) -> FALHA
            if v_date != yesterday_str and v_date != today_str:
                all_tasks_ok = False
                # Log de debug para você saber exatamente qual tarefa falhou
                log_event("DEBUG_FAIL", f"Tarefa falhou: {task.get('name')}. Data encontrada: {v_date}", category="system")
                break
        
        # Se não tinha nenhuma tarefa agendada para ontem (ex: ontem foi Domingo de folga),
        # mantemos o streak vivo, mas não aumentamos o contador.
        day_was_empty = (tasks_checked_count == 0)

        # --- LÓGICA DE STREAK ---
        
        if last_rewarded != yesterday_str and last_rewarded != today_str:
            
            if all_tasks_ok and not day_was_empty:
                # SUCESSO
                self.config['consecutive_completion_days'] += 1
                
                was_flex_day = (econ.get('flex_active_date') == yesterday_str)
                
                if not was_flex_day:
                    econ['streak_progress'] = econ.get('streak_progress', 0) + 1
                    
                    if econ['streak_progress'] >= 10:
                        econ['streak_progress'] = 0 
                        if len(econ['flex_credits']) < 4:
                            expire_date = (date.today() + timedelta(days=90)).isoformat()
                            econ['flex_credits'].append({
                                "earned_date": today_str,
                                "expires_at": expire_date
                            })
                            log_event("CREDIT_EARNED", "Mérito: 10 dias perfeitos.", category="history")
                        else:
                            econ['pending_trade'] = True
                            log_event("TRADE_TRIGGER", "Inventário cheio.", category="history")
                
                econ['last_rewarded_date'] = yesterday_str
                log_event("STREAK_UPDATE", f"Streak: {self.config['consecutive_completion_days']}", category="history")
                
            elif not all_tasks_ok and not day_was_empty:
                # FALHA REAL (Tinha tarefa e não fez)
                if self.config.get('consecutive_completion_days', 0) > 0:
                    self.config['consecutive_completion_days'] = 0
                    econ['streak_progress'] = 0 
                    log_event("reset_frequencia", "Falha de continuidade detectada.", category="history")

        self.config['economy'] = econ

        # --- LIMPEZA DIÁRIA ---
        config_changed = False
        for task in self.tasks.values():
            raw = task.get('completed_on')
            v_date = verify_and_get_date(raw)
            
            # Limpa se for velha (ontem ou anterior). Mantém se for HOJE.
            if v_date == yesterday_str or (v_date != today_str and v_date is not None):
                task['completed_on'] = None
                task['proof'] = None
                config_changed = True
        
        if self.config.get('last_completion_date') == yesterday_str:
             self.config['last_completion_date'] = None
             config_changed = True

        if config_changed:
            self.save_config()
        else:
            save_config_data(self.config)

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
        # 1. Carrega dados atualizados
        self.reload_config()
        
        # 2. Grace Period (Ao ligar o PC)
        elapsed = time.time() - self.start_time
        remaining_grace = self.startup_grace_duration - elapsed
        
        if remaining_grace > 0:
            return int(remaining_grace)

        # 3. REJEIÇÕES
        return random.randint(1, 3) * 60

    def run_rejection_loop(self):
        self.start_time = time.time()
        
        # --- GRACE PERIOD ---
        # Define um tempo de 15 a 30 minutos de silêncio antes de começar a cobrar.
        self.startup_grace_duration = random.randint(15, 30) * 60
        log_event("daemon_started", f"Daemon Iniciado. Grace Period: {self.startup_grace_duration/60:.1f} minutos.", category="system")
        
        while self.running:
            try:
                self.reload_config()
                self.check_fixed_schedule_violations()

                if self.config.get('study_mode', False) or self.all_tasks_completed():
                    time.sleep(30)
                    continue

                # Pega o próximo intervalo (Grace Period, 1-3min ou 30min)
                interval = self.get_next_interval()
                
                # Loop de espera (dorme segundo a segundo para reagir rápido a mudanças)
                for i in range(interval):
                    if not self.running: break
                    
                    if i % 5 == 0: 
                        self.reload_config()
                        self.check_fixed_schedule_violations()
                        # Se entrar em modo estudo no meio do intervalo, para de esperar e reinicia
                        if self.config.get('study_mode', False) or self.all_tasks_completed(): break
                    
                    time.sleep(1)
                
                # Se acordou e ainda não tá trabalhando
                if self.running and not self.config.get('study_mode', False) and not self.all_tasks_completed():
                    elapsed_total = time.time() - self.start_time

                    is_severe = (elapsed_total > (self.startup_grace_duration + 1800))
                    self.play_rejection_sequence(is_severe_mode=is_severe)

            except Exception as e:
                print(f"Erro loop: {e}")
                time.sleep(60)

    def start(self):
        # 1. Auditoria de blockchain
        verify_blockchain_integrity("security", scope="full")
        verify_blockchain_integrity("history", scope="full")

        # 2. Checkpoint de Consciência
        self.check_initial_focus_popup()

        # 3. Inicia o loop de rejeição
        self.running = True
        self.rejection_thread = threading.Thread(target=self.run_rejection_loop, daemon=True)
        self.rejection_thread.start()
        
        log_event("system_start", "Daemon iniciado.", category="security")
        log_event("system_start", "Daemon iniciado.", category="system")
            
    def stop(self):
        self.running = False
        if self.rejection_thread: self.rejection_thread.join(timeout=2)

    def process_economy_daily_check(self):
        """Gerencia expiração, recarga mensal e limpeza."""
        econ = self.config.get('economy', {})
        today = date.today()
        today_str = today.isoformat()
        current_month = today.strftime("%Y-%m")
        changed = False

        # 1. Limpeza de Créditos Expirados
        valid_credits = []
        for c in econ.get('flex_credits', []):
            if c['expires_at'] >= today_str:
                valid_credits.append(c)
            else:
                log_event("CREDIT_EXPIRED", f"Crédito vencido em {c['expires_at']}", category="history")
                changed = True
        econ['flex_credits'] = valid_credits

        # 2. Recarga Mensal (Dia 1 ou primeiro boot do mês)
        if econ.get('last_month_reset') != current_month:
            # Lógica: Se tem < 2, completa até 2. Se tem >= 2, não dá nada.
            current_count = len(econ['flex_credits'])
            to_add = 0
            
            if current_count < 2:
                to_add = 2 - current_count
            
            if to_add > 0:
                # Validade de 90 dias
                expire_date = (today + timedelta(days=90)).isoformat()
                for _ in range(to_add):
                    econ['flex_credits'].append({
                        "earned_date": today_str,
                        "expires_at": expire_date
                    })
                log_event("MONTHLY_REFILL", f"Recarga mensal: +{to_add} créditos.", category="history")
                # Exibe notificação visual (opcional, pode ser via popup se quiser)
            
            econ['last_month_reset'] = current_month
            changed = True

        if changed:
            self.config['economy'] = econ
            self.save_config()

# --- SISTEMA DE POPUPS ---

def show_standalone_popup(root, text, is_severe=False):
    """Exibe o popup vermelho de rejeição com EGO ACTIVATION."""
    try:
        popup = tk.Toplevel(root)
        popup.title("IDENTIDADE REJEITADA")
        popup.attributes("-topmost", True)
        popup.overrideredirect(True) 
        popup.configure(bg="#1A0000")
        
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        if is_severe:
            # Modo Brutal (80% da tela)
            w, h = int(screen_width * 0.8), int(screen_height * 0.8)
            x, y = (screen_width - w) // 2, (screen_height - h) // 2
            font_size = 40
        else:
            # Modo Padrão
            w, h = 500, 200
            x, y = (screen_width - w) // 2, (screen_height - h) // 2
            font_size = 20

        popup.geometry(f"{w}x{h}+{x}+{y}")
        
        # Texto Principal (A Rejeição gritada)
        # Usei side=tk.TOP e expand=True para empurrar ele pro meio/topo
        label = tk.Label(popup, text=text, font=("Impact", font_size), 
                         fg="#FF0000", bg="#1A0000", wraplength=w-40, justify=tk.CENTER)
        label.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=(40, 20))
        
        # --- EGO ACTIVATION ---
        if is_severe:
            taunt_msg = ("Se estiver muito difícil... Exclua o programa.")
            
            # Fonte menor, itálico, cor cinza (fantasma)
            lbl_taunt = tk.Label(popup, text=taunt_msg, font=("Segoe UI", 12, "italic"), 
                                 fg="#555555", bg="#1A0000", justify=tk.CENTER)
            lbl_taunt.pack(side=tk.BOTTOM, pady=(0, 40))

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