# bank_manager.py
import os
import json
import uuid
from datetime import date, datetime, timedelta
from core import APP_DATA_DIR, atomic_write, run_backup_system

# Define o caminho do Banco de Dados
BANK_FILE = os.path.join(APP_DATA_DIR, "bank.json")

def load_bank_data():
    """Carrega o ledger do banco. Se não existir, cria a estrutura inicial."""
    default_structure = {
        "transactions": []
    }
    
    if not os.path.exists(BANK_FILE):
        return default_structure
        
    try:
        with open(BANK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao ler bank.json: {e}")
        return default_structure

def save_bank_data(data):
    """Persiste os dados com segurança atômica e aciona backup."""
    try:
        atomic_write(BANK_FILE, data)
        # Opcional: Acionar backup específico se desejar alta redundância
        # run_backup_system(arquivo_alterado=BANK_FILE)
    except Exception as e:
        print(f"Erro crítico ao salvar banco: {e}")

def create_transaction(task_name, min_time, actual_time):
    """
    Calcula e registra o depósito de horas extras.
    Regra do Teto: O bônus máximo é igual ao tempo mínimo da tarefa.
    """
    try:
        # Conversão preventiva para inteiros
        min_time = int(min_time)
        actual_time = int(actual_time)
        
        if actual_time <= min_time:
            return False, "Sem excedente para depositar."
        
        excedente = actual_time - min_time
        
        # APLICANDO A REGRA DO TETO (CAP)
        # Se a tarefa é 90min, o máximo que ganha é 90min, mesmo se trabalhar 500min.
        banco_earned = min(excedente, min_time)
        
        if banco_earned <= 0:
            return False, "Cálculo resultou em zero."

        today = date.today()
        unlock_date = today + timedelta(days=180) # 6 Meses de Carência (Lockup)
        
        transaction = {
            "id": str(uuid.uuid4()),
            "origin_date": today.isoformat(),
            "task_source": task_name,
            "amount_earned": banco_earned,
            "amount_remaining": banco_earned, # Começa cheio
            "unlock_date": unlock_date.isoformat(),
            "status": "locked" # locked | available | depleted
        }
        
        data = load_bank_data()
        data["transactions"].append(transaction)
        save_bank_data(data)
        
        return True, f"+{banco_earned} minutos depositados (Desbloqueio em {unlock_date.strftime('%d/%m/%Y')})"

    except Exception as e:
        return False, f"Erro no processamento bancário: {str(e)}"

def get_balances():
    """
    Retorna o saldo consolidado.
    LOCKED: Saldo futuro (ainda na carência).
    AVAILABLE: Saldo líquido (carência vencida e pronto para uso).
    """
    data = load_bank_data()
    today_str = date.today().isoformat()
    
    total_locked = 0
    total_available = 0
    
    for t in data.get("transactions", []):
        remaining = t.get("amount_remaining", 0)
        
        if remaining <= 0:
            continue
            
        unlock_date = t.get("unlock_date", "")
        
        if unlock_date <= today_str:
            total_available += remaining
            # Atualiza status visualmente se necessário, mas a lógica confia na data
            if t.get("status") == "locked": 
                t["status"] = "available" 
        else:
            total_locked += remaining
            
    # Salva apenas para persistir eventuais mudanças de status 'locked' -> 'available'
    save_bank_data(data)
    
    return total_locked, total_available

def spend_minutes(minutes_needed):
    """
    Lógica FIFO (First In, First Out).
    Consome os minutos das transações disponíveis mais antigas.
    Retorna: (Sucesso, Mensagem)
    """
    locked, available = get_balances()
    
    if available < minutes_needed:
        return False, f"Saldo insuficiente. Disponível: {available}m | Necessário: {minutes_needed}m"
        
    data = load_bank_data()
    today_str = date.today().isoformat()
    
    # 1. Filtra apenas as disponíveis com saldo
    available_txs = [
        t for t in data["transactions"] 
        if t.get("unlock_date") <= today_str and t.get("amount_remaining", 0) > 0
    ]
    
    # 2. Ordena por data de origem (Mais antigas primeiro)
    available_txs.sort(key=lambda x: x["origin_date"])
    
    minutes_to_deduct = minutes_needed
    spent_log = [] # Para registro interno ou debug
    
    for tx in available_txs:
        if minutes_to_deduct <= 0:
            break
            
        current_balance = tx["amount_remaining"]
        
        if current_balance >= minutes_to_deduct:
            # Transação atual cobre tudo o que falta
            tx["amount_remaining"] -= minutes_to_deduct
            spent_log.append(f"Gasto {minutes_to_deduct}m de {tx['origin_date']}")
            minutes_to_deduct = 0
        else:
            # Transação atual não cobre tudo, zera ela e passa para a próxima
            minutes_to_deduct -= current_balance
            spent_log.append(f"Gasto {current_balance}m de {tx['origin_date']} (Esgotada)")
            tx["amount_remaining"] = 0
            tx["status"] = "depleted"

    save_bank_data(data)
    return True, "Tempo resgatado com sucesso."

def get_history():
    """Retorna a lista de transações para a UI."""
    data = load_bank_data()
    # Retorna invertido (mais novas no topo)
    return list(reversed(data.get("transactions", [])))