; EVOSIA Connector — Inno Setup Installer Configuration
; P3b: Windows Installer Foundation
;
; Technology: Inno Setup 6+
; Scope: Per-user installation (no admin required)
; Install location: {localappdata}\Programs\EVOSIA Connector\

#define MyAppName "EVOSIA Connector"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Echoes & Visions"
#define MyAppURL "https://evosia-cloud.fly.dev"
#define MyAppExeName "evosia-connector.exe"
#define MyAppId "{{EVOSIA-Connector-0001-0000-0000-000000000000}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
; Per-user installation — no admin required
PrivilegesRequired=lowest
PrivilegesRequiredOverridingOwned
OutputDir=..\..\dist\connector\windows\installer
OutputBaseFilename=EVOSIA-Connector-{#MyAppVersion}-windows-x64-production-setup
Compression=lzma2/ultra64
SolidCompression=yes
; Modern UI
WizardStyle=modern
WizardSizePercent=110
; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Uninstall
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; Version info
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
; Signing (unsigned development build)
SignTool=
SignedUninstaller=no
; Disable unnecessary pages for simple installation
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableStartedPage=no
; License (if needed in future)
LicenseFile=
; Icon
SetupIconFile=
UninstallDisplaySize=0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Source: P3a PyInstaller directory bundle output
; This sources the entire directory bundle contents
Source: "..\..\dist\connector\windows\evosia-connector-0.1.0-windows-x64-production\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "Launch EVOSIA Connector"
Name: "{group}\{#MyAppName} Status"; Filename: "{app}\{#MyAppExeName}"; Parameters: "status"; Comment: "Show EVOSIA Connector status"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Launch after installation (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "Launch EVOSIA Connector"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove installed application files
Type: filesandordirs; Name: "{app}"

[UninstallRun]
; No special uninstall actions needed
; Credentials and logs are preserved (see documentation)

[Code]
// Pascal Script for Inno Setup
// P3b: Running-process handling and upgrade detection

function InitializeSetup: Boolean;
var
  ResultCode: Integer;
  ExistingPath: String;
begin
  Result := True;

  // Check if EVOSIA Connector is currently running
  // Use tasklist to check for evosia-connector processes
  if Exec('cmd.exe', '/c tasklist /FI "IMAGENAME eq evosia-connector.exe" 2>nul | find /I "evosia-connector.exe"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      // Process found — prompt user to close
      if MsgBox('EVOSIA Connector is currently running. Setup will close it to continue installation.' + #13#10 + #13#10 + 'Click OK to close EVOSIA Connector and continue.', mbConfirmation, MB_OKCANCEL) = IDOK then
      begin
        // Terminate the running process
        Exec('cmd.exe', '/c taskkill /F /IM evosia-connector.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        // Brief wait for process cleanup
        Sleep(1000);
      end
      else
      begin
        Result := False;
      end;
    end;
  end;
end;

function InitializeUninstall: Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  // Check if running during uninstall
  if Exec('cmd.exe', '/c tasklist /FI "IMAGENAME eq evosia-connector.exe" 2>nul | find /I "evosia-connector.exe"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      if MsgBox('EVOSIA Connector is currently running. Uninstall will close it.' + #13#10 + #13#10 + 'Click OK to close and uninstall.', mbConfirmation, MB_OKCANCEL) = IDOK then
      begin
        Exec('cmd.exe', '/c taskkill /F /IM evosia-connector.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        Sleep(1000);
      end
      else
      begin
        Result := False;
      end;
    end;
  end;
end;
