@echo off
REM ===========================================================================
REM  commands.bat  -  double-click entry for the algo_3 command menu.
REM  Thin door: it only launches the arrow-key menu in commands.ps1.
REM  Navigate with Up/Down, Enter to select, Esc to go back / quit.
REM ===========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0commands.ps1"
