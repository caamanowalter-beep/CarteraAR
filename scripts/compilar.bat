@echo off
echo Ejecutando análisis de carteras...
cd scripts
call ..\.venv\Scripts\activate
python Historico.py
pause
