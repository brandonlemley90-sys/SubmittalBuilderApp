Set WshShell = CreateObject("WScript.Shell")
strPath = WshShell.CurrentDirectory

' --- List of possible Python paths ---
arrPaths = Array(_
    WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Python\bin\pythonw.exe", _
    WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe", _
    "pythonw.exe" _
)

foundPath = ""
For Each path In arrPaths
    If CreateObject("Scripting.FileSystemObject").FileExists(path) Then
        foundPath = path
        Exit For
    End If
Next

' Default to "pythonw.exe" if not found specifically
If foundPath = "" Then foundPath = "pythonw.exe"

' Run the worker silently (0 = hide window)
WshShell.Run """" & foundPath & """ """ & strPath & "\worker.py""", 0, False
