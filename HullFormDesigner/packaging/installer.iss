; Inno Setup script (https://jrsoftware.org/isinfo.php): per-user installer for the folder built by
; build_exe.bat. Open this file in Inno Setup and press Compile; the setup .exe appears in dist\.
#define AppName "Parametric Hull Form Designer"
#define AppVersion "0.1.0"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=probPST
DefaultDirName={localappdata}\Programs\HullFormDesigner
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=HullFormDesigner-{#AppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\HullFormDesigner.exe

[Files]
Source: "..\dist\HullFormDesigner\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\HullFormDesigner.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\HullFormDesigner.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\HullFormDesigner.exe"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
