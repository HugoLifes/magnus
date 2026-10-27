# Genera MagnusSetup-<versión>.exe: un instalador de Windows que no necesita Python ni Flutter.
#
#   1. congela el daemon con PyInstaller (Python va dentro de daemon\)
#   2. compila la app de escritorio con Flutter
#   3. junta app\, daemon\ y el lanzador Magnus.cmd en build\installer\stage
#   4. llama a Inno Setup (deploy\windows\installer.iss)
#
# Requisitos en la máquina que compila: Python 3.10+, Flutter con soporte de Windows,
# Visual Studio Build Tools con C++ e Inno Setup 6 (winget install JRSoftware.InnoSetup).
# Uso, desde la raíz del repo:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\build-installer.ps1

param(
    [string]$Version = '0.9.0-beta.1',
    [switch]$SkipFlutter
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Build = Join-Path $Root 'build\installer'
$Stage = Join-Path $Build 'stage'
$Desktop = Join-Path $Root 'clients\desktop'

function Write-Step([string]$Text) { Write-Host "==> $Text" -ForegroundColor Cyan }

function Find-Tool([string]$Name, [string[]]$Candidates) {
    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "No se encontró $Name."
}

$iscc = Find-Tool 'ISCC.exe' @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'))

# --- 1. Daemon congelado ------------------------------------------------------
Write-Step 'Preparando el entorno de Python para compilar'
$venv = Join-Path $Build 'venv'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $python)) {
    & py -3 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de Python.' }
}
& $python -m pip install --quiet --disable-pip-version-check -e $Root pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación de dependencias.' }

Write-Step 'Congelando el daemon con PyInstaller'
$pyinstaller = Join-Path $venv 'Scripts\pyinstaller.exe'
# skills\ y agents\ se leen relativas a core\ (core/skills.py, core/agent.py), así que van
# junto al código dentro de _internal\. uvicorn carga daemon.app por nombre y keyring busca
# sus backends por metadatos: por eso los --collect-submodules y --copy-metadata.
& $pyinstaller --noconfirm --clean --log-level WARN --name magnus --console `
    --distpath (Join-Path $Build 'pyinstaller\dist') `
    --workpath (Join-Path $Build 'pyinstaller\work') `
    --specpath (Join-Path $Build 'pyinstaller') `
    --paths $Root `
    --add-data "$Root\skills;skills" --add-data "$Root\agents;agents" `
    --collect-submodules core --collect-submodules daemon --collect-submodules cli `
    --collect-submodules cloud --collect-submodules uvicorn --collect-submodules keyring `
    --copy-metadata keyring --copy-metadata magnus `
    (Join-Path $PSScriptRoot 'magnus_entry.py')
if ($LASTEXITCODE -ne 0) { throw 'Falló PyInstaller.' }

# --- 2. App de escritorio -----------------------------------------------------
$release = Join-Path $Desktop 'build\windows\x64\runner\Release'
if (-not $SkipFlutter) {
    Write-Step 'Compilando la app de escritorio'
    Push-Location $Desktop
    try {
        & flutter build windows --release
        if ($LASTEXITCODE -ne 0) { throw 'Falló flutter build windows.' }
    } finally {
        Pop-Location
    }
}
if (-not (Test-Path (Join-Path $release 'magnus_desktop.exe'))) {
    throw "No está la app compilada en $release."
}

# --- 3. Carpeta a instalar ----------------------------------------------------
Write-Step "Armando $Stage"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
Copy-Item -Recurse $release (Join-Path $Stage 'app')
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Stage 'app\*.msix')
Copy-Item -Recurse (Join-Path $Build 'pyinstaller\dist\magnus') (Join-Path $Stage 'daemon')
Copy-Item (Join-Path $PSScriptRoot 'Magnus.cmd') $Stage

# La app de Flutter necesita el runtime de C++ (msvcp140.dll y compañía). Se copia junto
# al .exe (despliegue local, permitido por Microsoft) para no depender del VC++ Redist.
$crt = Get-ChildItem -Directory -ErrorAction SilentlyContinue `
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\*\VC\Redist\MSVC\*\x64\Microsoft.VC143.CRT",
    "$env:ProgramFiles\Microsoft Visual Studio\2022\*\VC\Redist\MSVC\*\x64\Microsoft.VC143.CRT" |
    Sort-Object FullName | Select-Object -Last 1
if ($null -eq $crt) { throw 'No se encontró el runtime de C++ de Visual Studio (Microsoft.VC143.CRT).' }
foreach ($dll in @('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')) {
    Copy-Item (Join-Path $crt.FullName $dll) (Join-Path $Stage 'app')
}

# --- 4. Instalador ------------------------------------------------------------
Write-Step 'Generando el instalador con Inno Setup'
& $iscc /Qp "/DAppVersion=$Version" "/DStageDir=$Stage" "/DOutputDir=$Build" (Join-Path $PSScriptRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Falló Inno Setup.' }

$setup = Join-Path $Build "MagnusSetup-$Version.exe"
Write-Host ''
Write-Host "Instalador listo: $setup" -ForegroundColor Green
