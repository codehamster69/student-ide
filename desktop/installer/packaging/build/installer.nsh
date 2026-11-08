; Student IDE NSIS hooks (electron-builder include).
; Uninstall removes our WSL distro and its disk image, but not on an update.
!macro customUnInstall
  ${ifNot} ${isUpdated}
    nsExec::Exec 'wsl.exe --unregister StudentIDE'
    Pop $0
  ${endIf}
!macroend
