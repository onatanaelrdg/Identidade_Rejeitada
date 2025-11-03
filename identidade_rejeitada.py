#!/usr/bin/env python3
"""
IDENTITY REJECTION SYSTEM
Sistema de áudios de identidade rejeitada que tocam em horários aleatórios
para criar incômodo imediato e físico, forçando ação.
"""

import os
import random
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import threading
import subprocess
import platform

# Detecta sistema operacional
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

class IdentityRejectionSystem:
    def __init__(self, config_file="rejection_config.json"):
        self.config_file = config_file
        self.rejections = []
        self.min_interval = 30  # minutos entre áudios
        self.max_interval = 180  # 3 horas
        self.active_hours = (8, 22)  # Apenas entre 8h e 22h
        self.running = False
        self.load_config()
        
    def load_config(self):
        """Carrega configurações ou cria arquivo padrão"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.rejections = data.get('rejections', [])
                self.min_interval = data.get('min_interval', 30)
                self.max_interval = data.get('max_interval', 180)
                self.active_hours = tuple(data.get('active_hours', [8, 22]))
        else:
            self.create_default_config()
    
    def create_default_config(self):
        """Cria arquivo de configuração padrão"""
        default_rejections = [
            "Eu não quero emagrecer",
            "Eu não quero falar inglês fluentemente",
            "Eu não quero ser rico",
            "Eu não quero poder ajudar minha mãe",
            "Eu não quero liderar minha família",
            "Eu quero continuar sozinho pro resto da minha vida",
            "Eu não quero realizar meus sonhos",
            "Eu não quero ter disciplina",
            "Eu não quero ser respeitado",
            "Eu não quero ter controle da minha vida"
        ]
        
        config = {
            'rejections': default_rejections,
            'min_interval': 30,
            'max_interval': 180,
            'active_hours': [8, 22]
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        self.rejections = default_rejections
        print(f"✅ Arquivo de configuração criado: {self.config_file}")
        print("📝 Edite-o para personalizar suas rejeições!")
    
    def speak_text(self, text):
        """Faz o sistema falar o texto usando TTS nativo"""
        try:
            if IS_WINDOWS:
                # Windows: PowerShell com SAPI
                subprocess.run([
                    'powershell',
                    '-Command',
                    f'Add-Type -AssemblyName System.Speech; '
                    f'$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$speak.Rate = 2; '  # Mais lento e dramático
                    f'$speak.Volume = 100; '
                    f'$speak.Speak("{text}")'
                ], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            elif IS_MACOS:
                # macOS: say command
                subprocess.run(['say', '-r', '120', text], check=True)
            
            elif IS_LINUX:
                # Linux: espeak ou festival
                try:
                    subprocess.run(['espeak', '-s', '140', text], check=True)
                except FileNotFoundError:
                    try:
                        subprocess.run(['festival', '--tts'], 
                                     input=text.encode(), check=True)
                    except FileNotFoundError:
                        print("⚠️  Instale espeak ou festival para TTS no Linux")
                        print(f"   Text: {text}")
        
        except Exception as e:
            print(f"❌ Erro ao reproduzir áudio: {e}")
            print(f"   Texto: {text}")
    
    def is_active_hour(self):
        """Verifica se está dentro do horário ativo"""
        current_hour = datetime.now().hour
        return self.active_hours[0] <= current_hour < self.active_hours[1]
    
    def get_next_interval(self):
        """Retorna o próximo intervalo aleatório em minutos"""
        return random.randint(self.min_interval, self.max_interval)
    
    def play_random_rejection(self):
        """Toca uma rejeição aleatória"""
        if not self.rejections:
            print("⚠️  Nenhuma rejeição configurada!")
            return
        
        rejection = random.choice(self.rejections)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n{'='*60}")
        print(f"🔊 [{timestamp}] IDENTIDADE REJEITADA:")
        print(f"   \"{rejection}\"")
        print(f"{'='*60}\n")
        
        # Toca o áudio
        self.speak_text(rejection)
    
    def run(self):
        """Loop principal do sistema"""
        self.running = True
        print("\n" + "="*60)
        print("🚀 IDENTITY REJECTION SYSTEM ATIVADO")
        print("="*60)
        print(f"⏰ Horário ativo: {self.active_hours[0]}h às {self.active_hours[1]}h")
        print(f"⏱️  Intervalo: {self.min_interval}-{self.max_interval} minutos")
        print(f"📝 Rejeições carregadas: {len(self.rejections)}")
        print(f"🛑 Pressione Ctrl+C para parar")
        print("="*60 + "\n")
        
        try:
            while self.running:
                if self.is_active_hour():
                    self.play_random_rejection()
                    interval = self.get_next_interval()
                    next_time = datetime.now() + timedelta(minutes=interval)
                    print(f"⏳ Próximo áudio em {interval} minutos ({next_time.strftime('%H:%M')})")
                    time.sleep(interval * 60)
                else:
                    print(f"💤 Fora do horário ativo. Aguardando...")
                    time.sleep(300)  # Checa a cada 5 minutos
        
        except KeyboardInterrupt:
            print("\n\n🛑 Sistema interrompido pelo usuário")
            self.running = False
    
    def stop(self):
        """Para o sistema"""
        self.running = False


def main():
    """Função principal"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║        IDENTITY REJECTION SYSTEM v1.0                     ║
    ║        "Faça seu cérebro gritar"                          ║
    ║                                                           ║
    ║  Transforma suas rejeições em incômodos físicos          ║
    ║  para forçar ação através do desconforto imediato        ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    system = IdentityRejectionSystem()
    
    # Menu de opções
    print("\nOpções:")
    print("1. Iniciar sistema (rodar em background)")
    print("2. Testar uma rejeição agora")
    print("3. Editar configurações")
    print("4. Sair")
    
    choice = input("\nEscolha uma opção: ").strip()
    
    if choice == "1":
        system.run()
    elif choice == "2":
        print("\n🧪 Modo de teste...")
        system.play_random_rejection()
        print("\n✅ Teste concluído!")
    elif choice == "3":
        print(f"\n📝 Edite o arquivo: {system.config_file}")
        print("   Depois reinicie o programa.")
    else:
        print("\n👋 Até logo!")


if __name__ == "__main__":
    main()