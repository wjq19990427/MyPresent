@echo off
title MyPresent Launcher

rem === 根据本机环境修改以下两处路径 ===
rem   APP_PATH   : 项目根目录绝对路径
rem   CLOUDFLARED: cloudflared.exe 绝对路径
set APP_PATH=D:\MyPresent
set CLOUDFLARED=/d/cloudflared/cloudflared.exe

echo Starting MyPresent...
echo Local:  http://localhost:8501
echo Remote: https://mypresent.cloud
echo.
echo Press Ctrl+C in each window to stop.
echo.

start "MyPresent App" cmd /k "cd /d %APP_PATH% && python -m streamlit run app.py"
timeout /t 3 /nobreak > nul
start "Cloudflare Tunnel" cmd /k "%CLOUDFLARED% tunnel run mypresent"
