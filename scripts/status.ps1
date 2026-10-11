# Quick status check
$TaskName = "TheRepublicAgent"
Write-Host "=== Task Scheduler ==="
try {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $i = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "Task: $($t.TaskName)  State: $($t.State)"
    Write-Host "LastRun: $($i.LastRunTime)  Result: $($i.LastTaskResult)  Next: $($i.NextRunTime)"
} catch { Write-Host "Task $TaskName not found (not installed as boot service yet)" }

Write-Host "`n=== Process ==="
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_background.py*" } | Format-Table ProcessId, CreationDate, CommandLine -AutoSize
if (-not (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_background.py*" })) { Write-Host "(no run_background.py process found)" }

Write-Host "`n=== Port 5001 ==="
netstat -ano | findstr ":5001"

Write-Host "`n=== Health ==="
try {
    $h = Invoke-RestMethod -Uri "http://localhost:5001/api/health" -TimeoutSec 5
    $h | ConvertTo-Json -Depth 4
} catch { Write-Host "Health check failed: $_" }

Write-Host "`n=== Logs (last 20) ==="
$log = Join-Path (Resolve-Path "$PSScriptRoot\..").Path "data\agent.log"
if (Test-Path $log) { Get-Content $log -Tail 20 } else { Write-Host "No log file yet at $log" }
