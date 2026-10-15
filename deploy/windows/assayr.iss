; Assayr Windows installer.
; Build: ISCC /DVersion=0.3.0 /DStage=<stage dir> /DOutDir=<output dir> assayr.iss
#ifndef Version
  #error Pass /DVersion=x.y.z
#endif
#ifndef Stage
  #error Pass /DStage=<staging folder made by build.ps1>
#endif
#ifndef OutDir
  #define OutDir "."
#endif

[Setup]
; Never change AppId: upgrades find the existing installation through it.
AppId={{03AE51D2-794C-46E2-9883-A074E1623697}
AppName=Assayr
AppVersion={#Version}
AppVerName=Assayr {#Version}
AppPublisher=Assayr
DefaultDirName={autopf}\Assayr
DisableDirPage=auto
DisableProgramGroupPage=yes
OutputDir={#OutDir}
OutputBaseFilename=Assayr-Setup-{#Version}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
PrivilegesRequired=admin
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName=Assayr
UninstallDisplayIcon={app}\caddy\caddy.exe
CloseApplications=no
#ifdef SignTool
SignTool={#SignTool}
SignedUninstaller=yes
#endif

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[UninstallDelete]
; Files the services create at run time (service wrappers, Python caches, logs of WinSW).
Type: filesandordirs; Name: "{app}"

[Icons]
Name: "{autoprograms}\Assayr\Open Assayr"; Filename: "{code:SiteUrl}"
Name: "{autoprograms}\Assayr\Assayr Admin"; Filename: "{cmd}"; Parameters: "/k ""{app}\assayr-admin.cmd"" status"; WorkingDir: "{app}"
Name: "{autoprograms}\Assayr\Back up now"; Filename: "{cmd}"; Parameters: "/k ""{app}\assayr-admin.cmd"" backup"; WorkingDir: "{app}"

[Code]
const
  RegKey = 'SOFTWARE\Assayr';

type
  TMemoryStatusEx = record
    dwLength: DWORD;
    dwMemoryLoad: DWORD;
    ullTotalPhys: Int64;
    ullAvailPhys: Int64;
    ullTotalPageFile: Int64;
    ullAvailPageFile: Int64;
    ullTotalVirtual: Int64;
    ullAvailVirtual: Int64;
    ullAvailExtendedVirtual: Int64;
  end;

var
  ServerPage, AdminPage: TInputQueryWizardPage;
  CertPage, OptionsPage: TInputOptionWizardPage;
  CertFilesPage: TInputFileWizardPage;
  DataPage: TInputDirWizardPage;
  Upgrading, Silent, DeleteData, MovedAside, PostInstallRan: Boolean;
  OldVersion, OldDataDir, BackupFile: string;
  ExitCode: Integer;

function SetEnvironmentVariable(lpName, lpValue: string): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';
function GlobalMemoryStatusEx(var lpBuffer: TMemoryStatusEx): BOOL;
  external 'GlobalMemoryStatusEx@kernel32.dll stdcall';

{ ---------- helpers ---------- }

function Ini(Key, Default: string): string;
begin
  Result := GetIniString('Assayr', Key, Default, ExpandConstant('{param:CONFIG|}'));
end;

function VersionValue(V: string): Int64;
var
  Major, Minor, Patch, P: Integer;
begin
  P := Pos('.', V); Major := StrToIntDef(Copy(V, 1, P - 1), 0); Delete(V, 1, P);
  P := Pos('.', V); Minor := StrToIntDef(Copy(V, 1, P - 1), 0); Delete(V, 1, P);
  Patch := StrToIntDef(V, 0);
  Result := Int64(Major) * 1000000 + Minor * 1000 + Patch;
end;

function DataDir(Param: string): string;
begin
  if Upgrading then
    Result := OldDataDir
  else if Silent then
    Result := Ini('DataDir', ExpandConstant('{commonappdata}\Assayr'))
  else
    Result := DataPage.Values[0];
end;

function HttpsPort: string;
begin
  if Silent then Result := Ini('HttpsPort', '443') else Result := ServerPage.Values[2];
end;

function HttpPort: string;
begin
  if Silent then Result := Ini('HttpPort', '80') else Result := ServerPage.Values[3];
end;

function HostName: string;
begin
  if Silent then Result := Ini('Hostname', Lowercase(GetComputerNameString)) else Result := ServerPage.Values[0];
end;

function SiteUrl(Param: string): string;
begin
  if Upgrading then
    Result := 'https://localhost'
  else if Silent and (CompareText(Ini('WebMode', 'https'), 'http') = 0) then
    Result := 'http://' + HostName + ':' + HttpPort
  else
    Result := 'https://' + HostName + ':' + HttpsPort;
end;

function PortOwner(Port: string): string;
var
  Code: Integer;
  Tmp: string;
  Lines: TArrayOfString;
begin
  Result := '';
  Tmp := ExpandConstant('{tmp}\port-' + Port + '.txt');
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -Command "$c = Get-NetTCPConnection -State Listen -LocalPort ' + Port +
    ' -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) { (Get-Process -Id $c.OwningProcess).ProcessName | Out-File -Encoding ascii ''' + Tmp + ''' }"',
    '', SW_HIDE, ewWaitUntilTerminated, Code);
  if LoadStringsFromFile(Tmp, Lines) and (GetArrayLength(Lines) > 0) then
    Result := Trim(Lines[0]);
end;

function CheckPorts(Https, Http: string): string;
var
  Owner: string;
begin
  Result := '';
  Owner := PortOwner(Https);
  if Owner <> '' then
    Result := 'Port ' + Https + ' is used by ' + Owner + '. Choose another HTTPS port.';
  if Result = '' then begin
    Owner := PortOwner(Http);
    if Owner <> '' then
      Result := 'Port ' + Http + ' is used by ' + Owner + '. Choose another HTTP port.';
  end;
end;

function RunPython(Dir, Args: string): Integer;
var
  Code: Integer;
begin
  if not Exec(Dir + '\python\python.exe', '-m assayr win ' + Args, Dir, SW_HIDE, ewWaitUntilTerminated, Code) then
    Code := -1;
  Log('assayr win ' + Copy(Args, 1, Pos(' ', Args + ' ') - 1) + ' exited with ' + IntToStr(Code));
  Result := Code;
end;

procedure Report(Msg: string);
begin
  Log(Msg);
  SuppressibleMsgBox(Msg, mbCriticalError, MB_OK, IDOK);
end;

{ ---------- setup start ---------- }

function InitializeSetup: Boolean;
var
  Mem: TMemoryStatusEx;
  Installed, Problem: string;
  Limit: Int64;
begin
  Result := True;
  ExitCode := 0;
  if RegQueryStringValue(HKLM, RegKey, 'Version', Installed) then begin
    if VersionValue(Installed) > VersionValue('{#Version}') then begin
      SuppressibleMsgBox('Assayr ' + Installed + ' is installed, which is newer than {#Version}. ' +
        'Downgrading is not supported.', mbCriticalError, MB_OK, IDOK);
      Result := False;
    end;
    Exit;
  end;
  Mem.dwLength := SizeOf(Mem);
  Limit := 7800;
  Limit := Limit * 1048576;
  if GlobalMemoryStatusEx(Mem) then
    if (Mem.ullTotalPhys < Limit) and (SuppressibleMsgBox('This server has less than the recommended 8 GB of memory. Continue anyway?',
         mbConfirmation, MB_YESNO, IDYES) = IDNO) then
      Result := False;
  if Result and WizardSilent then begin
    Problem := CheckPorts(Ini('HttpsPort', '443'), Ini('HttpPort', '80'));
    if Problem <> '' then begin
      Log(Problem);
      Result := False;
    end;
  end;
end;

procedure InitializeWizard;
begin
  Silent := WizardSilent;
  Upgrading := RegQueryStringValue(HKLM, RegKey, 'Version', OldVersion) and
               RegQueryStringValue(HKLM, RegKey, 'DataDir', OldDataDir);

  ServerPage := CreateInputQueryPage(wpWelcome, 'Server', 'How users reach Assayr',
    'Enter the name users will type in the browser, your organisation and the ports.');
  ServerPage.Add('Hostname:', False);
  ServerPage.Add('Organisation name:', False);
  ServerPage.Add('HTTPS port:', False);
  ServerPage.Add('HTTP port (redirects to HTTPS):', False);
  ServerPage.Values[0] := Lowercase(GetComputerNameString);
  ServerPage.Values[2] := '443';
  ServerPage.Values[3] := '80';

  CertPage := CreateInputOptionPage(ServerPage.ID, 'HTTPS certificate', 'Which certificate should Assayr use?',
    'A self-signed certificate works at once, but browsers warn about it until you replace it.', True, False);
  CertPage.Add('Create a self-signed certificate');
  CertPage.Add('Use a certificate (.crt) and key (.key) from my certificate authority');
  CertPage.Add('Use a .pfx / .p12 file');
  CertPage.SelectedValueIndex := 0;

  CertFilesPage := CreateInputFilePage(CertPage.ID, 'Certificate files', 'Choose the files',
    'For a .pfx file leave the key empty; its password is asked for on the next page.');
  CertFilesPage.Add('Certificate (.crt, .pem, .pfx, .p12):',
    'Certificates|*.crt;*.pem;*.cer;*.pfx;*.p12|All files|*.*', '.crt');
  CertFilesPage.Add('Private key (.key):', 'Keys|*.key;*.pem|All files|*.*', '.key');

  AdminPage := CreateInputQueryPage(CertFilesPage.ID, 'First administrator',
    'Sign-in for the first administrator', 'The password must be at least 12 characters.');
  AdminPage.Add('Email:', False);
  AdminPage.Add('Password:', True);
  AdminPage.Add('Repeat password:', True);
  AdminPage.Add('PFX password (only for a .pfx file):', True);

  OptionsPage := CreateInputOptionPage(AdminPage.ID, 'Options', 'Malware scanning',
    'Scanning every upload with ClamAV needs about 2 GB of memory.', False, False);
  OptionsPage.Add('Scan uploaded evidence for malware (recommended)');
  OptionsPage.Values[0] := True;

  DataPage := CreateInputDirPage(OptionsPage.ID, 'Data folder', 'Where Assayr keeps its data',
    'The database, evidence files, certificates and backups go here. ' +
    'The folder is kept when Assayr is upgraded or uninstalled.', False, '');
  DataPage.Add('');
  DataPage.Values[0] := ExpandConstant('{commonappdata}\Assayr');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Upgrading and ((PageID = ServerPage.ID) or (PageID = CertPage.ID) or (PageID = CertFilesPage.ID) or
     (PageID = AdminPage.ID) or (PageID = OptionsPage.ID) or (PageID = DataPage.ID)) then
    Result := True
  else if (PageID = CertFilesPage.ID) and (CertPage.SelectedValueIndex = 0) then
    Result := True;
end;

function Inside(Child, Parent: string): Boolean;
begin
  { True when Child is Parent or a folder below it. }
  Child := Lowercase(AddBackslash(Child));
  Parent := Lowercase(AddBackslash(Parent));
  Result := Copy(Child, 1, Length(Parent)) = Parent;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Problem: string;
begin
  Result := True;
  if CurPageID = ServerPage.ID then begin
    if (Trim(ServerPage.Values[0]) = '') or (Trim(ServerPage.Values[1]) = '') then begin
      MsgBox('Enter the hostname and the organisation name.', mbError, MB_OK);
      Result := False;
    end else begin
      Problem := CheckPorts(ServerPage.Values[2], ServerPage.Values[3]);
      if Problem <> '' then begin
        MsgBox(Problem, mbError, MB_OK);
        Result := False;
      end;
    end;
  end else if CurPageID = CertFilesPage.ID then begin
    if not FileExists(CertFilesPage.Values[0]) then begin
      MsgBox('Choose the certificate file.', mbError, MB_OK);
      Result := False;
    end else if (CertPage.SelectedValueIndex = 1) and not FileExists(CertFilesPage.Values[1]) then begin
      MsgBox('Choose the private key file.', mbError, MB_OK);
      Result := False;
    end;
  end else if CurPageID = AdminPage.ID then begin
    if Pos('@', AdminPage.Values[0]) = 0 then begin
      MsgBox('Enter a valid email address.', mbError, MB_OK);
      Result := False;
    end else if Length(AdminPage.Values[1]) < 12 then begin
      MsgBox('The password must be at least 12 characters.', mbError, MB_OK);
      Result := False;
    end else if AdminPage.Values[1] <> AdminPage.Values[2] then begin
      MsgBox('The passwords do not match.', mbError, MB_OK);
      Result := False;
    end;
  end else if CurPageID = DataPage.ID then begin
    if Inside(DataPage.Values[0], WizardDirValue) or Inside(WizardDirValue, DataPage.Values[0]) then begin
      MsgBox('Choose a data folder separate from the program folder (' + WizardDirValue + '), ' +
        'for example ' + ExtractFileDrive(WizardDirValue) + '\AssayrData. Neither may be inside the other, ' +
        'because upgrades replace the program folder.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo,
  MemoGroupInfo, MemoTasksInfo: String): String;
begin
  if Upgrading then
    Result := 'Upgrade Assayr ' + OldVersion + ' to {#Version}.' + NewLine +
      'A backup is taken first. If the new version does not start, ' + OldVersion +
      ' and its data are put back automatically.'
  else
    Result := 'Install Assayr {#Version}' + NewLine + 'Data folder: ' + DataDir('') + NewLine +
      'Address: https://' + ServerPage.Values[0] + ':' + HttpsPort;
end;

{ ---------- install and upgrade ---------- }

function BoolStr(B: Boolean): string;
begin
  if B then Result := 'true' else Result := 'false';
end;

function JsonStr(S: string): string;
begin
  StringChangeEx(S, '\', '\\', True);
  StringChangeEx(S, '"', '\"', True);
  Result := '"' + S + '"';
end;

function WriteAnswers: string;
var
  Mode, CertFile, KeyFile, Host, Org, Email, WebMode: string;
  Scan, Proxy: Boolean;
begin
  if Silent then begin
    Host := Ini('Hostname', Lowercase(GetComputerNameString));
    Org := Ini('Organisation', 'My Organization');
    Email := Ini('AdminEmail', '');
    Mode := Ini('CertMode', 'self-signed');
    CertFile := Ini('CertFile', '');
    KeyFile := Ini('KeyFile', '');
    Scan := CompareText(Ini('MalwareScan', 'yes'), 'yes') = 0;
    WebMode := Ini('WebMode', 'https');
    Proxy := CompareText(Ini('BehindTlsProxy', 'no'), 'yes') = 0;
  end else begin
    Host := ServerPage.Values[0];
    Org := ServerPage.Values[1];
    Email := AdminPage.Values[0];
    case CertPage.SelectedValueIndex of
      0: Mode := 'self-signed';
      1: Mode := 'pem';
    else
      Mode := 'pfx';
    end;
    CertFile := CertFilesPage.Values[0];
    KeyFile := CertFilesPage.Values[1];
    Scan := OptionsPage.Values[0];
    WebMode := 'https';
    Proxy := False;
    SetEnvironmentVariable('ASSAYR_ADMIN_PASSWORD', AdminPage.Values[1]);
    SetEnvironmentVariable('ASSAYR_PFX_PASSWORD', AdminPage.Values[3]);
  end;
  Result := ExpandConstant('{tmp}\answers.json');
  SaveStringToFile(Result,
    '{"install_dir": ' + JsonStr(ExpandConstant('{app}')) + ', "data_dir": ' + JsonStr(DataDir('')) +
    ', "hostname": ' + JsonStr(Host) + ', "org_name": ' + JsonStr(Org) +
    ', "https_port": ' + HttpsPort + ', "http_port": ' + HttpPort + ', "web_mode": ' + JsonStr(WebMode) +
    ', "behind_tls_proxy": ' + BoolStr(Proxy) + ', "malware_scan": ' + BoolStr(Scan) +
    ', "version": "{#Version}", "admin_email": ' + JsonStr(Email) + ', "cert_mode": ' + JsonStr(Mode) +
    ', "cert_file": ' + JsonStr(CertFile) + ', "key_file": ' + JsonStr(KeyFile) + '}', False);
end;

procedure ClearSecrets;
begin
  SetEnvironmentVariable('ASSAYR_ADMIN_PASSWORD', '');
  SetEnvironmentVariable('ASSAYR_PFX_PASSWORD', '');
end;

procedure RecordInstall;
begin
  RegWriteStringValue(HKLM, RegKey, 'InstallDir', ExpandConstant('{app}'));
  RegWriteStringValue(HKLM, RegKey, 'DataDir', DataDir(''));
  RegWriteStringValue(HKLM, RegKey, 'Version', '{#Version}');
end;

function RenameWithRetry(FromDir, ToDir: string): Boolean;
var
  Attempt: Integer;
begin
  { Antivirus and indexer handles can hold a folder for a moment after the services stop. }
  Result := False;
  for Attempt := 1 to 10 do begin
    if RenameFile(FromDir, ToDir) then begin
      Result := True;
      Exit;
    end;
    Sleep(2000);
  end;
end;

function PutPreviousBack(App: string): Boolean;
var
  Attempt: Integer;
begin
  for Attempt := 1 to 10 do begin
    if DirExists(App) then DelTree(App, True, True, True);
    if not DirExists(App) then Break;
    Sleep(2000);
  end;
  Result := RenameWithRetry(App + '.previous', App);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  App, OutFile: string;
  Lines: TArrayOfString;
begin
  Result := '';
  if not Upgrading then Exit;
  App := ExpandConstant('{app}');
  OutFile := ExpandConstant('{tmp}\backup-path.txt');
  if RunPython(App, 'prepare-upgrade --data-dir "' + OldDataDir + '" --backup-out "' + OutFile + '"') <> 0 then begin
    Result := 'The backup before the upgrade failed, so nothing was changed. See ' + OldDataDir + '\install.log';
    Exit;
  end;
  if LoadStringsFromFile(OutFile, Lines) and (GetArrayLength(Lines) > 0) then
    BackupFile := Trim(Lines[0]);
  DelTree(App + '.previous', True, True, True);
  if not RenameWithRetry(App, App + '.previous') then begin
    RunPython(App, 'start --data-dir "' + OldDataDir + '"');
    Result := 'The old program folder could not be moved aside. Close any window using ' + App + ' and try again.';
  end else
    MovedAside := True;
end;

procedure FinishUpgrade(App: string);
begin
  if RunPython(App, 'finish-upgrade --data-dir "' + OldDataDir + '" --version {#Version} --install-dir "' +
     App + '"') = 0 then begin
    RecordInstall;
    DelTree(App + '.previous', True, True, True);
    Exit;
  end;
  ExitCode := 1;
  RunPython(App, 'stop --data-dir "' + OldDataDir + '"');
  if not PutPreviousBack(App) then begin
    Report('The upgrade to {#Version} failed and the previous program folder could not be put back. ' +
      'It is in ' + App + '.previous. See ' + OldDataDir + '\install.log');
    Exit;
  end;
  RunPython(App, 'rollback --data-dir "' + OldDataDir + '" --backup "' + BackupFile + '" --version ' + OldVersion +
    ' --install-dir "' + App + '"');
  Report('The upgrade to {#Version} failed, so Assayr ' + OldVersion + ' and its data have been put back. ' +
    'See ' + OldDataDir + '\install.log');
end;

procedure FirstInstall(App: string);
var
  Answers: string;
begin
  Answers := WriteAnswers;
  if RunPython(App, 'install --answers "' + Answers + '"') = 0 then
    RecordInstall
  else begin
    ExitCode := 1;
    Report('Assayr could not be set up. The step that failed is at the end of ' + DataDir('') +
      '\install.log (or ' + DataDir('') + '-install-failed.log when the data folder was removed). ' +
      'Fix the cause, then run this setup again.');
  end;
  DeleteFile(Answers);
  ClearSecrets;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then Exit;
  PostInstallRan := True;
  WizardForm.StatusLabel.Caption := 'Configuring Assayr. This takes a few minutes...';
  if Upgrading then
    FinishUpgrade(ExpandConstant('{app}'))
  else
    FirstInstall(ExpandConstant('{app}'));
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and (ExitCode <> 0) then begin
    WizardForm.FinishedHeadingLabel.Caption := 'Assayr was not set up';
    if Upgrading then
      WizardForm.FinishedLabel.Caption := 'The upgrade did not complete. See the message shown before and ' +
        OldDataDir + '\install.log.'
    else
      WizardForm.FinishedLabel.Caption := 'Setup could not configure Assayr. See the message shown before, ' +
        'fix the cause and run this setup again.';
  end;
end;

procedure DeinitializeSetup;
var
  App: string;
begin
  { An upgrade cancelled or failed during the file copy: put the old program back and start it. }
  if Upgrading and MovedAside and not PostInstallRan then begin
    App := ExpandConstant('{app}');
    if DirExists(App + '.previous') and PutPreviousBack(App) then
      RunPython(App, 'start --data-dir "' + OldDataDir + '"');
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := ExitCode;
end;

{ ---------- uninstall ---------- }

function InitializeUninstall: Boolean;
begin
  Result := True;
  DeleteData := CompareText(ExpandConstant('{param:DELETEDATA|no}'), 'yes') = 0;
  if not UninstallSilent then
    DeleteData := MsgBox('Also delete ALL Assayr data (database, evidence files, certificates and backups)?' + #13#10#13#10 +
      'Choose No to keep the data so Assayr can be reinstalled later. ' +
      'Take a backup first if you are unsure.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Code: Integer;
  Data, Args: string;
begin
  if CurUninstallStep <> usUninstall then Exit;
  if not RegQueryStringValue(HKLM, RegKey, 'DataDir', Data) then
    Data := ExpandConstant('{commonappdata}\Assayr');
  Args := '-m assayr win uninstall --data-dir "' + Data + '"';
  if DeleteData then Args := Args + ' --delete-data';
  Exec(ExpandConstant('{app}\python\python.exe'), Args, ExpandConstant('{app}'), SW_HIDE,
    ewWaitUntilTerminated, Code);
  RegDeleteKeyIncludingSubkeys(HKLM, RegKey);
end;
