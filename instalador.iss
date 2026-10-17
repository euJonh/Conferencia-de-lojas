; Instalador da Conferência de Lojas (Inno Setup 6).
; Compile com build.bat, que gera o .exe antes. Saída: instalador\Instalar_ConferenciaLojas_<versão>.exe
;
; Instala por usuário em %LOCALAPPDATA%\Programs\ConferenciaLojas (sem pedir administrador),
; junto com o lojas.txt e o modelo PLANILHA DE PEDIDOS.xlsx, que o programa lê da própria pasta.

#define AppNome "Conferência de Lojas"
#define AppVersao "1.1"
#define AppExe "ConferenciaLojas.exe"
; Pasta onde está o .exe gerado pelo PyInstaller (pode trocar com ISCC /DPastaExe=...).
#ifndef PastaExe
  #define PastaExe "dist"
#endif

[Setup]
AppId={{737B89C0-F0E6-4AE4-8F1E-3F7E56E2B944}
AppName={#AppNome}
AppVersion={#AppVersao}
AppVerName={#AppNome} {#AppVersao}
DefaultDirName={userpf}\ConferenciaLojas
DefaultGroupName={#AppNome}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=instalador
OutputBaseFilename=Instalar_ConferenciaLojas_{#AppVersao}
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppNome}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Fecha o programa aberto antes de atualizar os arquivos.
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#PastaExe}\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "lojas.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "PLANILHA DE PEDIDOS.xlsx"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppNome}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppNome}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppNome}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppNome}}"; Flags: nowait postinstall skipifsilent
