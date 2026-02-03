@echo off
rem Wrapper to call the PowerShell merging script
if "%~1"=="" (
  echo Usage: merge_videos.bat ^"reference.mp4^" ^"output.mp4^" ^"other1.mp4^" [other2.mp4 ...]
  exit /b 1
)

set PS1=%~dp0merge_videos.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" "%~1" "%~2" %*
