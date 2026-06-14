param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

# ── Auto-elevate to administrator if not already ──
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Requesting administrator privileges..." -ForegroundColor Yellow
    # Prefer PowerShell 7 (pwsh.exe), fallback to Windows PowerShell 5.1 (powershell.exe)
    $shell = if (Get-Command pwsh.exe -ErrorAction SilentlyContinue) { "pwsh.exe" } else { "powershell.exe" }
    $startArgs = @{
        FilePath     = $shell
        Verb         = "RunAs"
        ArgumentList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath) + $Arguments
    }
    Start-Process @startArgs
    exit
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$packagePath = Join-Path $repoRoot "app"
$previousPythonPath = $env:PYTHONPATH

try {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        $env:PYTHONPATH = $packagePath
    }
    else {
        $env:PYTHONPATH = "$packagePath;$previousPythonPath"
    }

    Push-Location $repoRoot
    python -m kaa_scheduler run @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
