@echo off
REM Install compas_tf into the Rhino 8 Python 3.9 environment (py39-rh8).
REM
REM Rhino only needs compas_tf to (a) be importable and (b) draw bundles via the
REM COMPAS scene - so we install compas + compas_rhino + compas_model and then
REM compas_tf itself with --no-deps. The heavy desktop-only deps (compas_manifold,
REM shapely, compas_viewer) are skipped on purpose: the fab examples bake their
REM geometry into a *_rhino.json bundle on the desktop, and the Rhino loader
REM (compas_tf.rhino.draw_bundle) recomputes nothing.

set RHINO_PYTHON=C:\Users\Petras\.rhinocode\py39-rh8\python.exe
set PACKAGE_DIR=C:\brg\compas_tf

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

REM Runtime deps the Rhino side actually needs (skip if Rhino already ships them).
"%RHINO_PYTHON%" -m pip install compas compas_rhino compas_model

REM Install compas_tf editable (live edits) WITHOUT pulling desktop-only deps.
"%RHINO_PYTHON%" -m pip install -e "%PACKAGE_DIR%" --no-deps

echo.
echo Done. You may need to restart Rhino for changes to take effect.
pause
