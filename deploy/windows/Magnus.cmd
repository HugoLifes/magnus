@echo off
rem Lanzador que instala MagnusSetup.exe: arranca el daemon si no esta corriendo y abre la app.
rem Estructura instalada: daemon\magnus.exe y app\magnus_desktop.exe junto a este archivo.
setlocal
set "URL=http://127.0.0.1:8420/health"

curl.exe -s -m 2 -o nul "%URL%" && goto abrir

start "Magnus daemon" /min "%~dp0daemon\magnus.exe" serve
for /l %%i in (1,1,30) do (
  curl.exe -s -m 2 -o nul "%URL%" && goto abrir
  ping -n 2 127.0.0.1 >nul
)
echo El daemon de Magnus no respondio en %URL%. Revisa la ventana "Magnus daemon".
pause
exit /b 1

:abrir
start "" "%~dp0app\magnus_desktop.exe"
