#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif
[Setup]
AppId={{9EAB079B-E6F3-4E1C-A96F-56B7351CB60F}
AppName=ArchiveLens
AppVersion={#AppVersion}
AppPublisher=ArchiveLens contributors
DefaultDirName={localappdata}\Programs\ArchiveLens
DefaultGroupName=ArchiveLens
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\release
OutputBaseFilename=ArchiveLens-{#AppVersion}-setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ArchiveLens.exe
LicenseFile=..\LICENSE
ChangesAssociations=yes
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\ArchiveLens\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\ArchiveLens"; Filename: "{app}\ArchiveLens.exe"
Name: "{userdesktop}\ArchiveLens"; Filename: "{app}\ArchiveLens.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "ArchiveLens"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe\shell\open\command"; ValueType: string; ValueData: """{app}\ArchiveLens.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe\SupportedTypes"; ValueType: string; ValueName: ".zip"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe\SupportedTypes"; ValueType: string; ValueName: ".cbz"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe\SupportedTypes"; ValueType: string; ValueName: ".7z"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe\SupportedTypes"; ValueType: string; ValueName: ".rar"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe\SupportedTypes"; ValueType: string; ValueName: ".cbr"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\ArchiveLens.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""

Root: HKCU; Subkey: "Software\Classes\ArchiveLens.Archive"; ValueType: string; ValueData: "ArchiveLens image archive"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ArchiveLens.Archive\shell\open\command"; ValueType: string; ValueData: """{app}\ArchiveLens.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.zip\OpenWithProgids"; ValueType: string; ValueName: "ArchiveLens.Archive"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.cbz\OpenWithProgids"; ValueType: string; ValueName: "ArchiveLens.Archive"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.7z\OpenWithProgids"; ValueType: string; ValueName: "ArchiveLens.Archive"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.rar\OpenWithProgids"; ValueType: string; ValueName: "ArchiveLens.Archive"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.cbr\OpenWithProgids"; ValueType: string; ValueName: "ArchiveLens.Archive"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\ArchiveLens.Pdf"; ValueType: string; ValueData: "ArchiveLens PDF document"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ArchiveLens.Pdf\shell\open\command"; ValueType: string; ValueData: """{app}\ArchiveLens.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "ArchiveLens.Pdf"; ValueData: ""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\ArchiveLens.exe"; Description: "Launch ArchiveLens"; Flags: nowait postinstall skipifsilent
