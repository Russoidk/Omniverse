$ErrorActionPreference = 'Stop'
$downloadUrl = 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe'
$destination = Join-Path $PSScriptRoot 'build\python-3.14.10-amd64.exe'
$expectedHash = '92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965'

if (Test-Path -LiteralPath $destination) {
    $existingHash = (Get-FileHash -Path $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($existingHash -eq $expectedHash) {
        Write-Host 'El instalador de Python ya existe y su SHA-256 es correcto.'
        exit 0
    }
    Remove-Item -LiteralPath $destination -Force
}

Write-Host 'Descargando Python 3.14.10 desde python.org...'
Invoke-WebRequest -Uri $downloadUrl -OutFile $destination
$actualHash = (Get-FileHash -Path $destination -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) {
    Remove-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
    throw 'La verificación SHA-256 del instalador de Python no coincide. Se canceló la compilación.'
}
Write-Host 'Python descargado y verificado correctamente.'
