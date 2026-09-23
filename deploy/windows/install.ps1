# Instala el daemon de Magnus en Windows para el usuario actual.
#
# No necesita permisos de administrador: todo va a %LOCALAPPDATA%\Magnus.
#   - copia Magnus (núcleo, daemon, CLI, skills y agentes incluidos)
#   - crea un entorno de Python propio y lo instala ahí
#   - deja `magnus serve` arrancando al iniciar sesión (sin ventana)
#
# Requisitos: Python 3.10+ y Ollama (https://ollama.com/download).
# Uso, desde la raíz del repo:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1 -NoAutostart

param(
    [string]$Source = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [switch]$NoAutostart
)

$ErrorActionPreference = 'Stop'
$MagnusHome = Join-Path $env:LOCALAPPDATA 'Magnus'
$AppDir = Join-Path $MagnusHome 'app'
$VenvDir = Join-Path $MagnusHome 'venv'

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }

# --- Python -----------------------------------------------------------------
Write-Step 'Buscando Python 3.10 o superior'
$python = $null
foreach ($candidate in @('py', 'python', 'python3')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { continue }
    $args = @()
    if ($candidate -eq 'py') { $args = @('-3') }
    $version = & $cmd.Source @args -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>$null
    if ($LASTEXITCODE -eq 0 -and [version]$version -ge [version]'3.10') {
        $python = @($cmd.Source) + $args
        Write-Host "    Python $version en $($cmd.Source)"
        break
    }
}
if ($null -eq $python) {
    throw 'No se encontró Python 3.10+. Instálalo con: winget install Python.Python.3.12'
}

# --- GPU y Ollama (solo avisos: Magnus funciona sin ellos, pero no sirve modelos) ---
if ($null -eq (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    Write-Warning 'No se encontró nvidia-smi: instala el driver de NVIDIA para usar la GPU.'
}
if ($null -eq (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Warning 'No se encontró Ollama. Instálalo con: winget install Ollama.Ollama'
}

# --- Copia ------------------------------------------------------------------
Write-Step "Copiando Magnus a $AppDir"
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
foreach ($item in @('core', 'daemon', 'cli', 'skills', 'agents')) {
    $target = Join-Path $AppDir $item
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Copy-Item -Recurse -Path (Join-Path $Source $item) -Destination $target
}
foreach ($file in @('pyproject.toml', 'requirements.txt', 'README.md')) {
    Copy-Item -Force -Path (Join-Path $Source $file) -Destination $AppDir
}

# --- Entorno de Python ------------------------------------------------------
Write-Step 'Creando el entorno de Python'
$pythonExe = $python[0]
$pythonArgs = @()
if ($python.Count -gt 1) { $pythonArgs = $python[1..($python.Count - 1)] }
& $pythonExe @pythonArgs -m venv $VenvDir
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de Python.' }

$venvPython = Join-Path $VenvDir 'Scripts\python.exe'
Write-Step 'Instalando dependencias (puede tardar un par de minutos)'
& $venvPython -m pip install --quiet --upgrade pip
# Editable: las skills y agentes incluidos se leen desde $AppDir.
& $venvPython -m pip install --quiet -e $AppDir
if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación de Magnus.' }

$magnusExe = Join-Path $VenvDir 'Scripts\magnus.exe'

# --- Arranque al iniciar sesión ----------------------------------------------
if (-not $NoAutostart) {
    Write-Step 'Configurando el arranque al iniciar sesión'
    $startup = [Environment]::GetFolderPath('Startup')
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path $startup 'Magnus daemon.lnk'))
    $shortcut.TargetPath = (Get-Command powershell).Source
    $shortcut.Arguments = "-NoProfile -WindowStyle Hidden -Command `"& '$magnusExe' serve`""
    $shortcut.WorkingDirectory = $MagnusHome
    $shortcut.Description = 'Magnus: API local en http://127.0.0.1:8420'
    $shortcut.Save()
}

# --- Comprobación -------------------------------------------------------------
Write-Step 'Comprobando el hardware'
& $magnusExe platform

Write-Host ''
Write-Host 'Magnus instalado.' -ForegroundColor Green
Write-Host "  Arrancar ahora:     & '$magnusExe' serve"
Write-Host "  Modelos que caben:  & '$magnusExe' catalog"
Write-Host "  Chat en terminal:   & '$magnusExe' chat <modelo>"
if (-not $NoAutostart) {
    Write-Host '  Arrancará solo al iniciar sesión (acceso directo en la carpeta Inicio).'
}
