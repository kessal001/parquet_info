param([string]$CommandDirectory = $PSScriptRoot, [switch]$Remove)
$ErrorActionPreference = 'Stop'
$taskDirectory = [IO.Path]::GetFullPath($CommandDirectory).TrimEnd('\')
if (-not $Remove -and -not (Test-Path -LiteralPath (Join-Path $taskDirectory 'parquet.exe') -PathType Leaf)) {
    throw "parquet.exe not found in $taskDirectory"
}
# Read only the user PATH; never write the merged machine PATH into it.
$taskOldPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$taskParts = @($taskOldPath -split ';' | Where-Object { $_ -and [Environment]::ExpandEnvironmentVariables($_).TrimEnd('\') -ine $taskDirectory })
if (-not $Remove) { $taskParts += $taskDirectory }
$taskNewPath = $taskParts -join ';'
if ($taskOldPath -cne $taskNewPath) {
    [Environment]::SetEnvironmentVariable('Path', $taskNewPath, 'User')
    if (-not ('ParquetPath.Broadcast' -as [type])) {
        Add-Type -Namespace ParquetPath -Name Broadcast -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll", SetLastError=true, CharSet=System.Runtime.InteropServices.CharSet.Unicode)]
public static extern System.IntPtr SendMessageTimeout(System.IntPtr hWnd, uint msg, System.UIntPtr wParam, string lParam, uint flags, uint timeout, out System.UIntPtr result);
'@
    }
    $taskResult = [UIntPtr]::Zero
    [void][ParquetPath.Broadcast]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 3000, [ref]$taskResult)
}
$taskCurrentParts = @($env:Path -split ';' | Where-Object { $_ -and $_.TrimEnd('\') -ine $taskDirectory })
if (-not $Remove) { $taskCurrentParts += $taskDirectory }
$env:Path = $taskCurrentParts -join ';'
if ($Remove) { Write-Output 'Command directory removed from user PATH.' }
else { Write-Output "Command installed: $taskDirectory\parquet.exe. Open a new CMD window and run parquet." }
