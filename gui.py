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
        else:
            for task_id, task in self.tasks_for_today.items():
                f = ttk.Frame(self.scrollable_frame, padding=5)
                f.pack(fill=tk.X, pady=2)
                
                # Verifica se a data salva tem a assinatura correta
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
        """Exibe popup verde, toca áudio calmo e parabeniza."""
        win = tk.Toplevel(self.root)
        win.title("DIA CONCLUÍDO")
        center_window(win, 500, 250)
        win.transient(self.root)
        win.grab_set()
        
        # Configuração Visual: Verde Sereno
        bg_color = "#1B5E20" # Verde escuro elegante
        fg_color = "#FFFFFF"
        win.configure(bg=bg_color)
        
        # Escolhe frase
        config = load_config_data()
        phrases = config.get('celebrations', ["Parabéns pelo foco."])
        phrase = random.choice(phrases)
        
        # Layout
        frame = tk.Frame(win, bg=bg_color, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="✅ VOCÊ CONSEGUIU!", font=("Impact", 22), 
                 bg=bg_color, fg="#66BB6A").pack(pady=(0, 15))
        
        tk.Label(frame, text=phrase, font=("Segoe UI", 12), 
                 bg=bg_color, fg=fg_color, wraplength=450, justify=tk.CENTER).pack(pady=(0, 20))
        
        # Botão Fechar
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
                # Assina a data de hoje antes de salvar
                signed_today = sign_date(date.today().isoformat())
                task['completed_on'] = signed_today
                
                task['proof'] = pdata; task['proof_type'] = ptype
                self.config_data['tasks'] = self.tasks
                save_config_data(self.config_data)
                log_event("task_completed", f"{task_id}: {task['name']}")
                self.update_task_list()
                
                # Verifica se TUDO foi concluído (agora checando hashes)
                tasks_for_today = get_tasks_for_today()
                all_done = True
                if not tasks_for_today: all_done = False
                
                for t in tasks_for_today.values():
                    # Verifica hash de cada tarefa
                    v_date = verify_and_get_date(t.get('completed_on'))
                    if v_date != date.today().isoformat(): 
                        all_done = False; break
                
                if all_done:
                    # Assina a data geral também, por segurança
                    self.config_data['last_completion_date'] = date.today().isoformat()
                    save_config_data(self.config_data)
                    self.show_celebration_popup()
            else: var.set(False)

    def get_proof(self, task):
        """Janela de prova com validação rígida de tempo."""
        task_name = task.get('name', 'Tarefa')
        min_val = task.get('min_time_val', '')
        min_unit = task.get('min_time_unit', 'minutos')
        
        # Monta a string de validação (Ex: "30 minutos" ou "4 horas")
        validation_str = f"{min_val} {min_unit}" if min_val else None

        win = tk.Toplevel(self.root)
        win.title(f"Prova: {task_name}")
        center_window(win, 450, 400) # Aumentei um pouco a altura
        win.transient(self.root)
        win.grab_set()
        
        # Container principal
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # --- SEÇÃO DE VALIDAÇÃO DE TEMPO ---
        time_entry = None
        
        if validation_str:
            # Container visual para a validação
            val_frame = tk.LabelFrame(frame, text="Verificação de Tempo", padx=10, pady=10, bg="#2E2E2E", fg="#E0E0E0")
            val_frame.pack(fill=tk.X, pady=(0, 15))
            
            # Label com o alvo
            ttk.Label(val_frame, text=f"Tempo Mínimo Exigido: {validation_str}", 
                      font=("Segoe UI", 10, "bold"), foreground="#FFCC00", background="#2E2E2E").pack(anchor=tk.W)
            
            # Input do usuário
            row = tk.Frame(val_frame, bg="#2E2E2E")
            row.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(row, text="Tempo trabalhado:", background="#2E2E2E", foreground="#FFFFFF").pack(side=tk.LEFT, padx=(0, 5))
            
            time_entry = ttk.Entry(row)
            time_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            ttk.Label(val_frame, text=f"(Digite exatamente: '{validation_str}')", 
                      font=("Segoe UI", 8), foreground="#888888", background="#2E2E2E").pack(anchor=tk.W)

        # --- SEÇÃO DE PROVA (TEXTO/IMAGEM) ---
        ttk.Label(frame, text="Descreva o que foi feito ou anexe prova:").pack(anchor=tk.W, pady=(0, 5))
        
        entry = tk.Text(frame, height=8, width=50)
        entry.pack(pady=5, fill=tk.BOTH, expand=True)
        
        res = {"t": None, "d": None}
        
        def check_time_validation():
            """Retorna True se passou na validação ou se não há validação."""
            if not validation_str:
                return True
                
            user_input = time_entry.get().strip()
            
            # Validação EXATA (String match)
            if user_input != validation_str:
                messagebox.showerror("Integridade Falhou", 
                                     f"Você definiu um mínimo de '{validation_str}'.\n"
                                     f"Você digitou '{user_input}'.\n\n"
                                     "Se você fez menos, não marque como concluído.\n"
                                     "Se fez o tempo certo, digite exatamente igual.",
                                     parent=win)
                return False
            return True

        def save_txt():
            if not check_time_validation(): return
            
            d = entry.get("1.0", tk.END).strip()
            if d: 
                res["t"] = "text"
                res["d"] = d
                win.destroy()
            else:
                messagebox.showwarning("Prova Vazia", "Escreva algo sobre a tarefa.", parent=win)

        def save_img():
            if not check_time_validation(): return

            fp = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
            if fp:
                try:
                    np = os.path.join(PROOFS_DIR, f"proof_{date.today()}_{os.path.basename(fp)}")
                    shutil.copy(fp, np)
                    res["t"] = "image"
                    res["d"] = np
                    win.destroy()
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao salvar imagem: {e}")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10, fill=tk.X)
        
        ttk.Button(btn_frame, text="Salvar Texto", command=save_txt).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(btn_frame, text="Anexar Imagem", command=save_img).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        self.root.wait_window(win)
        return res["t"], res["d"]

    def open_menu(self):
        win = tk.Toplevel(self.root); win.title("Menu"); center_window(win, 300, 250)
        win.transient(self.root); win.grab_set()
        f = ttk.Frame(win, padding="15"); f.pack(fill=tk.BOTH, expand=True)
        ttk.Button(f, text="Gerenciar Tarefas", command=self.open_task_manager).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Gerenciar Rejeições", command=lambda: self.manage_list("Rejeições", "rejections")).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Configurar Velocidade", command=self.open_settings).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Testar Áudio", command=self.test_audio).pack(fill=tk.X, pady=5)
        ttk.Button(f, text="Sair", command=self.quit_app).pack(fill=tk.X, pady=15)

    def test_audio(self):
        cfg = load_config_data()
        if not cfg['rejections']: return
        rej = self.tasks.get('rejections', ["Teste"])[0] if not cfg['rejections'] else cfg['rejections'][0]
        set_system_volume(80)
        
        # Gambiarra rápida para testar usando a lógica do subprocess que já temos, ou simplificar:
        # Para manter simples, vou chamar o powershell direto aqui também ou importar do daemon se fosse static
        # Mas como movemos para daemon, vamos replicar simples:
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
        
        # Estilo e Frame
        frame = ttk.Frame(manager_win, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Treeview
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
                # Só mostra as ativas (em progresso)
                if t.get('status', 'em progresso') == 'em progresso':
                    if t.get('schedule_type') == 'daily':
                        sched = "Todos os dias"
                    else:
                        ds = t.get('schedule_days', [])
                        sched = ", ".join([dias_sem[i] for i in ds]) if ds else "Personalizado"
                    tree.insert("", tk.END, iid=tid, values=(t['name'], sched))

        populate()

        # Botões
        btn_frame = ttk.Frame(manager_win, padding=(10, 10))
        btn_frame.pack(fill=tk.X)

        def edit_selected():
            sel = tree.selection()
            if not sel: return
            task_id = sel[0]
            # Abre o editor passando o ID da tarefa existente
            self.open_task_editor(parent=manager_win, task_id=task_id, callback=lambda: [populate(), self.update_task_list()])

        def create_new():
            # Abre o editor sem ID (modo criação)
            self.open_task_editor(parent=manager_win, task_id=None, callback=lambda: [populate(), self.update_task_list()])

        def open_archives():
            # Abre a nova janela de arquivados
            self.open_archived_manager(manager_win)
            # Atualiza esta lista quando voltar, caso tenha desarquivado algo
            populate()
            self.update_task_list()

        ttk.Button(btn_frame, text="Nova Tarefa", command=create_new).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Editar Selecionada", command=edit_selected).pack(side=tk.LEFT, padx=5)
        
        # Botão de Arquivados (Fica na direita, cor diferente se possível, mas padrão aqui)
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
            # Abre o mesmo editor, permitindo desmarcar "Arquivado"
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
        """Janela unificada com Trava de 7 dias, Hash e Horário Fixo."""
        is_edit = task_id is not None
        title = "Editar Tarefa" if is_edit else "Nova Tarefa"
        
        win = tk.Toplevel(parent)
        win.title(title)
        center_window(win, 450, 550) # Aumentei altura
        win.transient(parent)
        win.grab_set()
        
        config = load_config_data()
        task_data = config['tasks'].get(task_id, {}) if is_edit else {}
        
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. Nome
        ttk.Label(frame, text="Nome da Tarefa:").pack(anchor=tk.W)
        name_entry = ttk.Entry(frame)
        name_entry.pack(fill=tk.X, pady=(0, 10))
        if is_edit: name_entry.insert(0, task_data.get('name', ''))
        else: name_entry.focus()

        # 2. Tempo Mínimo Diário
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

        # Lógica de Trava (Hash)
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

        # 3. Horário Fixo (NOVO)
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(frame, text="Horário Fixo de Início (Opcional):", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, text="Formato HH:MM (Ex: 14:30). Deixe vazio se não usar.", font=("Segoe UI", 8), foreground="#888").pack(anchor=tk.W)
        
        fixed_time_var = tk.StringVar(value=task_data.get('fixed_start_time', ''))
        fixed_time_entry = ttk.Entry(frame, textvariable=fixed_time_var, width=10)
        fixed_time_entry.pack(anchor=tk.W, pady=(0, 10))

        # 4. Agenda
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

        # 5. Checkbox Arquivar
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        is_archived = (task_data.get('status') == 'encerrado')
        archive_var = tk.BooleanVar(value=is_archived)
        ttk.Checkbutton(frame, text="Arquivar (Inativar Tarefa)", variable=archive_var).pack(anchor=tk.W, pady=5)

        # --- Lógica de Salvar ---
        def pre_save_check():
            name = name_entry.get().strip()
            val_str = time_val.get().strip()
            fixed_time = fixed_time_var.get().strip()

            if not name:
                messagebox.showerror("Erro", "Nome da tarefa é obrigatório.", parent=win)
                return
            
            # Validação simples de HH:MM
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
                "fixed_start_time": fixed_time_var.get().strip() # <--- SALVA O HORÁRIO
            }
            
            cfg = load_config_data()
            cfg['tasks'][final_id] = new_data
            save_config_data(cfg)
            if callback: callback()
            win.destroy()

        ttk.Button(frame, text="Salvar Alterações", command=pre_save_check).pack(fill=tk.X, pady=10)
        
    def check_dreamer_vs_doer(self, parent, val, unit):
        """Janela Modal: Sonhador vs Realizador."""
        alert_win = tk.Toplevel(parent)
        alert_win.title("SONHADOR x REALIZADOR")
        center_window(alert_win, 500, 300)
        alert_win.transient(parent)
        alert_win.grab_set()
        alert_win.configure(bg="#1A1A1A")
        
        # Remove a barra de título padrão para forçar foco no conteúdo (opcional, mas fica mais agressivo)
        # alert_win.overrideredirect(True) 
        
        container = tk.Frame(alert_win, bg="#1A1A1A", padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Título
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
        
        # Botão Comprometer (Agora o Principal: Verde e na Esquerda)
        btn_commit = tk.Button(btn_frame, text="ME COMPROMETO\n(Minha decisão)", font=("Segoe UI", 10, "bold"),
                               bg="#4CAF50", fg="white", relief=tk.FLAT, padx=10, pady=5,
                               command=on_commit, cursor="hand2")
        btn_commit.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        # Botão Re-analisar (Agora Secundário: Azul e na Direita)
        btn_rethink = tk.Button(btn_frame, text=f"RE-ANALISAR TEMPO\n({val} {unit})", font=("Segoe UI", 10),
                                bg="#007ACC", fg="white", relief=tk.FLAT, padx=10, pady=5,
                                command=on_rethink, cursor="hand2")
        btn_rethink.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))
        
        parent.wait_window(alert_win)
        return result["proceed"]