<#
.SYNOPSIS
  End-to-end test of the Windows installer on a clean Windows Server (run as Administrator, PowerShell 7).
.EXAMPLE
  ./e2e.ps1 -Setup dist\Assayr-Setup-0.3.0.exe -Newer dist\test\Assayr-Setup-99.0.0.exe -Broken dist\test\Assayr-Setup-99.1.0.exe
#>
param(
  [Parameter(Mandatory)] [string] $Setup,
  [Parameter(Mandatory)] [string] $Newer,
  [Parameter(Mandatory)] [string] $Broken
)
$ErrorActionPreference = 'Stop'
$Data = 'C:\ProgramData\Assayr'
$App = "$env:ProgramFiles\Assayr"
# Windows (http.sys) often holds port 80 on servers, as on the CI runner: use other ports, as a customer would.
$Base = 'https://localhost:8443'
$Email = 'e2e@example.com'
$env:ASSAYR_ADMIN_PASSWORD = 'e2e-password-123'
$Services = 'AssayrDb', 'AssayrClamAV', 'AssayrApi', 'AssayrWorker', 'AssayrWeb'

function Step([string] $name) { Write-Host "`n=== $name" }

function Fail([string] $msg) {
  Write-Host "FAILED: $msg"
  if (Test-Path "$Data\install.log") { Write-Host '== install.log'; Get-Content "$Data\install.log" -Tail 150 }
  if (Test-Path "$env:TEMP\setup.log") { Write-Host '== setup.log'; Get-Content "$env:TEMP\setup.log" -Tail 80 }
  Get-ChildItem "$Data\logs" -Filter *.log -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "== $($_.Name)"; Get-Content $_.FullName -Tail 40
  }
  Get-Service Assayr* -ErrorAction SilentlyContinue | Format-Table -AutoSize | Out-String | Write-Host
  exit 1
}

# Wait for the given program only, with a time limit. (PowerShell 7's Start-Process -Wait also waits for every
# descendant process, so it can hang on processes the install leaves running.)
function Wait-Program([string] $exe, [string[]] $argv, [int] $minutes = 20) {
  $p = Start-Process (Resolve-Path $exe) -ArgumentList $argv -PassThru
  if (-not $p.WaitForExit($minutes * 60 * 1000)) { Fail "$exe did not finish within $minutes minutes" }
  return $p.ExitCode
}

function Run-Setup([string] $exe, [string[]] $extra) {
  $argv = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=$env:TEMP\setup.log") + $extra
  return Wait-Program $exe $argv
}

# Services can still be starting for a few seconds after a setup returns: retry before failing.
function Health {
  for ($i = 1; $i -le 30; $i++) {
    try { return Invoke-RestMethod "$Base/api/v1/healthz" -SkipCertificateCheck -TimeoutSec 10 }
    catch { if ($i -eq 30) { throw } ; Start-Sleep -Seconds 4 }
  }
}

function Session {
  $s = $null
  $body = @{ email = $Email; password = $env:ASSAYR_ADMIN_PASSWORD } | ConvertTo-Json
  Invoke-RestMethod "$Base/api/v1/auth/login" -Method Post -Body $body -ContentType 'application/json' `
    -SessionVariable s -SkipCertificateCheck | Out-Null
  return $s
}

function Risk-Count($s) { @(Invoke-RestMethod "$Base/api/v1/risks" -WebSession $s -SkipCertificateCheck).Count }

function New-Risk($s, [string] $title) {
  $csrf = ($s.Cookies.GetCookies($Base) | Where-Object Name -eq 'assayr_csrf').Value
  Invoke-RestMethod "$Base/api/v1/risks" -Method Post -WebSession $s -SkipCertificateCheck `
    -Headers @{ 'X-CSRF-Token' = $csrf } -ContentType 'application/json' -Body (@{ title = $title } | ConvertTo-Json) | Out-Null
}

function Admin([string[]] $cmd) {
  & "$App\python\python.exe" -m assayr win @cmd --data-dir $Data
  if ($LASTEXITCODE) { Fail "assayr win $($cmd -join ' ')" }
}

# Windows Defender would quarantine the EICAR test upload before ClamAV sees it (README-INSTALL-WINDOWS: exclusions).
Add-MpPreference -ExclusionPath $Data -ErrorAction SilentlyContinue

$answers = "$env:TEMP\answers.ini"
@"
[Assayr]
Hostname=localhost
Organisation=E2E Org
AdminEmail=$Email
CertMode=self-signed
MalwareScan=yes
HttpsPort=8443
HttpPort=8080
"@ | Set-Content $answers -Encoding ascii

Step 'Silent install'
if ((Run-Setup $Setup @("/CONFIG=$answers")) -ne 0) { Fail 'setup exit code' }
if ((Health).status -ne 'ok') { Fail 'unhealthy after install' }
foreach ($name in $Services) {
  $svc = Get-CimInstance Win32_Service -Filter "Name='$name'"
  if (-not $svc) { Fail "$name is not registered" }
  if ($svc.State -ne 'Running') { Fail "$name is $($svc.State)" }
  if ($svc.StartName -ne "NT SERVICE\$name") { Fail "$name runs as $($svc.StartName)" }
}
$pg = Get-NetTCPConnection -LocalPort 5432 -State Listen
if ($pg.LocalAddress | Where-Object { $_ -ne '127.0.0.1' }) { Fail 'PostgreSQL listens beyond localhost' }
if ((curl.exe -s -o NUL -w '%{http_code}' http://localhost:8080/) -ne '301') { Fail 'HTTP does not redirect to HTTPS' }
if ((Get-ItemProperty HKLM:\SOFTWARE\Assayr).Version -notmatch '^\d+\.\d+\.\d+$') { Fail 'registry Version missing' }
if (Select-String -Path "$Data\install.log" -Pattern $env:ASSAYR_ADMIN_PASSWORD -SimpleMatch -Quiet) { Fail 'password in install.log' }

Step 'Sign in, upload evidence, EICAR rejected'
& "$App\python\python.exe" "$PSScriptRoot\e2e_evidence.py" $Base $Email $env:ASSAYR_ADMIN_PASSWORD
if ($LASTEXITCODE) { Fail 'evidence checks' }

Step 'Backup, change, restore'
$s = Session
New-Risk $s 'Before the backup'
$before = Risk-Count $s
Admin @('backup')
$backup = Get-ChildItem "$Data\backups\assayr-*.tar.gz" | Sort-Object LastWriteTime | Select-Object -Last 1
New-Risk $s 'After the backup'
Admin @('restore', $backup.FullName, '--yes')
if ((Health).status -ne 'ok') { Fail 'unhealthy after restore' }
$s = Session
if ((Risk-Count $s) -ne $before) { Fail "restore did not bring back $before risks" }

Step 'Upgrade to a newer version'
if ((Run-Setup $Newer @()) -ne 0) { Fail 'upgrade exit code' }
if ((Health).version -ne '99.0.0') { Fail "version after upgrade: $((Health).version)" }
$s = Session
if ((Risk-Count $s) -ne $before) { Fail 'data lost in the upgrade' }

Step 'A broken upgrade rolls back'
if ((Run-Setup $Broken @()) -eq 0) { Fail 'the broken upgrade reported success' }
if ((Health).version -ne '99.0.0') { Fail 'rollback did not bring back 99.0.0' }
if ((Get-ItemProperty HKLM:\SOFTWARE\Assayr).Version -ne '99.0.0') { Fail 'registry version after rollback' }
$s = Session
if ((Risk-Count $s) -ne $before) { Fail 'data lost in the rollback' }

Step 'Uninstall keeps the data'
$unins = Get-ChildItem "$App\unins*.exe" | Select-Object -First 1
Wait-Program $unins.FullName @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') | Out-Null
if (Get-Service Assayr* -ErrorAction SilentlyContinue) { Fail 'services still registered after uninstall' }
if (-not (Test-Path "$Data\db\PG_VERSION")) { Fail 'the data folder was removed' }
if (Test-Path HKLM:\SOFTWARE\Assayr) { Fail 'registry key left behind' }

Step 'Reinstall over the kept data'
if ((Run-Setup $Newer @("/CONFIG=$answers")) -ne 0) { Fail 'reinstall exit code' }
$s = Session
if ((Risk-Count $s) -ne $before) { Fail 'data not picked up by the reinstall' }

Write-Host "`nAll Windows end-to-end checks passed."
