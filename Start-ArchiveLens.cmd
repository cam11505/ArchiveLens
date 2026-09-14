@echo off
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo Please follow the Development Setup in README.md first.
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" -m archivelens %*
