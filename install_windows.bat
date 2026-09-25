@echo off
setlocal
cd /d "%~dp0"
set "DIRECTOR_PYTHON="
if exist "..\python_embeded\python.exe" set "DIRECTOR_PYTHON=..\python_embeded\python.exe"
if exist "..\..\python_embeded\python.exe" set "DIRECTOR_PYTHON=..\..\python_embeded\python.exe"
if exist "..\..\..\python_embeded\python.exe" set "DIRECTOR_PYTHON=..\..\..\python_embeded\python.exe"
if defined DIRECTOR_PYTHON goto run
echo Portable Python was not found. Use your ComfyUI Python to run install.py install --comfy "path to ComfyUI".
pause
exit /b 1
:run
echo Stop ComfyUI before installing this patch.
"%DIRECTOR_PYTHON%" -X utf8 install.py install %*
set "DIRECTOR_EXIT=%ERRORLEVEL%"
pause
exit /b %DIRECTOR_EXIT%
