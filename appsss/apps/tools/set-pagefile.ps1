# AVOS: give Windows a big page file so models larger than your RAM can run on the CPU (the part that doesn't fit in
# RAM is paged from the SSD). Run in PowerShell AS ADMINISTRATOR, then restart Windows:
#   powershell -ExecutionPolicy Bypass -File D:\star\apps\tools\set-pagefile.ps1 -Drive D: -SizeGB 48
# Put it on your fastest SSD (NVMe). 48 GB is enough for LTX-2.3 fp8 on a 16 GB PC; Z-Image Turbo needs no change.
param([string]$Drive = "C:", [int]$SizeGB = 48)
$ErrorActionPreference = "Stop"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "Run PowerShell as Administrator (right-click > Run as administrator) and try again."; exit 1 }
$Drive = $Drive.TrimEnd('\').ToUpper()
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$Drive'"
if (-not $disk) { Write-Host "No drive $Drive."; exit 1 }
$freeGB = [math]::Floor($disk.FreeSpace / 1GB)
if ($freeGB -lt $SizeGB + 10) { Write-Host "$Drive has $freeGB GB free; it needs $SizeGB GB for the page file plus room to spare."; exit 1 }
$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.AutomaticManagedPagefile) { Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $false } }
$name = "$Drive\pagefile.sys"
$pf = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -ieq $name }
if (-not $pf) { $pf = New-CimInstance -ClassName Win32_PageFileSetting -Property @{ Name = $name } }
Set-CimInstance -InputObject $pf -Property @{ InitialSize = [uint32]8192; MaximumSize = [uint32]($SizeGB * 1024) }
$ram = [math]::Round($cs.TotalPhysicalMemory / 1GB)
Write-Host "Page file $name set to 8-$SizeGB GB (RAM $ram GB). Restart Windows to apply."
Write-Host "After the restart the AVOS worker reports about $($ram + $SizeGB) GB for models (GPU page)."
