param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..\dist\windows'))
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = 'python' }
Push-Location $taskRoot
try {
    & $taskPython scripts/generate_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
    $taskIcon = Join-Path $taskRoot 'assets\parquet-info.ico'
    & $taskPython -m PyInstaller --noconfirm --clean --onefile --console --name parquet --icon $taskIcon --hidden-import pyarrow._parquet --hidden-import pyarrow._compute --exclude-module pyarrow.tests --exclude-module pytest --exclude-module PIL --exclude-module tkinter --distpath $OutputDirectory --workpath build/windows --specpath build parquet_windows.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows executable build failed' }
    $taskOutput = [IO.Path]::GetFullPath($OutputDirectory)
    Copy-Item -LiteralPath 'examples/demo_inventory.parquet' -Destination $taskOutput
    Copy-Item -LiteralPath 'LICENSE' -Destination $taskOutput
    Copy-Item -LiteralPath 'docs/LEGGIMI-WINDOWS.txt' -Destination $taskOutput
    Copy-Item -LiteralPath 'scripts/install-command.ps1' -Destination $taskOutput
    $taskHash = Get-FileHash -LiteralPath (Join-Path $taskOutput 'parquet.exe') -Algorithm SHA256
    [IO.File]::WriteAllText((Join-Path $taskOutput 'SHA256SUMS.txt'), ($taskHash.Hash.ToLowerInvariant() + '  parquet.exe' + [Environment]::NewLine))
    Write-Output "Built $taskOutput\parquet.exe"
} finally { Pop-Location }
