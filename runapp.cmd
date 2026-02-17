@echo off
set "REPO_PY=%~dp0apps\ivan\.venv\Scripts\python.exe"
if exist "%REPO_PY%" (
  "%REPO_PY%" "%~dp0runapp" %*
) else (
  python "%~dp0runapp" %*
)
