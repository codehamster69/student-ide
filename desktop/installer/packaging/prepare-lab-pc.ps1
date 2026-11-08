<#
  Student IDE: prepare a lab PC once (run as administrator, e.g. from your deployment tool).
  Turns on WSL2 so every student can finish Student IDE setup without admin rights.
  It cannot turn on virtualization: that is a BIOS/UEFI setting (Intel VT-x / AMD-V / SVM).

    powershell -ExecutionPolicy Bypass -File prepare-lab-pc.ps1 [-Install StudentIDE-Setup.exe]

  Exit codes: 0 ready, 3010 ready after a restart, 2 virtualization off in BIOS, 1 failed.
#>
param([string]$Install)
$ErrorActionPreference = 'Stop'

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$id).IsInRole('Administrators')) {
  Write-Error 'Run this script as an administrator.'; exit 1
}
$build = [int](Get-CimInstance Win32_OperatingSystem).BuildNumber
if ($build -lt 19041) { Write-Error "Windows build $build is too old; WSL2 needs 19041 or newer."; exit 1 }

$fw = (Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled
$hv = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
if ($fw -eq $false -and $hv -eq $false) {
  Write-Output 'Virtualization is OFF in the BIOS/UEFI. Turn on Intel VT-x / AMD-V (SVM), then run this again.'
  exit 2
}

$restart = $false
& wsl.exe --status *> $null
if ($LASTEXITCODE -ne 0) {
  & wsl.exe --install --no-distribution
  if ($LASTEXITCODE -ne 0) {
    # Older inbox WSL: turn the two features on directly.
    foreach ($f in 'Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform') {
      & dism.exe /online /enable-feature /featurename:$f /all /norestart
      if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 3010) { Write-Error "Could not enable $f"; exit 1 }
    }
  }
  $restart = $true
}
& wsl.exe --update 2>$null | Out-Null

if ($Install) { Start-Process -FilePath $Install -ArgumentList '/S','/allusers' -Wait }

if ($restart) { Write-Output 'WSL2 turned on. Restart this PC to finish.'; exit 3010 }
Write-Output 'This PC is ready for Student IDE.'
exit 0
