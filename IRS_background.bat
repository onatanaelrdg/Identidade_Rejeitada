@echo off
cd /d "%~dp0"

REM Inicia o script em modo DAEMON, sem janela de console
pythonw.exe identidade_rejeitada.py --daemon