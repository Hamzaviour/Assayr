<#
.SYNOPSIS
  Assemble the Windows installer staging folder from pinned, hash-checked components.
.EXAMPLE
  .\deploy\windows\build.ps1 -Version 0.3.0 -Out E:\assayr-win-build -Signatures sigs
#>
param(
  [Parameter(Mandatory)] [ValidatePattern('^\d+\.\d+\.\d+$')] [string] $Version,
  [Parameter(Mandatory)] [string] $Out,
  [string] $Signatures = ""
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$components = Get-Content "$PSScriptRoot\components.json" -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force $Out | Out-Null
$Out = (Resolve-Path $Out).Path
$downloads = Join-Path $Out 'downloads'
$stage = Join-Path $Out 'stage'
New-Item -ItemType Directory -Force $downloads | Out-Null
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force $stage | Out-Null

function Get-Component([string] $name) {
  $c = $components.$name
  $file = Join-Path $downloads ([Uri]::UnescapeDataString([IO.Path]::GetFileName(([Uri]$c.url).AbsolutePath)))
  if (-not (Test-Path $file)) { Invoke-WebRequest $c.url -OutFile $file }
  $hash = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
  if ($hash -ne $c.sha256) { throw "$name download does not match its pinned SHA-256 (got $hash)" }
  return $file
}

function Expand-Fresh([string] $zip, [string] $dest) {
  if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
  Expand-Archive $zip $dest
}

# Python (relocatable build) with the backend and its locked dependencies
tar -xzf (Get-Component python) -C $stage
if ($LASTEXITCODE -or -not (Test-Path "$stage\python\python.exe")) { throw "python.exe missing after unpacking" }
Push-Location "$repo\backend"
try {
  if (Test-Path "$Out\wheel") { Remove-Item -Recurse -Force "$Out\wheel" }
  uv build --wheel --out-dir "$Out\wheel" | Out-Host
  if ($LASTEXITCODE) { throw "uv build failed" }
  uv export --frozen --no-dev --no-hashes --no-emit-project -o "$Out\requirements.txt" | Out-Null
  if ($LASTEXITCODE) { throw "uv export failed" }
} finally { Pop-Location }
$wheel = (Get-ChildItem "$Out\wheel\assayr-*.whl").FullName
& "$stage\python\python.exe" -m pip install --no-warn-script-location --disable-pip-version-check --no-cache-dir `
    -r "$Out\requirements.txt" $wheel | Out-Host
if ($LASTEXITCODE) { throw "pip install failed" }
foreach ($junk in 'Lib\test', 'Lib\idlelib', 'Lib\tkinter', 'tcl') {
  Remove-Item -Recurse -Force "$stage\python\$junk" -ErrorAction SilentlyContinue
}

# PostgreSQL: keep bin, lib and share only (no pgAdmin, docs, headers or symbols)
$tmp = Join-Path $Out 'pgsql-unpacked'
Expand-Fresh (Get-Component postgres) $tmp
New-Item -ItemType Directory "$stage\pgsql" | Out-Null
foreach ($d in 'bin', 'lib', 'share') { Copy-Item -Recurse "$tmp\pgsql\$d" "$stage\pgsql\$d" }
Get-ChildItem "$stage\pgsql" -Recurse -Include *.pdb | Remove-Item -Force
Remove-Item -Recurse -Force $tmp

# Caddy
Expand-Fresh (Get-Component caddy) "$stage\caddy"
Get-ChildItem "$stage\caddy" -Exclude caddy.exe | Remove-Item -Recurse -Force

# ClamAV, with signatures when given
$tmp = Join-Path $Out 'clamav-unpacked'
Expand-Fresh (Get-Component clamav) $tmp
$root = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
if (-not (Test-Path "$root\clamd.exe")) { throw "clamd.exe missing in the ClamAV archive" }
Copy-Item -Recurse $root "$stage\clamav"
Remove-Item -Recurse -Force $tmp
New-Item -ItemType Directory -Force "$stage\clamav\database" | Out-Null
if ($Signatures) { Copy-Item "$Signatures\*.c?d" "$stage\clamav\database\" }

# WinSW
New-Item -ItemType Directory "$stage\services" | Out-Null
Copy-Item (Get-Component winsw) "$stage\services\WinSW-x64.exe"

# Frontend
Push-Location "$repo\frontend"
try {
  npm ci --no-audit --no-fund | Out-Host
  if ($LASTEXITCODE) { throw "npm ci failed" }
  npm run build | Out-Host
  if ($LASTEXITCODE) { throw "frontend build failed" }
} finally { Pop-Location }
Copy-Item -Recurse "$repo\frontend\dist" "$stage\web"

Copy-Item "$PSScriptRoot\assayr-admin.cmd" $stage
Set-Content "$stage\VERSION" $Version -NoNewline -Encoding ascii
& "$stage\python\python.exe" -c "import assayr, sys; assert assayr.__version__ == sys.argv[1], assayr.__version__" $Version
if ($LASTEXITCODE) { throw "The packaged backend is not version $Version" }
Write-Host "Staged Assayr $Version in $stage"
