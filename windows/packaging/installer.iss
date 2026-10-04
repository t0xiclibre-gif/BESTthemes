; Installateur BESTthemes (Inno Setup 6) — installation par utilisateur, sans droits admin.
;   iscc windows\packaging\installer.iss
#define AppName "BESTthemes"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F1C2B8E-5A43-4C7E-9B0E-BE57BE57BE57}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=BESTthemes
AppPublisherURL=https://github.com/t0xiclibre-gif/BESTthemes
AppSupportURL=https://github.com/t0xiclibre-gif/BESTthemes/issues
DefaultDirName={localappdata}\Programs\BESTthemes
DefaultGroupName=BESTthemes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=BESTthemes-Setup-{#AppVersion}
SetupIconFile=..\bestthemes_win\data\bestthemes.ico
UninstallDisplayIcon={app}\BESTthemes.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "..\..\dist\BESTthemes\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\BESTthemes"; Filename: "{app}\BESTthemes.exe"
Name: "{autodesktop}\BESTthemes"; Filename: "{app}\BESTthemes.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BESTthemes.exe"; Description: "Lancer BESTthemes"; Flags: nowait postinstall skipifsilent
