param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

Set-Location $RepoRoot

$versionLine = Select-String -Path "backend\pyproject.toml" -Pattern '^version = ' | Select-Object -First 1
$version = if ($versionLine) { $versionLine.Line -replace '.*"(.*)".*', '$1' } else { "0.0.0" }
$zipName = "Binderdash-$version-win64.zip"

if (-not (Test-Path "backend\static")) {
    Write-Host "Building frontend..."
    Push-Location frontend
    pnpm install
    pnpm run build
    Pop-Location
}

Write-Host "Installing dependencies..."
uv pip install -r backend/requirements.txt
uv pip install pywebview pyinstaller

Write-Host "Running PyInstaller..."
pyinstaller --noconfirm desktop/binderdash.spec

$distDir = Join-Path $RepoRoot "dist\Binderdash"
if (-not (Test-Path $distDir)) {
    throw "Expected dist\Binderdash after PyInstaller build"
}

$readme = @"
Binderdash (Windows)

1. Unzip this folder anywhere.
2. Run Binderdash.exe.

Requires Microsoft Edge WebView2 runtime:
https://developer.microsoft.com/en-us/microsoft-edge/webview2/

If SmartScreen warns about an unsigned app, choose More info → Run anyway.
"@

$staging = Join-Path $RepoRoot "dist\windows-staging"
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Path $staging | Out-Null
Copy-Item -Recurse $distDir (Join-Path $staging "Binderdash")
Set-Content -Path (Join-Path $staging "README.txt") -Value $readme -Encoding UTF8

$zipPath = Join-Path $RepoRoot "dist\$zipName"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath

Write-Host "Created $zipPath"
