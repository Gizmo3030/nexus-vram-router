<#
.SYNOPSIS
  Installs the nexus VRAM agent on this Windows GPU machine.

.DESCRIPTION
  Copies agent.py to a fixed folder, opens the agent's TCP port on the Private network
  profile, and registers a Scheduled Task that starts the agent with pythonw at boot.
  Safe to run again: it replaces the task and the firewall rule instead of adding more.
  Run from an elevated PowerShell.

.PARAMETER Port
  TCP port the agent listens on (default 11500).

.PARAMETER Token
  Optional shared secret; the router must then send it as agent_token. Note it is stored
  in the Scheduled Task's arguments, readable by local administrators.

.PARAMETER Python
  Path to pythonw.exe. Defaults to the first pythonw on PATH. It must be readable by SYSTEM
  (a python.org install for all users is; a Microsoft Store Python is not).

.PARAMETER InstallDir
  Where agent.py is installed (default %ProgramData%\nexus-agent).

.EXAMPLE
  .\install-agent.ps1 -Port 11500 -Token mysecret
#>
#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [int]$Port = 11500,
    [string]$Token,
    [string]$Python,
    [string]$InstallDir = (Join-Path $env:ProgramData 'nexus-agent')
)

$ErrorActionPreference = 'Stop'
$TaskName = 'nexus-agent'
$RuleName = 'nexus-agent'

# agent.py sits next to this script when copied by hand, or in src\nexus_router\ in a checkout.
$candidates = @(
    (Join-Path $PSScriptRoot 'agent.py'),
    (Join-Path $PSScriptRoot '..\src\nexus_router\agent.py')
)
$source = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $source) { throw "agent.py not found (looked in: $($candidates -join ', '))" }

if (-not $Python) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'pythonw.exe not found on PATH. Install Python 3.10+ or pass -Python <path to pythonw.exe>.' }
    $Python = $cmd.Source
}
if (-not (Test-Path $Python)) { throw "pythonw not found at $Python" }

# Stop a running copy first so the file can be replaced.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*$InstallDir*agent.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$agent = Join-Path $InstallDir 'agent.py'
Copy-Item -Path $source -Destination $agent -Force

# Private profile only: the agent should never be reachable from public networks.
Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name $RuleName -DisplayName "nexus-agent (TCP $Port)" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null

$agentArgs = "`"$agent`" --port $Port"
if ($Token) { $agentArgs += " --token `"$Token`"" }
$action = New-ScheduledTaskAction -Execute $Python -Argument $agentArgs -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Description 'Reports GPU VRAM to nexus-router' | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "nexus-agent installed in $InstallDir and listening on port $Port."
Write-Host "Check it with: curl http://localhost:$Port/vram"
