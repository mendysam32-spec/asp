' Double-click this to start agent in background with NO visible window
' Uses pythonw.exe so no console pops up
Set WshShell = CreateObject("WScript.Shell")
BaseDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
BaseDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(BaseDir)
PythonW = "C:\Python314\pythonw.exe"
Runner = BaseDir & "\run_background.py"

' Fallback to pythonw in PATH
Set fso = CreateObject("Scripting.FileSystemObject")
If Not fso.FileExists(PythonW) Then
    PythonW = "pythonw"
End If

WshShell.CurrentDirectory = BaseDir
WshShell.Run """" & PythonW & """ """ & Runner & """", 0, False

' Give it 3s then open health check
WScript.Sleep 3000
WshShell.Run "http://localhost:5001/api/health", 1, False
