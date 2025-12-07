@echo off
TITLE Identidade Rejeitada
COLOR 0C

REM Inicia o script principal
cd /d "%~dp0"
start "" pythonw identidade_rejeitada.py --daemon