@echo off
REM Install compas_tf package into Rhino 8 Python environment

set RHINO_PYTHON=C:\Users\petrasv\.rhinocode\py39-rh8\python.exe
set PACKAGE_DIR=C:\brg\code_python\compas_tf

echo Installing compas_tf into Rhino 8 Python
echo Python: %RHINO_PYTHON%
echo Package: %PACKAGE_DIR%
echo.

REM Check if python exists
if not exist "%RHINO_PYTHON%" (
    echo ERROR: Rhino Python not found at expected path.
    echo Expected: %RHINO_PYTHON%
    pause
    exit /b 1
)

REM Install in editable mode for development
"%RHINO_PYTHON%" -m pip install -e "%PACKAGE_DIR%"

echo.
echo Done. You may need to restart Rhino for changes to take effect.
pause
