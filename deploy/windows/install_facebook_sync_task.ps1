# Registers a daily Windows Task Scheduler job running the Facebook feed sync.
# Usage: .\install_facebook_sync_task.ps1 [-Time 04:30] [-Python C:\path\to\python.exe]
# Remove: Unregister-ScheduledTask -TaskName ImpactFacebookSync -Confirm:$false
param(
    [string]$Time = "04:30",
    [string]$Python = "python",
    [string]$TaskName = "ImpactFacebookSync"
)

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$action = New-ScheduledTaskAction -Execute $Python -Argument "-m app.modules.social_media.sync" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Task '$TaskName' registered: daily at $Time (working directory $root)"
