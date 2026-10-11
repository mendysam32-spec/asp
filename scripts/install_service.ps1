# Installs Windows Task Scheduler task so agent survives reboot + runs in background
# Run as Administrator:  powershell -ExecutionPolicy Bypass -File scripts\install_service.ps1
# Or double-click start_hidden.vbs (no admin needed for current session)

$ErrorActionPreference = "Stop"
$BaseDir = (Resolve-Path "$PSScriptRoot\..").Path
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = "C:\Python314\python.exe" }
$Runner = Join-Path $BaseDir "run_background.py"
$TaskName = "ASPAgent"
$OldTaskNames = @("TheRepublicAgent")
$LogFile = Join-Path $BaseDir "data\agent.log"

Write-Host "BaseDir: $BaseDir"
Write-Host "Python: $Python"
Write-Host "Runner: $Runner"

if (-not (Test-Path $Runner)) { Write-Error "run_background.py not found at $Runner"; exit 1 }

# Check if running as admin for Task Scheduler registration
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdmin) {
    Write-Host "`n[1/3] Removing old task if exists..."
    try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
    foreach ($old in $OldTaskNames) {
        try { Unregister-ScheduledTask -TaskName $old -Confirm:$false -ErrorAction SilentlyContinue; Write-Host "  -> Removed legacy task '$old'" } catch {}
    }
    
    Write-Host "[2/3] Creating Task Scheduler task '$TaskName'..."
    $Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Runner`"" -WorkingDirectory $BaseDir
    $Trigger1 = New-ScheduledTaskTrigger -AtLogOn
    $Trigger2 = New-ScheduledTaskTrigger -AtStartup
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)
    $Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest
    
    # Use S4U so it runs whether user is logged in or not, without storing password
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger1,$Trigger2 -Settings $Settings -Principal $Principal -Description "ASP Agent (Agent SP) - dashboard + autonomous loop 24/7" | Out-Null
        Write-Host "  -> Task registered (logon + startup triggers, auto-restart on failure)"
    } catch {
        Write-Host "  -> S4U failed, trying interactive principal..."
        $Principal2 = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger1 -Settings $Settings -Principal $Principal2 -Description "ASP Agent (Agent SP)" | Out-Null
    }
    
    Write-Host "[3/3] Starting task now..."
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 3
    $state = (Get-ScheduledTask -TaskName $TaskName).State
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "`nTask State: $state"
    Write-Host "Last Run: $($info.LastRunTime)  Result: $($info.LastTaskResult) (0=ok, 267009=still running)"
    Write-Host "`nDone! Agent will now:"
    Write-Host "  - Start automatically on every boot/logon"
    Write-Host "  - Restart if it crashes"
    Write-Host "  - Run hidden in background"
    Write-Host "`nVerify: http://localhost:5001/api/health"
    Write-Host "Logs: $LogFile"
    Write-Host "Stop: powershell -File scripts\stop.ps1  or  Task Scheduler -> $TaskName -> End"
} else {
    Write-Host "`nNot running as Administrator - installing for CURRENT SESSION only (no boot persistence)."
    Write-Host "To get boot persistence, right-click PowerShell -> Run as Administrator, then re-run this script."
    Write-Host "`nStarting hidden background process now..."
    $vbs = Join-Path $PSScriptRoot "start_hidden.vbs"
    if (Test-Path $vbs) {
        Start-Process "wscript.exe" -ArgumentList "`"$vbs`""
        Write-Host "Started via start_hidden.vbs (pythonw, hidden window)"
    } else {
        Start-Process -FilePath $Python -ArgumentList "`"$Runner`"" -WindowStyle Hidden -WorkingDirectory $BaseDir
        Write-Host "Started via python Hidden window"
    }
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:5001/api/health" -TimeoutSec 5
        Write-Host "Health check OK: $($r | ConvertTo-Json -Depth 2)"
    } catch {
        Write-Host "Health check pending... check $LogFile in 10s, then http://localhost:5001"
    }
}
