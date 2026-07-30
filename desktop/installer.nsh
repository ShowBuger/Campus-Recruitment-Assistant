!macro customInstall
  ; The installer cannot remove itself while it is still running. Start an
  ; asynchronous cleanup process that retries after the installer has exited.
  Exec '"$SYSDIR\cmd.exe" /D /Q /C "for /L %i in (1,1,30) do @(del /F /Q $\"$EXEPATH$\" 2>NUL && exit /B 0 || ping 127.0.0.1 -n 2 >NUL)"'
!macroend
