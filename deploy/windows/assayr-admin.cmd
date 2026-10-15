@echo off
rem Assayr Admin: status, start, stop, restart, logs, backup, restore, create-admin, update-signatures
setlocal
set "ASSAYR_HOME=%~dp0"
for /f "usebackq tokens=2,*" %%A in (`reg query "HKLM\SOFTWARE\Assayr" /v DataDir 2^>nul ^| find "DataDir"`) do set "ASSAYR_DATA_DIR=%%B"
if not defined ASSAYR_DATA_DIR set "ASSAYR_DATA_DIR=%ProgramData%\Assayr"
set "ASSAYR_ENV_FILE=%ASSAYR_DATA_DIR%\assayr.env"
set "PYTHONUTF8=1"
if "%~1"=="" (
  "%ASSAYR_HOME%python\python.exe" -m assayr win --help
) else (
  "%ASSAYR_HOME%python\python.exe" -m assayr win %* --data-dir "%ASSAYR_DATA_DIR%"
)
exit /b %ERRORLEVEL%
