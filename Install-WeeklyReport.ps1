param(
    [string]$Time = "19:00"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Run Start-Dashboard.ps1 once before installing the weekly report."
}

$taskName = "Investor OS Weekly Macro Report"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$script = Join-Path $PSScriptRoot "weekly_report.py"
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Deep English Investor OS weekly macro report" -Force
Write-Host "Scheduled '$taskName' for Sundays at $Time."
