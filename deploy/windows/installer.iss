; Instalador de Magnus para Windows (Inno Setup 6). No lo compiles a mano:
; deploy\windows\build-installer.ps1 prepara las carpetas y llama a ISCC con estas variables.
;   AppVersion  versión que se muestra (p. ej. 0.9.0-beta.1)
;   StageDir    carpeta con app\, daemon\ y Magnus.cmd ya armados
;   OutputDir   dónde queda MagnusSetup-<versión>.exe

#ifndef AppVersion
  #error Falta /DAppVersion
#endif
#ifndef StageDir
  #error Falta /DStageDir
#endif
#ifndef OutputDir
  #error Falta /DOutputDir
#endif

[Setup]
AppId={{C9516896-FB89-4446-B8BC-5B5721308570}
AppName=Magnus
AppVersion={#AppVersion}
AppPublisher=Magnus
AppPublisherURL=https://github.com/HugoLifes/magnus
; Instalación por usuario, sin permisos de administrador: {autopf} es %LOCALAPPDATA%\Programs.
PrivilegesRequired=lowest
DefaultDirName={autopf}\Magnus
DefaultGroupName=Magnus
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=MagnusSetup-{#AppVersion}
SetupIconFile={#SourcePath}..\..\clients\desktop\windows\runner\resources\app_icon.ico
UninstallDisplayIcon={app}\app\magnus_desktop.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Magnus"; Filename: "{app}\Magnus.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app\magnus_desktop.exe"; Flags: runminimized
Name: "{group}\{cm:UninstallProgram,Magnus}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Magnus"; Filename: "{app}\Magnus.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app\magnus_desktop.exe"; Flags: runminimized; Tasks: desktopicon

[Run]
Filename: "{app}\Magnus.cmd"; Description: "{cm:LaunchProgram,Magnus}"; Flags: nowait postinstall skipifsilent runminimized

[UninstallRun]
; Cierra la app y el daemon de esta instalación (no toca otros magnus.exe del equipo) y
; espera a que salgan: si no, sus archivos siguen en uso y quedan sin borrar.
Filename: "powershell.exe"; Parameters: "-NoProfile -Command ""Get-Process magnus,magnus_desktop -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{app}\*' } | ForEach-Object {{ $_.Kill(); [void]$_.WaitForExit(10000) }"""; Flags: runhidden waituntilterminated; RunOnceId: "StopMagnus"

[Code]
function OllamaInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'))
    or FileExists(ExpandConstant('{commonpf}\Ollama\ollama.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent()) and (not OllamaInstalled()) then
  begin
    if MsgBox('Magnus usa Ollama para correr los modelos y no está instalado.' + #13#10 + #13#10 +
              '¿Instalarlo ahora con winget? (necesita internet)', mbConfirmation, MB_YESNO) = IDYES then
    begin
      if not Exec('winget', 'install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements',
                  '', SW_SHOW, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
        MsgBox('No se pudo instalar Ollama. Descárgalo de https://ollama.com/download', mbError, MB_OK);
    end;
  end;
end;
