@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating Gene Python environment...
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Python 3 could not create a virtual environment.
        pause
        exit /b 1
    )
    call ".venv\Scripts\python.exe" -m pip install --upgrade pip
    call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
if exist "%~1" (
    ".venv\Scripts\python.exe" main.py "%~1"
) else if exist "jene_PSO2.pmx" (
    ".venv\Scripts\python.exe" main.py "jene_PSO2.pmx"
) else (
    echo Drag a PMX file onto this BAT, or put jene_PSO2.pmx beside main.py.
    pause
)
endlocal
