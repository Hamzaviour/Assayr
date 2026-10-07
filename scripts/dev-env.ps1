# Dot-source this before running uv, npm or python: . .\scripts\dev-env.ps1
$root = (Resolve-Path "$PSScriptRoot\..").Path
$env:UV_CACHE_DIR = "$root\.cache\uv"
$env:UV_PYTHON_INSTALL_DIR = "$root\.cache\python"
$env:npm_config_cache = "$root\.cache\npm"
$env:TMP = "$root\.cache\tmp"; $env:TEMP = $env:TMP; $env:TMPDIR = $env:TMP
foreach ($d in @($env:UV_CACHE_DIR, $env:UV_PYTHON_INSTALL_DIR, $env:npm_config_cache, $env:TMP)) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}
