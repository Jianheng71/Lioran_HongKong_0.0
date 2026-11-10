#ifndef AppVersion
#define AppVersion "0.1.0"
#endif

[Setup]
AppId={{AB18A01E-FEAB-4C18-8519-FBBDA2D81623}
AppName=Lioran
AppVersion={#AppVersion}
AppPublisher=Jianheng71
DefaultDirName={autopf}\Lioran
DefaultGroupName=Lioran
UninstallDisplayIcon={app}\Lioran.exe
OutputDir=..\dist\installer
OutputBaseFilename=LioranSetup
SetupIconFile=generated-icons\lioran.ico
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "..\dist\Lioran\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Lioran"; Filename: "{app}\Lioran.exe"
Name: "{autodesktop}\Lioran"; Filename: "{app}\Lioran.exe"; Tasks: desktopicon
