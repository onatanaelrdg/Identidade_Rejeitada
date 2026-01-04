# bank_manager.py
import os
import json
import uuid
import hashlib
import tkinter as tk
from datetime import date, datetime, timedelta
# ADICIONADO: log_event para registrar a violação
from core import APP_DATA_DIR, atomic_write, SECRET_SALT, log_event

# Caminho do Ledger
BANK_FILE = os.path.join(APP_DATA_DIR, "bank.json")

# --- SISTEMA DE ALERTA VISUAL E LOG ---
def alert_security_breach(error_msg):
    """
    Exibe um Popup Crítico Vermelho e LOGA a violação na segurança.
    """
    # 1. REGISTRO FORENSE (O mais importante)
    # Isso vai para o security_log.json com hash na blockchain principal
    try:
        log_event("BANK_INTEGRITY_FAIL", f"Violação Crítica do Banco de Horas: {error_msg}", category="security")
    except:
        print("FALHA AO LOGAR VIOLAÇÃO DE SEGURANÇA")

    # 2. ALERTA VISUAL (O Pânico)
    try:
        root = tk.Tk()
        root.withdraw() 
        
        popup = tk.Toplevel(root)
        popup.title("ALERTA DE SEGURANÇA MÁXIMA")
        popup.attributes("-topmost", True)
        
        bg_color = "#330000" 
        fg_color = "#FF0000" 
        
        popup.configure(bg=bg_color)
        
        w, h = 600, 300
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        popup.geometry(f"{w}x{h}+{x}+{y}")
        
        tk.Label(popup, text="⚠️ VIOLAÇÃO DE INTEGRIDADE ⚠️", font=("Impact", 24), 
                 bg=bg_color, fg=fg_color).pack(pady=(20, 10))
                 
        tk.Label(popup, text="O Banco de Horas foi adulterado manualmente.", font=("Segoe UI", 12, "bold"), 
                 bg=bg_color, fg="#FFFFFF").pack()
                 
        tk.Label(popup, text=f"REGISTRO DE SEGURANÇA CRIADO.\nDETALHE: {error_msg}", font=("Consolas", 10), 
                 bg=bg_color, fg="#FFAAAA", pady=20).pack()

        tk.Button(popup, text="ENTENDI (O SALDO SERÁ ZERADO)", font=("Segoe UI", 10, "bold"),
                  bg="#FF0000", fg="white", command=lambda: [popup.destroy(), root.destroy()]).pack(pady=10)
        
        popup.grab_set()
        root.wait_window(popup)
    except:
        print(f"CRITICAL FAIL: {error_msg}")

# --- LÓGICA DE BLOCKCHAIN ---

def calculate_hash(index, timestamp, type_, task, amount, unlock_date, prev_hash):
    """
    Gera o hash SHA-256 do bloco.
    BLINDADO: Inclui unlock_date e todos os campos vitais.
    """
    payload = f"{index}{timestamp}{type_}{task}{amount}{unlock_date}{prev_hash}{SECRET_SALT}".encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def init_genesis_block():
    """Cria o bloco zero."""
    now_iso = datetime.now().isoformat()
    genesis_unlock = "2000-01-01"
    
    genesis = {
        "index": 0,
        "timestamp": now_iso,
        "type": "GENESIS",
        "task_source": "SYSTEM",
        "amount": 0,
        "unlock_date": genesis_unlock,
        "previous_hash": "0" * 64,
        "hash": ""
    }
    genesis["hash"] = calculate_hash(0, now_iso, "GENESIS", "SYSTEM", 0, genesis_unlock, "0"*64)
    return {"chain": [genesis]}

def load_ledger():
    """Carrega a blockchain."""
    if not os.path.exists(BANK_FILE):
        return init_genesis_block()
    
    try:
        with open(BANK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "transactions" in data and "chain" not in data:
            return migrate_old_format(data)
            
        return data
    except:
        return init_genesis_block()

def migrate_old_format(old_data):
    """Converte formato inseguro para Blockchain."""
    new_data = init_genesis_block()
    chain = new_data["chain"]
    
    for tx in old_data.get("transactions", []):
        add_block_to_chain(chain, "DEPOSIT", tx.get("task_source"), 
                           tx.get("amount_earned"), tx.get("unlock_date"))
        
        gasto = tx.get("amount_earned", 0) - tx.get("amount_remaining", 0)
        if gasto > 0:
             add_block_to_chain(chain, "SPEND", "Migração de Gasto", -gasto, date.today().isoformat())

    save_ledger(new_data)
    return new_data

def verify_integrity(chain):
    """Auditoria completa da corrente. Dispara ALERTA + LOG se falhar."""
    for i in range(1, len(chain)):
        current = chain[i]
        prev = chain[i-1]
        
        # 1. Elo da corrente
        if current['previous_hash'] != prev['hash']:
            msg = f"Quebra de corrente no bloco {i}.\nLink Hash inválido."
            alert_security_breach(msg)
            return False
            
        # 2. Conteúdo do bloco
        recalc = calculate_hash(
            current['index'], 
            current['timestamp'], 
            current['type'], 
            current['task_source'], 
            current['amount'], 
            current['unlock_date'], 
            current['previous_hash']
        )
        
        if current['hash'] != recalc:
            msg = f"Conteúdo adulterado no bloco {i}.\nHash de conteúdo inválido."
            alert_security_breach(msg)
            return False
            
    return True

def add_block_to_chain(chain, type_, task, amount, unlock_date):
    last_block = chain[-1]
    new_index = last_block['index'] + 1
    now_iso = datetime.now().isoformat()
    
    new_block = {
        "index": new_index,
        "timestamp": now_iso,
        "type": type_,
        "task_source": task,
        "amount": int(amount),
        "unlock_date": unlock_date,
        "previous_hash": last_block['hash'],
        "hash": ""
    }
    
    new_block["hash"] = calculate_hash(
        new_index, now_iso, type_, task, int(amount), unlock_date, last_block['hash']
    )
    
    chain.append(new_block)

def save_ledger(data):
    if verify_integrity(data['chain']):
        atomic_write(BANK_FILE, data)
    else:
        print("ABORTANDO SALVAMENTO: Blockchain corrompida.")

# --- API PÚBLICA ---

def create_transaction(task_name, min_time, actual_time):
    data = load_ledger()
    if not verify_integrity(data['chain']):
        return False, "ERRO CRÍTICO: Blockchain violada. Log de segurança gerado."

    min_time = int(min_time)
    actual_time = int(actual_time)
    excedente = actual_time - min_time
    banco_earned = min(excedente, min_time) 
    
    if banco_earned <= 0: return False, "Sem excedente."
    
    unlock_date = (date.today() + timedelta(days=180)).isoformat()
    
    add_block_to_chain(data['chain'], "DEPOSIT", task_name, banco_earned, unlock_date)
    save_ledger(data)
    
    return True, f"+{banco_earned}m depositados (Cadeado: 6 meses)"

def get_balances():
    data = load_ledger()
    if not verify_integrity(data['chain']): return 0, 0
    
    today_str = date.today().isoformat()
    
    total_locked = 0
    gross_available = 0
    total_spent = 0
    
    for block in data['chain']:
        if block['type'] == 'GENESIS': continue
        
        amt = block['amount']
        
        if block['type'] == 'DEPOSIT':
            if block['unlock_date'] <= today_str:
                gross_available += amt
            else:
                total_locked += amt
        elif block['type'] == 'SPEND':
            total_spent += abs(amt)
            
    net_available = max(0, gross_available - total_spent)
    return total_locked, net_available

def spend_minutes(minutes_needed):
    locked, available = get_balances()
    
    if available < minutes_needed:
        return False, f"Saldo insuficiente. Tem: {available}m | Precisa: {minutes_needed}m"
        
    data = load_ledger()
    add_block_to_chain(data['chain'], "SPEND", "Standby Mode", -minutes_needed, date.today().isoformat())
    save_ledger(data)
    
    return True, "Tempo resgatado."

def get_history():
    data = load_ledger()
    chain = data['chain']
    
    if not verify_integrity(chain): return []

    today_str = date.today().isoformat()
    total_spent_history = sum(abs(b['amount']) for b in chain if b['type'] == 'SPEND')
    
    view_list = []
    deposits = [b for b in chain if b['type'] == 'DEPOSIT']
    
    remaining_debt = total_spent_history
    
    for block in deposits:
        original_amount = block['amount']
        current_remaining = original_amount
        
        if block['unlock_date'] <= today_str:
            if remaining_debt > 0:
                deduction = min(remaining_debt, original_amount)
                current_remaining -= deduction
                remaining_debt -= deduction
        
        view_obj = {
            "origin_date": block['timestamp'][:10],
            "task_source": block['task_source'],
            "amount_earned": original_amount,
            "amount_remaining": current_remaining,
            "unlock_date": block['unlock_date'],
            "status": "locked" if block['unlock_date'] > today_str else "available"
        }
        view_list.append(view_obj)
        
    return list(reversed(view_list))