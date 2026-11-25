@echo off
chcp 65001 >nul
rem 双击启动本机服务（实际逻辑在 start.ps1）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if errorlevel 1 pause
