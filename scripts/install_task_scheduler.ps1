param(
    [string]$TaskName = "kaa-scheduler-daily",
    [string]$StartTime = "05:30"
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$runScript = Join-Path $PSScriptRoot "run_manual.ps1"
$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runScript`""

Write-Host "Installing scheduled task '$TaskName' for $StartTime"
Write-Host "Command: $taskCommand"

schtasks /Create /TN $TaskName /SC DAILY /ST $StartTime /RL HIGHEST /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create scheduled task '$TaskName'."
}

Write-Host "Scheduled task installed successfully."
