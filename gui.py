# gui.py
import os
import sys
import time
import shutil
import random
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import date

# Dependências Opcionais
try: from PIL import Image, ImageDraw
except ImportError: Image = None
try: import pystray; from pystray import MenuItem as item
except ImportError: pystray = None

from core import (
    APP_NAME, PROOFS_DIR, IS_WINDOWS, IS_MACOS, IS_LINUX,
    load_config_data, save_config_data, log_event, run_backup_system,
    set_system_volume, center_window, get_tasks_for_today,
    sign_date, verify_and_get_date
)
from daemon import show_standalone_popup
# --- NOVO: Integração com o Banco de Horas ---
from bank_manager import create_transaction, get_balances, get_history

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        center_window(self.root, 600, 500)
        self.config_data = load_config_data()
        self.tasks = self.config_data.get('tasks', {})
        self.setup_style()
        self.create_main_widgets()
        self.setup_tray_icon()
        threading.Thread(target=run_backup_system, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.update_task_list()
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
        self.style.map("TCheckbutton", background=[('active', '#3E3E3E')], indicatorcolor=[('selected', '#007ACC'), ('!selected', '#555555')])
        self.style.configure("Vertical.TScrollbar", background="#4A4A4A", troughcolor="#2E2E2E")

    def create_main_widgets(self):
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        header = ttk.Frame(self.main_frame)
        header.pack(fill=tk.X, pady=5)
        ttk.Label(header, text="GERENCIADOR DE ATIVIDADES", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="☰ Menu", command=self.open_menu).pack(side=tk.RIGHT)

        self.study_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.main_frame, text="Modo Estudo/Trabalho", variable=self.study_mode_var, command=self.toggle_study_mode).pack(anchor=tk.W, pady=5)
        
        routine_frame = ttk.Frame(self.main_frame)
        routine_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        ttk.Label(routine_frame, text="Tarefas de Rotina:", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        canvas_frame = ttk.Frame(routine_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.task_canvas = tk.Canvas(canvas_frame, bg="#2E2E2E", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.task_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.task_canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all")))
        self.task_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.task_canvas.configure(yscrollcommand=scrollbar.set)
        self.task_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_widgets = {}

    def update_task_list(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        self.task_widgets = {}
        today_str = date.today().isoformat()
        self.tasks_for_today = get_tasks_for_today()
        
        if not self.tasks_for_today:
            ttk.Label(self.scrollable_frame, text="Nenhuma tarefa de rotina para hoje.", font=("Segoe UI", 10, "italic")).pack(pady=20, padx=10)
            #ttk.Label(self.scrollable_frame, text="⏸️ Streak Pausado (Folga)", font=("Segoe UI", 9, "bold"), foreground="#00CCFF").pack(pady=5)
            
            # --- CORREÇÃO: SALVA O DIA COMO 'VISTO' ---
            # Se não tem nada pra fazer, atualizamos a data para hoje.
            # Assim, amanhã o sistema vê que não houve falha hoje e mantém o streak.
            if self.config_data.get('last_completion_date') != today_str:
                self.config_data['last_completion_date'] = today_str
                save_config_data(self.config_data)
                log_event("streak_paused", "Dia sem tarefas: Streak preservado.", category="system")
        else:
            for task_id, task in self.tasks_for_today.items():
                f = ttk.Frame(self.scrollable_frame, padding=5)
                f.pack(fill=tk.X, pady=2)
                
                raw_completed = task.get('completed_on')
                valid_date = verify_and_get_date(raw_completed) 
                is_completed = (valid_date == today_str)

                var = tk.BooleanVar(value=is_completed)
                cb = ttk.Checkbutton(f, text=task['name'], variable=var, command=lambda v=var, tid=task_id: self.on_task_check(v, tid))
                cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                if is_completed:
                    cb.config(state=tk.DISABLED)
                    ttk.Label(f, text="Concluído", font=("Segoe UI", 9, "italic"), foreground="#00A000").pack(side=tk.RIGHT)
                
                self.task_widgets[task_id] = {'var': var, 'cb': cb}

    def show_celebration_popup(self):
        win = tk.Toplevel(self.root)
        win.title("DIA CONCLUÍDO")
        center_window(win, 500, 250)
        win.transient(self.root)
        win.grab_set()
        
        bg_color = "#1B5E20"
        fg_color = "#FFFFFF"
        win.configure(bg=bg_color)
        
        config = load_config_data()
        phrases = config.get('celebrations', ["Parabéns pelo foco."])
        phrase = random.choice(phrases)
        
        frame = tk.Frame(win, bg=bg_color, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="✅ VOCÊ CONSEGUIU!", font=("Impact", 22), 
                 bg=bg_color, fg="#66BB6A").pack(pady=(0, 15))
        
        tk.Label(frame, text=phrase, font=("Segoe UI", 12), 
                 bg=bg_color, fg=fg_color, wraplength=450, justify=tk.CENTER).pack(pady=(0, 20))
        
        tk.Button(frame, text="FECHAR", font=("Segoe UI", 10, "bold"),
                  bg="#2E7D32", fg="white", relief=tk.FLAT, padx=20, pady=8, cursor="hand2",
                  command=win.destroy).pack()
    
    def on_task_check(self, var, task_id):
        if var.get(): 
            self.config_data = load_config_data()
            self.tasks = self.config_data.get('tasks', {})
            if task_id not in self.tasks: return
            task = self.tasks[task_id]

            ptype, pdata = self.get_proof(task)
            
            if pdata:
                signed_today = sign_date(date.today().isoformat())
                task['completed_on'] = signed_today
                
                task['proof'] = pdata; task['proof_type'] = ptype
                self.config_data['tasks'] = self.tasks
                save_config_data(self.config_data)
                log_event("task_completed", f"{task_id}: {task['name']}", category="history")
                self.update_task_list()
                
                tasks_for_today = get_tasks_for_today()
                all_done = True
                if not tasks_for_today: all_done = False
                
                for t in tasks_for_today.values():
                    v_date = verify_and_get_date(t.get('completed_on'))
                    if v_date != date.today().isoformat(): 
                        all_done = False; break
                
                if all_done:
                    self.config_data['last_completion_date'] = date.today().isoformat()
                    save_config_data(self.config_data)
                    self.show_celebration_popup()
            else: var.set(False)

    def get_proof(self, task):
        """
        Janela de prova com Validação Numérica e Integração com Banco de Horas.
        """
        task_name = task.get('name', 'Tarefa')
        
        # --- LÓGICA FLEX ---
        cfg = load_config_data()
        econ = cfg.get('economy', {})
        is_flex_day = (econ.get('flex_active_date') == date.today().isoformat())
        
        # Dados do Contrato Original
        raw_min_val = task.get('min_time_val', '0')
        raw_min_unit = task.get('min_time_unit', 'minutos')
        
        # 1. Converte o tempo mínimo original para minutos (base para o Banco)
        try:
            original_min_minutes = int(raw_min_val)
            if raw_min_unit == 'horas':
                original_min_minutes *= 60
        except:
            original_min_minutes = 0

        # 2. Define o tempo exigido para passar HOJE (base para Validação)
        effective_min_minutes = original_min_minutes
        
        if is_flex_day and original_min_minutes > 15:
            # No modo Flex, o mínimo para passar cai para 15 (ou mantém se for menor)
            effective_min_minutes = 15

        win = tk.Toplevel(self.root)
        win.title(f"Prova: {task_name}")
        center_window(win, 450, 480)
        win.transient(self.root)
        win.grab_set()
        
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        if is_flex_day:
            tk.Label(frame, text="⚡ MODO FLEX ATIVO: Meta reduzida para 15 min.", fg="#00CCFF", bg="#2E2E2E").pack(fill=tk.X, pady=(0, 10))

        # --- SEÇÃO DE INPUT (OBRIGATÓRIO SE TIVER MIN TIME) ---
        time_entry = None
        is_time_tracking = (original_min_minutes > 0)
        
        if is_time_tracking:
            val_frame = tk.LabelFrame(frame, text="Registro de Tempo", padx=10, pady=10)
            val_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Texto explicativo da meta
            meta_texto = f"{effective_min_minutes} minutos"
            ttk.Label(val_frame, text=f"Meta de Hoje: {meta_texto}", font=("Segoe UI", 10, "bold"), foreground="#FFCC00").pack(anchor=tk.W)
            
            row = tk.Frame(val_frame)
            row.pack(fill=tk.X, pady=(5, 0))
            ttk.Label(row, text="Tempo Realizado (min):").pack(side=tk.LEFT)
            
            # Campo Numérico
            time_entry = ttk.Entry(row, width=10)
            time_entry.pack(side=tk.LEFT, padx=5)
            
            ttk.Label(val_frame, text="(Ou digite 'Passe Livre')", font=("Segoe UI", 8, "italic")).pack(anchor=tk.W)

        # --- SEÇÃO DE PROVA ---
        ttk.Label(frame, text="Descreva o que foi feito:").pack(anchor=tk.W)
        entry = tk.Text(frame, height=8, width=50)
        entry.pack(pady=5, fill=tk.BOTH, expand=True)
        
        res = {"t": None, "d": None}
        
        # --- NOVO FLUXO: Separação de Validação e Commit ---
        
        def validate_inputs():
            """Valida os números e retorna o valor (int) ou 'PASS' ou False."""
            if not is_time_tracking: return 0 # 0 = OK, mas sem tempo a registrar
            
            user_input = time_entry.get().strip()
            
            # --- CHEQUE DE PASSE LIVRE ---
            if user_input.lower() == "passe livre":
                passes = econ.get('free_passes', 0)
                if passes > 0:
                    if messagebox.askyesno("Usar Passe", f"Você tem {passes} passes.\nDeseja gastar 1 para pular esta tarefa?"):
                        # Nota: Descontamos o passe aqui pois requer interação do usuário, 
                        # mas se ele cancelar a prova depois, perde o passe. É aceitável.
                        econ['free_passes'] -= 1
                        cfg['economy'] = econ
                        save_config_data(cfg)
                        log_event("PASS_USED", f"Usou passe na tarefa: {task_name}", category="history")
                        return "PASS"
                else:
                    messagebox.showerror("Impostor", "Você não tem Passes Livres.")
                    return False

            # Validação Numérica
            try:
                actual_minutes = int(user_input)
            except ValueError:
                messagebox.showerror("Erro", "Digite apenas números para os minutos (ex: 90).")
                return False
            
            # Validação: Cumpriu a meta de hoje?
            if actual_minutes < effective_min_minutes:
                messagebox.showerror("Falha de Disciplina", f"Você fez {actual_minutes}min. A meta de hoje era {effective_min_minutes}min.\nComplete o tempo antes de marcar.")
                return False
                
            return actual_minutes

        def commit_bank_transaction(validated_value):
            """Executa a transação no banco SOMENTE no final."""
            if validated_value == "PASS" or not is_time_tracking:
                return

            # validated_value é int aqui
            success, msg = create_transaction(task_name, original_min_minutes, validated_value)
            if success:
                messagebox.showinfo("Banco de Horas", msg)

        def save_txt():
            # 1. Valida Números primeiro
            val_result = validate_inputs()
            if val_result is False: return
            
            # 2. Valida Texto da Prova
            d = entry.get("1.0", tk.END).strip()
            
            if val_result == "PASS": 
                d = "CONCLUÍDO COM PASSE LIVRE 🎫"
            elif not d: # Se não for passe e não tiver texto
                messagebox.showwarning("Vazio", "Escreva algo.")
                return

            # 3. SE CHEGOU AQUI, ESTÁ TUDO CERTO. COMMIT NO BANCO.
            commit_bank_transaction(val_result)

            res["t"] = "text"; res["d"] = d
            win.destroy()

        def save_img():
            # 1. Valida Números primeiro
            val_result = validate_inputs()
            if val_result is False: return

            if val_result == "PASS":
                messagebox.showinfo("Info", "Passe Livre não requer imagem.")
                res["t"] = "text"; res["d"] = "CONCLUÍDO COM PASSE LIVRE 🎫"
                win.destroy()
                return

            # 2. Valida Imagem
            fp = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg")])
            if fp:
                try:
                    # 3. SE CHEGOU AQUI, ESTÁ TUDO CERTO. COMMIT NO BANCO.
                    commit_bank_transaction(val_result)
                    
                    np = os.path.join(PROOFS_DIR, f"proof_{date.today()}_{os.path.basename(fp)}")
                    shutil.copy(fp, np)
                    res["t"] = "image"; res["d"] = np
                    win.destroy()
                except: pass

        btn_frame = ttk.Frame(frame); btn_frame.pack(pady=10, fill=tk.X)
        ttk.Button(btn_frame, text="Salvar", command=save_txt).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(btn_frame, text="Anexar Imagem", command=save_img).pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        self.root.wait_window(win)
        return res["t"], res["d"]

    def open_menu(self):
        win = tk.Toplevel(self.root); win.title("Menu"); center_window(win, 300, 250)
        win.transient(self.root); win.grab_set()
        f = ttk.Frame(win, padding="15"); f.pack(fill=tk.BOTH, expand=True)
        ttk.Button(f, text="Gerenciar Tarefas", command=self.open_task_manager).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="💎 Loja da Disciplina", command=self.open_store).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="⏳ Banco de Horas", command=self.open_bank_statement).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Gerenciar Rejeições", command=lambda: self.manage_list("Rejeições", "rejections")).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Configurar Velocidade", command=self.open_settings).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Testar Áudio", command=self.test_audio).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Sair", command=self.quit_app).pack(fill=tk.X, pady=15)

    # 2. A Loja Visual
    def open_store(self):
        win = tk.Toplevel(self.root)
        win.title("Loja da Disciplina")
        center_window(win, 600, 550)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg="#1E1E1E")

        cfg = load_config_data()
        econ = cfg.get('economy', {})
        credits_list = econ.get('flex_credits', [])
        num_credits = len(credits_list)
        passes = econ.get('free_passes', 0)
        streak = econ.get('streak_progress', 0)
        pending_trade = econ.get('pending_trade', False)

        today_tasks = get_tasks_for_today()
        all_done_today = True
        if not today_tasks: 
            all_done_today = False
        else:
            for t in today_tasks.values():
                v_date = verify_and_get_date(t.get('completed_on'))
                if v_date != date.today().isoformat():
                    all_done_today = False; break
        
        last_comp = cfg.get('last_completion_date')
        today_str = date.today().isoformat()
        
        streak_display = f"{streak}/10"
        
        if all_done_today and last_comp == today_str:
             if econ.get('flex_active_date') != today_str:
                 streak_display = f"{streak} (+1 ⏳)/10"

        dash_frame = tk.Frame(win, bg="#1E1E1E", highlightbackground="#333333", highlightthickness=2)
        dash_frame.pack(pady=20, padx=40, fill=tk.X)

        tk.Label(dash_frame, text="RECURSOS DISPONÍVEIS", font=("Segoe UI", 10, "bold"), 
                 bg="#1E1E1E", fg="#666666", pady=10).pack(fill=tk.X)

        grid_frame = tk.Frame(dash_frame, bg="#1E1E1E")
        grid_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        grid_frame.columnconfigure(1, weight=1)

        def add_stat_row(row, icon, title, value, color):
            tk.Label(grid_frame, text=icon, font=("Segoe UI", 16), 
                     bg="#1E1E1E", fg=color).grid(row=row, column=0, padx=(0, 10), pady=5)
            tk.Label(grid_frame, text=title, font=("Segoe UI", 12), 
                     bg="#1E1E1E", fg="#E0E0E0").grid(row=row, column=1, sticky="w")
            tk.Label(grid_frame, text=value, font=("Consolas", 14, "bold"), 
                     bg="#1E1E1E", fg=color).grid(row=row, column=2, sticky="e")

        add_stat_row(0, "💎", "Créditos Flex", f"{num_credits}/4", "#00CCFF") 
        add_stat_row(1, "🎫", "Passes Livres", f"{passes}", "#FFD700")     
        add_stat_row(2, "🔥", "Streak Mérito", streak_display, "#FF4444")  

        if "(+1 ⏳)" in streak_display:
            lbl_info = tk.Label(win, text="* Progresso de hoje será confirmado amanhã.", 
                                font=("Segoe UI", 8, "italic"), bg="#1E1E1E", fg="#666666")
            lbl_info.pack(pady=(0, 10))

        frame_list = tk.Frame(win, bg="#1E1E1E")
        frame_list.pack(fill=tk.X, padx=40)
        
        tk.Label(frame_list, text="Validade dos Créditos:", font=("Segoe UI", 10, "bold"), 
                 bg="#1E1E1E", fg="#FFFFFF").pack(anchor=tk.W, pady=(0, 5))
        
        if not credits_list:
            tk.Label(frame_list, text="• Nenhum crédito disponível.", bg="#1E1E1E", fg="#666").pack(anchor=tk.W)
        else:
            today = date.today()
            for c in credits_list:
                exp = date.fromisoformat(c['expires_at'])
                days_left = (exp - today).days
                color = "#FF4444" if days_left < 7 else "#AAAAAA"
                txt = f"• 1 Crédito expira em {days_left} dias"
                row = tk.Frame(frame_list, bg="#1E1E1E")
                row.pack(fill=tk.X)
                tk.Label(row, text=txt, bg="#1E1E1E", fg=color, font=("Segoe UI", 10)).pack(side=tk.LEFT)
                tk.Label(row, text=f"({c['expires_at']})", bg="#1E1E1E", fg="#444", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=5)

        frame_actions = tk.Frame(win, bg="#1E1E1E", pady=20)
        frame_actions.pack(fill=tk.X, padx=40)

        today_str = date.today().isoformat()
        is_flex_active = (econ.get('flex_active_date') == today_str)
        
        def use_flex():
            if num_credits < 1:
                messagebox.showerror("Saldo Insuficiente", "Você precisa de pelo menos 1 💎.")
                return
            
            checkout = tk.Toplevel(win)
            checkout.title("CONFIRMAR TRANSAÇÃO")
            center_window(checkout, 450, 380)
            checkout.transient(win)
            checkout.grab_set()
            checkout.configure(bg="#151515") 
            
            main_frame = tk.Frame(checkout, bg="#1E1E1E", highlightbackground="#00CCFF", highlightthickness=2)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

            tk.Label(main_frame, text="💎", font=("Segoe UI", 40), 
                     bg="#1E1E1E", fg="#00CCFF").pack(pady=(20, 0))
            tk.Label(main_frame, text="ATIVAR MODO FLEX", font=("Impact", 18), 
                     bg="#1E1E1E", fg="#FFFFFF").pack(pady=(5, 15))

            rules_frame = tk.Frame(main_frame, bg="#252525", padx=15, pady=15)
            rules_frame.pack(fill=tk.X, padx=30)
            
            rules = [
                ("CUSTO:", "1 Crédito Flex", "#00CCFF"),
                ("EFEITO:", "Tempo mínimo reduzido p/ 15 min", "#FFFFFF"),
                ("CONSEQUÊNCIA:", "Pausa no Streak de Mérito", "#FF4444"),
                ("AVISO:", "Esta ação é irreversível", "#888888")
            ]
            
            for title, desc, color in rules:
                row = tk.Frame(rules_frame, bg="#252525")
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=title, font=("Segoe UI", 9, "bold"), width=13, anchor="w",
                         bg="#252525", fg="#AAAAAA").pack(side=tk.LEFT)
                tk.Label(row, text=desc, font=("Segoe UI", 9, "bold"), 
                         bg="#252525", fg=color).pack(side=tk.LEFT)

            result = {"confirm": False}

            def on_pay():
                result["confirm"] = True
                checkout.destroy()
            def on_cancel():
                checkout.destroy()

            btn_frame = tk.Frame(main_frame, bg="#1E1E1E", pady=20)
            btn_frame.pack(fill=tk.X, padx=30)

            btn_pay = tk.Button(btn_frame, text="PAGAR 1 💎", font=("Segoe UI", 11, "bold"),
                                bg="#00CCFF", fg="#000000", relief=tk.FLAT, cursor="hand2",
                                command=on_pay)
            btn_pay.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            btn_cancel = tk.Button(btn_frame, text="CANCELAR", font=("Segoe UI", 11),
                                   bg="#333333", fg="#FFFFFF", relief=tk.FLAT, cursor="hand2",
                                   command=on_cancel)
            btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))

            win.wait_window(checkout)
            
            if result["confirm"]:
                econ['flex_credits'].pop(0)
                econ['flex_active_date'] = today_str
                cfg['economy'] = econ
                save_config_data(cfg)
                log_event("FLEX_ACTIVATED", "Modo Flex ativado (-1 crédito).", category="history")
                win.destroy() 
                messagebox.showinfo("Transação Aprovada", "Modo Flex ATIVADO.\nRespire fundo e faça o mínimo hoje.")

        btn_flex = tk.Button(frame_actions, text="USAR FLEXIBILIDADE (-1 💎)", 
                             bg="#2E2E2E", fg="#00CCFF", font=("Segoe UI", 11, "bold"),
                             state=tk.DISABLED if (is_flex_active or num_credits == 0) else tk.NORMAL,
                             command=use_flex)
        btn_flex.pack(fill=tk.X, pady=5)
        
        if is_flex_active:
            tk.Label(frame_actions, text="⚡ MODO FLEX ATIVO HOJE", font=("Segoe UI", 10, "bold"), bg="#1E1E1E", fg="#00CCFF").pack(pady=5)

        if pending_trade and num_credits >= 4:
            def trade_pass():
                resp = messagebox.askyesno("OPORTUNIDADE LENDÁRIA", 
                    "Deseja trocar TODOS os seus 4 créditos + Bônus por 1 PASSE LIVRE?\n\n"
                    "O Passe Livre é eterno e completa qualquer dia instantaneamente.")
                if resp:
                    econ['flex_credits'] = []
                    econ['free_passes'] += 1
                    econ['pending_trade'] = False
                    cfg['economy'] = econ
                    save_config_data(cfg)
                    log_event("PASS_BOUGHT", "Trocou 4 créditos por 1 passe.", category="history")
                    win.destroy()
                    messagebox.showinfo("GLÓRIA", "Você adquiriu 1 PASSE LIVRE Eterno!")

            tk.Label(frame_actions, text="--- OFERTA ESPECIAL ---", bg="#1E1E1E", fg="#FFD700").pack(pady=(10, 0))
            btn_trade = tk.Button(frame_actions, text="🔥 RESGATAR PASSE LIVRE 🔥", 
                                  bg="#FFD700", fg="black", font=("Segoe UI", 11, "bold"),
                                  command=trade_pass)
            btn_trade.pack(fill=tk.X, pady=5)

    def open_bank_statement(self):
        win = tk.Toplevel(self.root)
        win.title("Extrato do Banco de Horas")
        center_window(win, 700, 500)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg="#1E1E1E")

        # 1. Obter Dados
        locked_min, available_min = get_balances()
        history = get_history()

        def fmt_time(minutes):
            h = minutes // 60
            m = minutes % 60
            return f"{h}h {m}m"

        # 2. Dashboard (Cabeçalho)
        dash_frame = tk.Frame(win, bg="#1E1E1E", pady=20)
        dash_frame.pack(fill=tk.X)

        # Container Centralizado para os Saldos
        stats_container = tk.Frame(dash_frame, bg="#1E1E1E")
        stats_container.pack()

        # Saldo Futuro (Bloqueado)
        f_locked = tk.Frame(stats_container, bg="#252525", padx=20, pady=10)
        f_locked.pack(side=tk.LEFT, padx=10)
        tk.Label(f_locked, text="A LIBERAR", font=("Segoe UI", 9, "bold"), bg="#252525", fg="#888888").pack()
        tk.Label(f_locked, text=fmt_time(locked_min), font=("Consolas", 18, "bold"), bg="#252525", fg="#FF6666").pack()
        tk.Label(f_locked, text="Investimento a longo prazo", font=("Segoe UI", 8), bg="#252525", fg="#555").pack()

        # Saldo Atual (Disponível)
        f_avail = tk.Frame(stats_container, bg="#252525", padx=20, pady=10)
        f_avail.pack(side=tk.LEFT, padx=10)
        tk.Label(f_avail, text="DISPONÍVEL HOJE", font=("Segoe UI", 9, "bold"), bg="#252525", fg="#888888").pack()
        tk.Label(f_avail, text=fmt_time(available_min), font=("Consolas", 18, "bold"), bg="#252525", fg="#4CAF50").pack()
        tk.Label(f_avail, text="Pode ser usado agora", font=("Segoe UI", 8), bg="#252525", fg="#555").pack()

        # 3. Tabela de Transações
        table_frame = ttk.Frame(win, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("Data", "Tarefa", "Ganho", "Restante", "Status/Liberação")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="none")
        
        # Configuração das Colunas
        tree.heading("Data", text="Data Origem")
        tree.heading("Tarefa", text="Fonte")
        tree.heading("Ganho", text="Depósito")
        tree.heading("Restante", text="Saldo")
        tree.heading("Status/Liberação", text="Disponibilidade")

        tree.column("Data", width=90, anchor="center")
        tree.column("Tarefa", width=200, anchor="w")
        tree.column("Ganho", width=80, anchor="center")
        tree.column("Restante", width=80, anchor="center")
        tree.column("Status/Liberação", width=120, anchor="center")

        # Scrollbar
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Tags de Cor
        tree.tag_configure('available', foreground='#4CAF50') # Verde
        tree.tag_configure('locked', foreground='#AAAAAA')    # Cinza/Neutro
        tree.tag_configure('depleted', foreground='#444444')  # Escuro (Gasto)

        # Popular Tabela
        today_str = date.today().isoformat()
        
        for tx in history:
            origin = tx.get('origin_date')
            task = tx.get('task_source')
            earned = tx.get('amount_earned')
            remain = tx.get('amount_remaining')
            unlock = tx.get('unlock_date')
            
            # Formata data para BR
            try:
                dt_obj = date.fromisoformat(origin)
                origin_fmt = dt_obj.strftime("%d/%m/%y")
                
                ul_obj = date.fromisoformat(unlock)
                unlock_fmt = ul_obj.strftime("%d/%m/%y")
            except:
                origin_fmt = origin
                unlock_fmt = unlock

            status_txt = unlock_fmt
            tag = "locked"

            if remain == 0:
                tag = "depleted"
                status_txt = "ESGOTADO"
            elif unlock <= today_str:
                tag = "available"
                status_txt = "LIBERADO"
            
            # Se for locked, mostra data de liberação com ícone de cadeado
            if tag == "locked":
                status_txt = f"🔒 {unlock_fmt}"

            vals = (origin_fmt, task, f"+{earned}min", f"{remain}min", status_txt)
            tree.insert("", tk.END, values=vals, tags=(tag,))

        # Botão Fechar
        tk.Button(win, text="FECHAR EXTRATO", font=("Segoe UI", 10), 
                  bg="#333333", fg="white", relief=tk.FLAT, command=win.destroy).pack(pady=10)

    def test_audio(self):
        cfg = load_config_data()
        if not cfg['rejections']: return
        rej = self.tasks.get('rejections', ["Teste"])[0] if not cfg['rejections'] else cfg['rejections'][0]
        set_system_volume(80)
        try:
            tts = cfg.get('tts_speed', 2)
            if IS_WINDOWS:
                subprocess.run(['powershell', '-Command', f'Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate={tts}; $s.Speak("Teste de áudio funcionando")'], creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass

    def manage_list(self, title, key):
        win = tk.Toplevel(self.root); win.title(title); center_window(win, 400, 350)
        win.transient(self.root); win.grab_set()
        cfg = load_config_data(); items = cfg.get(key, [])
        f = ttk.Frame(win, padding="10"); f.pack(fill=tk.BOTH, expand=True)
        lst = tk.Listbox(f); lst.pack(fill=tk.BOTH, expand=True)
        for i in items: lst.insert(tk.END, i)
        e = ttk.Entry(f); e.pack(fill=tk.X, pady=5)
        def add():
            v = e.get()
            if v: items.append(v); lst.insert(tk.END, v); e.delete(0, tk.END); cfg[key]=items; save_config_data(cfg)
        def rem():
            s = lst.curselection()
            if s: items.pop(s[0]); lst.delete(s[0]); cfg[key]=items; save_config_data(cfg)
        ttk.Button(f, text="Adicionar", command=add).pack(fill=tk.X)
        ttk.Button(f, text="Remover", command=rem).pack(fill=tk.X)

    def open_task_manager(self):
        manager_win = tk.Toplevel(self.root)
        manager_win.title("Tarefas de Rotina (Ativas)")
        center_window(manager_win, 600, 450)
        manager_win.transient(self.root)
        manager_win.grab_set()
        
        frame = ttk.Frame(manager_win, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Nome", "Agenda")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("Nome", text="Nome da Tarefa")
        tree.heading("Agenda", text="Frequência")
        tree.column("Nome", width=350)
        tree.column("Agenda", width=150)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def populate():
            for item in tree.get_children(): tree.delete(item)
            cfg = load_config_data()
            dias_sem = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            
            for tid, t in cfg.get('tasks', {}).items():
                if t.get('status', 'em progresso') == 'em progresso':
                    if t.get('schedule_type') == 'daily':
                        sched = "Todos os dias"
                    else:
                        ds = t.get('schedule_days', [])
                        sched = ", ".join([dias_sem[i] for i in ds]) if ds else "Personalizado"
                    tree.insert("", tk.END, iid=tid, values=(t['name'], sched))

        populate()

        btn_frame = ttk.Frame(manager_win, padding=(10, 10))
        btn_frame.pack(fill=tk.X)

        def edit_selected():
            sel = tree.selection()
            if not sel: return
            task_id = sel[0]
            self.open_task_editor(parent=manager_win, task_id=task_id, callback=lambda: [populate(), self.update_task_list()])

        def create_new():
            self.open_task_editor(parent=manager_win, task_id=None, callback=lambda: [populate(), self.update_task_list()])

        def open_archives():
            self.open_archived_manager(manager_win)
            populate()
            self.update_task_list()

        ttk.Button(btn_frame, text="Nova Tarefa", command=create_new).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Editar Selecionada", command=edit_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Ver Arquivados 📂", command=open_archives).pack(side=tk.RIGHT, padx=5)

    def open_archived_manager(self, parent):
        arch_win = tk.Toplevel(parent)
        arch_win.title("Arquivo Morto (Tarefas Encerradas)")
        center_window(arch_win, 500, 400)
        arch_win.transient(parent)
        arch_win.grab_set()

        frame = ttk.Frame(arch_win, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = ttk.Label(frame, text="Estas tarefas não aparecem na sua rotina diária.", font=("Segoe UI", 9, "italic"))
        lbl.pack(pady=(0, 10))

        tree = ttk.Treeview(frame, columns=("Nome",), show="headings", selectmode="browse")
        tree.heading("Nome", text="Nome da Tarefa Arquivada")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrol = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=scrol.set)
        scrol.pack(side=tk.RIGHT, fill=tk.Y)

        def populate_archived():
            for item in tree.get_children(): tree.delete(item)
            cfg = load_config_data()
            for tid, t in cfg.get('tasks', {}).items():
                if t.get('status') == 'encerrado':
                    tree.insert("", tk.END, iid=tid, values=(t['name'],))

        populate_archived()

        btn_frame = ttk.Frame(arch_win, padding=10)
        btn_frame.pack(fill=tk.X)

        def edit_restore():
            sel = tree.selection()
            if not sel: return
            self.open_task_editor(parent=arch_win, task_id=sel[0], callback=lambda: [populate_archived(), self.update_task_list()])

        ttk.Button(btn_frame, text="Editar / Restaurar", command=edit_restore).pack(fill=tk.X)

    def open_settings(self):
        win = tk.Toplevel(self.root); win.title("Config"); center_window(win, 300, 150)
        cfg = load_config_data()
        ttk.Label(win, text="Velocidade Fala:").pack()
        var = tk.IntVar(value=cfg.get('tts_speed', 2))
        ttk.Spinbox(win, from_=-5, to=10, textvariable=var).pack()
        def save(): cfg['tts_speed'] = var.get(); save_config_data(cfg); win.destroy()
        ttk.Button(win, text="Salvar", command=save).pack(pady=10)

    def toggle_study_mode(self):
        s = self.study_mode_var.get()
        self.config_data = load_config_data(); self.config_data['study_mode'] = s; save_config_data(self.config_data)
        if s:
            try:
                p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "study_mode.py")
                if not os.path.exists(p): p = "study_mode.py"
                subprocess.Popen(["pythonw", p]); self.quit_app()
            except: self.study_mode_var.set(False)

    def setup_tray_icon(self):
        if not pystray or not Image: return
        im = Image.new('RGB', (64, 64), (0, 100, 200)); d = ImageDraw.Draw(im); d.text((10, 10), "IRS", fill="white")
        self.tray = pystray.Icon(APP_NAME, im, "IRS", (item('Abrir', self.show_window, default=True), item('Sair', self.quit_app)))
        threading.Thread(target=self.tray.run, daemon=True).start()

    def hide_window(self): self.root.withdraw()
    def show_window(self): self.root.deiconify(); self.root.attributes("-topmost", True); self.update_task_list(); self.root.after(100, lambda: self.root.attributes("-topmost", False))
    def quit_app(self):
        if hasattr(self, 'tray'): self.tray.stop()
        self.root.quit(); sys.exit()

    def open_task_editor(self, parent, task_id=None, callback=None):
        is_edit = task_id is not None
        title = "Editar Tarefa" if is_edit else "Nova Tarefa"
        
        win = tk.Toplevel(parent)
        win.title(title)
        center_window(win, 450, 550) 
        win.transient(parent)
        win.grab_set()
        
        config = load_config_data()
        task_data = config['tasks'].get(task_id, {}) if is_edit else {}
        
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Nome da Tarefa:").pack(anchor=tk.W)
        name_entry = ttk.Entry(frame)
        name_entry.pack(fill=tk.X, pady=(0, 10))
        if is_edit: name_entry.insert(0, task_data.get('name', ''))
        else: name_entry.focus()

        ttk.Label(frame, text="Tempo Mínimo Diário:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(5, 0))
        time_frame = ttk.Frame(frame)
        time_frame.pack(fill=tk.X, pady=(0, 10))
        
        time_val = tk.StringVar(value=str(task_data.get('min_time_val', '')))
        time_unit = tk.StringVar(value=task_data.get('min_time_unit', 'minutos'))
        vcmd = (win.register(lambda P: P.isdigit() or P == ""), '%P')
        time_entry = ttk.Entry(time_frame, textvariable=time_val, validate="key", validatecommand=vcmd, width=10)
        time_entry.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(time_frame, text="Minutos", variable=time_unit, value="minutos").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(time_frame, text="Horas", variable=time_unit, value="horas").pack(side=tk.LEFT, padx=5)

        raw_last_set = task_data.get('min_time_last_set', None)
        valid_date_str = verify_and_get_date(raw_last_set)
        tampered = False
        if raw_last_set and valid_date_str is False:
            tampered = True
            valid_date_str = date.today().isoformat()
            messagebox.showwarning("⚠️ ALERTA", "Adulteração detectada. Trava reiniciada.", parent=win)
        if not valid_date_str: valid_date_str = date.today().isoformat()

        is_locked = False
        remaining = 0
        if is_edit:
            last_set_date = date.fromisoformat(valid_date_str)
            days_since_change = (date.today() - last_set_date).days
            if days_since_change < 7:
                is_locked = True
                remaining = 7 - days_since_change

        if is_locked:
            time_entry.configure(state='disabled')
            for child in time_frame.winfo_children():
                try: child.configure(state='disabled')
                except: pass
            lock_msg = f"🔒 Tempo travado por mais {remaining} dias"
            if tampered: lock_msg += " (PENALIDADE)"
            ttk.Label(frame, text=lock_msg, foreground="#FF4444", font=("Segoe UI", 8, "bold")).pack(anchor=tk.W, pady=(0, 10))

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(frame, text="Horário Fixo de Início (Opcional):", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, text="Formato HH:MM (Ex: 14:30). Deixe vazio se não usar.", font=("Segoe UI", 8), foreground="#888").pack(anchor=tk.W)
        
        fixed_time_var = tk.StringVar(value=task_data.get('fixed_start_time', ''))
        fixed_time_entry = ttk.Entry(frame, textvariable=fixed_time_var, width=10)
        fixed_time_entry.pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(frame, text="Frequência:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        sched_var = tk.StringVar(value=task_data.get('schedule_type', 'daily'))
        days_frame = ttk.Frame(frame, padding=(10, 5))
        dias_vars = []
        dias_nomes = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        def toggle_days(*args):
            state = "normal" if sched_var.get() == "custom" else "disabled"
            for w in days_frame.winfo_children(): w.configure(state=state)
        ttk.Radiobutton(frame, text="Todos os dias", variable=sched_var, value="daily", command=toggle_days).pack(anchor=tk.W)
        ttk.Radiobutton(frame, text="Personalizado:", variable=sched_var, value="custom", command=toggle_days).pack(anchor=tk.W)
        days_frame.pack(fill=tk.X)
        saved_days = task_data.get('schedule_days', [])
        for i, nome in enumerate(dias_nomes):
            is_checked = (i in saved_days) if is_edit and task_data.get('schedule_type') == 'custom' else True
            dv = tk.BooleanVar(value=is_checked)
            ttk.Checkbutton(days_frame, text=nome, variable=dv).pack(side=tk.LEFT, expand=True)
            dias_vars.append(dv)
        toggle_days()

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        is_archived = (task_data.get('status') == 'encerrado')
        archive_var = tk.BooleanVar(value=is_archived)
        ttk.Checkbutton(frame, text="Arquivar (Inativar Tarefa)", variable=archive_var).pack(anchor=tk.W, pady=5)

        def pre_save_check():
            name = name_entry.get().strip()
            val_str = time_val.get().strip()
            fixed_time = fixed_time_var.get().strip()

            if not name:
                messagebox.showerror("Erro", "Nome da tarefa é obrigatório.", parent=win)
                return
            
            if fixed_time:
                try:
                    time.strptime(fixed_time, "%H:%M")
                except ValueError:
                    messagebox.showerror("Erro", "Formato de hora inválido. Use HH:MM (ex: 14:30)", parent=win)
                    return

            if val_str and not is_locked:
                try:
                    val = int(val_str)
                    unit = time_unit.get()
                    old_val = task_data.get('min_time_val', 0)
                    old_unit = task_data.get('min_time_unit', 'minutos')
                    current_minutes = val * 60 if unit == 'horas' else val
                    old_minutes = (int(old_val) * 60 if old_unit == 'horas' else int(old_val)) if old_val else 0
                    if current_minutes > old_minutes:
                         if not self.check_dreamer_vs_doer(win, val, unit): return 
                except ValueError: pass
            save_final()

        def save_final():
            name = name_entry.get().strip()
            final_id = task_id if is_edit else str(int(time.time()))
            selected_days = [i for i, v in enumerate(dias_vars) if v.get()]
            status = "encerrado" if archive_var.get() else "em progresso"

            current_time_val = time_val.get().strip()
            current_time_unit = time_unit.get()
            old_time_val = str(task_data.get('min_time_val', ''))
            old_time_unit = task_data.get('min_time_unit', 'minutos')
            
            final_signed_date = raw_last_set
            if (current_time_val != old_time_val) or (current_time_unit != old_time_unit) or not is_edit or tampered or not raw_last_set:
                final_signed_date = sign_date(date.today().isoformat())

            new_data = {
                "name": name,
                "schedule_type": sched_var.get(),
                "schedule_days": [0,1,2,3,4,5,6] if sched_var.get() == 'daily' else selected_days,
                "status": status,
                "created_on": task_data.get('created_on', date.today().isoformat()),
                "completed_on": task_data.get('completed_on', None),
                "proof": task_data.get('proof', None),
                "min_time_val": current_time_val,
                "min_time_unit": current_time_unit,
                "min_time_last_set": final_signed_date,
                "fixed_start_time": fixed_time_var.get().strip()
            }
            
            cfg = load_config_data()
            cfg['tasks'][final_id] = new_data
            save_config_data(cfg)
            if callback: callback()
            win.destroy()

        ttk.Button(frame, text="Salvar Alterações", command=pre_save_check).pack(fill=tk.X, pady=10)
        
    def check_dreamer_vs_doer(self, parent, val, unit):
        alert_win = tk.Toplevel(parent)
        alert_win.title("SONHADOR x REALIZADOR")
        center_window(alert_win, 500, 300)
        alert_win.transient(parent)
        alert_win.grab_set()
        alert_win.configure(bg="#1A1A1A")
        
        container = tk.Frame(alert_win, bg="#1A1A1A", padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(container, text="⚠️ SONHADOR x REALIZADOR", font=("Impact", 18), 
                 fg="#FFCC00", bg="#1A1A1A").pack(pady=(0, 15))
        
        msg = (f"Você está definindo uma meta mínima de {val} {unit.upper()}.\n\n"
               "Tem certeza que consegue manter isso?\n"
               "Não será possível alterar o tempo mínimo pelos próximos 7 dias.\n"
               "Se estiver iniciando agora, jogue seguro.")
               
        tk.Label(container, text=msg, font=("Segoe UI", 11), fg="white", bg="#1A1A1A", 
                 justify=tk.CENTER, wraplength=450).pack(pady=(0, 20))
        
        result = {"proceed": False}
        
        def on_rethink():
            result["proceed"] = False
            alert_win.destroy()
            
        def on_commit():
            result["proceed"] = True
            alert_win.destroy()
            
        btn_frame = tk.Frame(container, bg="#1A1A1A")
        btn_frame.pack(fill=tk.X)
        
        btn_commit = tk.Button(btn_frame, text="ME COMPROMETO\n(Minha decisão)", font=("Segoe UI", 10, "bold"),
                               bg="#4CAF50", fg="white", relief=tk.FLAT, padx=10, pady=5,
                               command=on_commit, cursor="hand2")
        btn_commit.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        btn_rethink = tk.Button(btn_frame, text=f"RE-ANALISAR TEMPO\n({val} {unit})", font=("Segoe UI", 10),
                                bg="#007ACC", fg="white", relief=tk.FLAT, padx=10, pady=5,
                                command=on_rethink, cursor="hand2")
        btn_rethink.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))
        
        parent.wait_window(alert_win)
        return result["proceed"]