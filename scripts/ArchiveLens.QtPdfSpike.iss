#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
[Setup]
AppId={{E606963D-90B4-4A95-A96F-59989BE764E2}
AppName=ArchiveLens QtPdf Spike
AppVersion={#AppVersion}
AppPublisher=ArchiveLens contributors
DefaultDirName={localappdata}\Programs\ArchiveLens-QtPdf-Spike
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\release
OutputBaseFilename=ArchiveLens-{#AppVersion}-qtpdf-spike-setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ArchiveLens.exe
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\ArchiveLens\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
