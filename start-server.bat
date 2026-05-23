@echo off
cd /d "%~dp0"
echo 启动本地服务器 ...
start http://localhost:8080/heart.html
python -m http.server 8080
pause
