# Fallback for update-data.yml's cron (GitHub skips most */15 schedules): run from the
# Windows Task Scheduler every 20 minutes. Compares the tracker's HEAD with the commit the
# site last processed (data/tracker_head.txt on GitHub) and, if the tracker moved and no
# update is already queued or running, dispatches update-data.yml. Needs git + an authed gh.
#
#   register:  powershell -ExecutionPolicy Bypass -File tools\watch_tracker.ps1 -Register
#   remove:    Unregister-ScheduledTask -TaskName CyclopeanTrackerWatch -Confirm:$false
param([switch]$Register)

$ErrorActionPreference = 'Stop'
$Tracker = 'https://github.com/SteamTracking/GameTracking-Deadlock.git'
$Repo = 'sikleq/Cyclopean'
$TaskName = 'CyclopeanTrackerWatch'
$LogDir = Join-Path $env:LOCALAPPDATA 'cyclopean'
$Log = Join-Path $LogDir 'watch_tracker.log'

function Write-Log([string]$msg) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Out-File -FilePath $Log -Append -Encoding utf8
    # keep the log small
    $lines = Get-Content $Log -ErrorAction SilentlyContinue
    if ($lines.Count -gt 500) { $lines | Select-Object -Last 300 | Set-Content $Log -Encoding utf8 }
}

if ($Register) {
    # conhost --headless: no console window flashes every 20 minutes
    $taskArgs = "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $action = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument $taskArgs
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 20)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
        -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Description 'Cyclopean: dispatch update-data when the Deadlock tracker has a new build' -Force | Out-Null
    Write-Host "registered $TaskName (every 20 min); log: $Log"
    exit 0
}

try {
    $head = ((git ls-remote $Tracker HEAD) -split "`t")[0]
    if (-not $head) { Write-Log 'ls-remote returned nothing'; exit 1 }
    $last = (gh api "repos/$Repo/contents/data/tracker_head.txt" -H 'Accept: application/vnd.github.raw' | Out-String).Trim()
    if ($head -eq $last) { exit 0 }                       # nothing new: stay silent
    $busy = gh run list --repo $Repo --workflow update-data.yml --limit 5 --json status `
        -q '[.[] | select(.status != "completed")] | length'
    if ([int]$busy -gt 0) { Write-Log "tracker $($head.Substring(0,8)) new; update already running"; exit 0 }
    gh workflow run update-data.yml --repo $Repo | Out-Null
    Write-Log "tracker moved $($last.Substring(0, [Math]::Min(8, $last.Length))) -> $($head.Substring(0,8)): dispatched update-data"
} catch {
    Write-Log "error: $($_.Exception.Message)"
    exit 1
}
