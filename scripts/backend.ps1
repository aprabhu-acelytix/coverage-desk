param([ValidateSet('start','stop','restart','status')][string]$Action='status')
$ErrorActionPreference='Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$statePath = Join-Path $projectRoot 'data\backend.json'
function Get-CoverageProcess {
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $candidate = Get-CimInstance Win32_Process -Filter "ProcessId = $($state.pid)" -ErrorAction SilentlyContinue
        if ($candidate -and $candidate.CommandLine.Contains($pythonPath) -and $candidate.CommandLine -match '-m coverage_desk start') { return $candidate }
    }
    return $null
}
$running = Get-CoverageProcess
if ($Action -in @('stop','restart') -and $running) {
    Stop-Process -Id $running.ProcessId
    Write-Output 'Coverage Desk stopped.'
    $running = $null
}
if ($Action -in @('start','restart')) {
    if ($running) { Write-Output 'Coverage Desk is already running.'; exit 0 }
    New-Item -ItemType Directory -Force (Join-Path $projectRoot 'logs') | Out-Null
    Start-Process -FilePath $pythonPath -ArgumentList @('-m','coverage_desk','start') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'logs\backend-out.log') -RedirectStandardError (Join-Path $projectRoot 'logs\backend-error.log') | Out-Null
    Write-Output 'Coverage Desk starting. Check status in a few seconds.'
}
if ($Action -eq 'status') {
    if ($running) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        Write-Output "Coverage Desk running; Socket Mode readiness: $($state.ready); PID: $($state.pid)."
    } else { Write-Output 'Coverage Desk is stopped.' }
}
