Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\24274\Desktop\code\VibeCoding\float-pocket"
WshShell.Run """C:\Users\24274\Desktop\code\VibeCoding\float-pocket\.venv\Scripts\pythonw.exe"" main.py", 0, False
