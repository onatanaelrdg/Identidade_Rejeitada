# gui.py
import os
import sys
import time
import shutil
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
    set_system_volume, center_window, get_tasks_for_today
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
                var = tk.BooleanVar(value=(task.get('completed_on') == today_str))
                cb = ttk.Checkbutton(f, text=task['name'], variable=var, command=lambda v=var, tid=task_id: self.on_task_check(v, tid))
                cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
                if task.get('completed_on') == today_str:
                    cb.config(state=tk.DISABLED)
                    ttk.Label(f, text="Concluído", font=("Segoe UI", 9, "italic"), foreground="#00A000").pack(side=tk.RIGHT)
                self.task_widgets[task_id] = {'var': var, 'cb': cb}

    def on_task_check(self, var, task_id):
        if var.get(): 
            self.config_data = load_config_data()
            self.tasks = self.config_data.get('tasks', {})
            if task_id not in self.tasks: return
            task = self.tasks[task_id]
            ptype, pdata = self.get_proof(task['name'])
            
            if pdata:
                task['completed_on'] = date.today().isoformat()
                task['proof'] = pdata; task['proof_type'] = ptype
                self.config_data['tasks'] = self.tasks
                save_config_data(self.config_data)
                log_event("task_completed", f"{task_id}: {task['name']}")
                self.update_task_list()
                
                tasks_for_today = get_tasks_for_today()
                all_done = True
                if not tasks_for_today: all_done = False
                for t in tasks_for_today.values():
                    if t.get('completed_on') != date.today().isoformat(): all_done = False; break
                
                if all_done:
                    messagebox.showinfo("Parabéns!", "Todas as atividades de rotina foram concluídas! Os áudios estão desativados por hoje.")
                    self.config_data['last_completion_date'] = date.today().isoformat()
                    save_config_data(self.config_data)
            else: var.set(False)

    def get_proof(self, task_name):
        win = tk.Toplevel(self.root)
        win.title(f"Prova: {task_name}")
        center_window(win, 400, 300)
        win.transient(self.root); win.grab_set()
        ttk.Label(win, text="Descreva ou anexe imagem.").pack(pady=10)
        entry = tk.Text(win, height=10, width=50); entry.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        res = {"t": None, "d": None}
        
        def save_txt():
            d = entry.get("1.0", tk.END).strip()
            if d: res["t"]="text"; res["d"]=d; win.destroy()
        def save_img():
            fp = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
            if fp:
                try:
                    np = os.path.join(PROOFS_DIR, f"proof_{date.today()}_{os.path.basename(fp)}")
                    shutil.copy(fp, np); res["t"]="image"; res["d"]=np; win.destroy()
                except: pass
        
        btn = ttk.Frame(win); btn.pack(pady=10)
        ttk.Button(btn, text="Texto", command=save_txt).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text="Imagem", command=save_img).pack(side=tk.LEFT, padx=5)
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
        win = tk.Toplevel(self.root); win.title("Tarefas"); center_window(win, 500, 400)
        win.transient(self.root); win.grab_set()
        tree = ttk.Treeview(win, columns=("Nome", "Agenda"), show="headings"); tree.pack(fill=tk.BOTH, expand=True)
        tree.heading("Nome", text="Nome"); tree.heading("Agenda", text="Agenda")
        
        def pop():
            for i in tree.get_children(): tree.delete(i)
            cfg = load_config_data()
            for tid, t in cfg.get('tasks', {}).items():
                if t.get('status') == 'em progresso':
                    sched = "Todos dias" if t.get('schedule_type') == 'daily' else "Personalizado"
                    tree.insert("", tk.END, iid=tid, values=(t['name'], sched))
        pop()
        
        def add_task():
            aw = tk.Toplevel(win); aw.title("Nova"); center_window(aw, 300, 200)
            ne = ttk.Entry(aw); ne.pack(pady=5)
            def save():
                n = ne.get()
                if n:
                    tid = str(int(time.time()))
                    new_t = {"name": n, "created_on": date.today().isoformat(), "completed_on": None, "proof": None, "schedule_type": "daily", "schedule_days": [0,1,2,3,4,5,6], "status": "em progresso"}
                    c = load_config_data(); c['tasks'][tid] = new_t; save_config_data(c); pop(); self.update_task_list(); aw.destroy()
            ttk.Button(aw, text="Salvar", command=save).pack()
            
        def end_task():
            s = tree.selection()
            if s:
                c = load_config_data(); c['tasks'][s[0]]['status'] = 'encerrado'; save_config_data(c); pop(); self.update_task_list()

        ttk.Button(win, text="Nova Tarefa", command=add_task).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(win, text="Encerrar Selecionada", command=end_task).pack(side=tk.RIGHT, padx=10, pady=10)

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