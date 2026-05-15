param(
    [Parameter(Mandatory = $true)]
    [string]$JurorPath
)

$taskName = "AIHallucinationJuror"
$arguments = 'start --no-tui'
$workingDir = Split-Path -Parent $JurorPath

$action = New-ScheduledTaskAction -Execute $JurorPath -Argument $arguments -WorkingDirectory $workingDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Installed Task Scheduler entry: $taskName"
