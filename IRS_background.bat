@echo off
cd /d "%~dp0"

REM Inicia o script em modo DAEMON, sem janela de console
start pythonw identidade_rejeitada.py --daemon