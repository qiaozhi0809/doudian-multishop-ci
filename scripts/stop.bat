@echo off
chcp 65001 >nul
rem 双击停止本机服务（实际逻辑在 stop.ps1）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
if errorlevel 1 pause
