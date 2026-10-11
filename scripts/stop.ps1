# Stop the background agent
$TaskName = "ASPAgent"
try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue; Write-Host "Stopped scheduled task $TaskName" } catch {}
try { Unregister-ScheduledTask -TaskName "TheRepublicAgent" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
# Kill any python running run_background.py
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_background.py*" } | ForEach-Object {
    Write-Host "Killing PID $($_.ProcessId): $($_.CommandLine)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
# Also kill waitress/pythonw orphan
Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*Python*" } | ForEach-Object {
    # only kill if its working dir is ai-agent (avoid killing other pythons)
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        if ($cmd -like "*ai-agent*") { 
            Write-Host "Killing orphan python PID $($_.Id)"
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue 
        }
    } catch {}
}
Write-Host "Done. Verify: netstat -ano | findstr 5001  should be empty"
