@echo off
rem Usage: merge_folder.bat "C:\path\to\folder" "output.mp4" [reference.mp4]
if "%~1"=="" (
  echo Usage: merge_folder.bat ^"folder^" ^"output.mp4^" [reference.mp4]
  exit /b 1
)

set FOLDER=%~1
set OUTPUT=%~2
set REF=%~3

set PS1=%~dp0merge_folder.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" "%FOLDER%" "%OUTPUT%" "%REF%"
