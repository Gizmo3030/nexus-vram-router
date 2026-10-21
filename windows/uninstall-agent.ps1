<#
.SYNOPSIS
  Removes what install-agent.ps1 set up: the Scheduled Task, firewall rule and installed files.
  Run from an elevated PowerShell.
#>
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:ProgramData 'nexus-agent')
)

$ErrorActionPreference = 'Stop'

if (Get-ScheduledTask -TaskName 'nexus-agent' -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName 'nexus-agent' -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName 'nexus-agent' -Confirm:$false
}
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*$InstallDir*agent.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Get-NetFirewallRule -Name 'nexus-agent' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }

Write-Host 'nexus-agent removed.'
