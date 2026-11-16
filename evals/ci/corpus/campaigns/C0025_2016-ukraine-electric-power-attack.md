# C0025 — 2016 Ukraine Electric Power Attack

- **Type:** campaign
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **First seen:** 2016-12-01
- **Last seen:** 2016-12-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0025
- **Last modified:** 2026-07-31

## Description

2016 Ukraine Electric Power Attack was a Sandworm Team campaign during which they used Industroyer malware to target and disrupt distribution substations within the Ukrainian power grid. This campaign was the second major public attack conducted against Ukraine by Sandworm Team.

## Techniques used

- **T0849 Masquerading** — During the 2016 Ukraine Electric Power Attack, Sandworm Team transferred executable files as .txt and then renamed them to .exe, likely to avoid detection through extension tracking.
- **T0859 Valid Accounts** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used valid accounts to laterally move through VPN connections and dual-homed systems.
- **T0867 Lateral Tool Transfer** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used a VBS script to facilitate lateral tool transfer. The VBS script was used to copy ICS-specific payloads with the following command: `cscript C:\Backinfo\ufn.vbs C:\Backinfo\101.dll C:\Delta\101.dll`
- **T0886 Remote Services** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used MS-SQL access to a pivot machine, allowing code execution throughout the ICS network.
- **T1003.001 OS Credential Dumping: LSASS Memory** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used Mimikatz to capture and use legitimate credentials.
- **T1018 Remote System Discovery** — During the 2016 Ukraine Electric Power Attack, Sandworm Team checked for connectivity to resources within the network and used LDAP to query Active Directory, discovering information about computers listed in AD.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — During the 2016 Ukraine Electric Power Attack, Sandworm Team utilized `net use` to connect to network shares.
- **T1027 Obfuscated Files or Information** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used heavily obfuscated code with Industroyer in its Windows Notepad backdoor.
- **T1027.002 Obfuscated Files or Information: Software Packing** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used UPX to pack a copy of Mimikatz.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — During the 2016 Ukraine Electric Power Attack, DLLs and EXEs with filenames associated with common electric power sector protocols were used to masquerade files.
- **T1036.008 Masquerading: Masquerade File Type** — During the 2016 Ukraine Electric Power Attack, Sandworm Team masqueraded executables as `.txt` files.
- **T1036.010 Masquerading: Masquerade Account Name** — During the 2016 Ukraine Electric Power Attack, Sandworm Team created two new accounts, “admin” and “система” (System).
- **T1047 Windows Management Instrumentation** — During the 2016 Ukraine Electric Power Attack, WMI in scripts were used for remote execution and system surveys.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used PowerShell scripts to run a credential harvesting tool in memory to evade defenses.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used the `xp_cmdshell` command in MS-SQL.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — During the 2016 Ukraine Electric Power Attack, Sandworm Team created VBScripts to run on an SSH server.
- **T1098 Account Manipulation** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used the `sp_addlinkedsrvlogin` command in MS-SQL to create a link between a created account and other servers in the network.
- **T1110 Brute Force** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used a script to attempt RPC authentication against a number of hosts.
- **T1136 Create Account** — During the 2016 Ukraine Electric Power Attack, Sandworm Team added a login to a SQL Server with `sp_addlinkedsrvlogin`.
- **T1136.002 Create Account: Domain Account** — During the 2016 Ukraine Electric Power Attack, Sandworm Team created two new accounts, “admin” and “система” (System). The accounts were then assigned to a domain matching local operation and were delegated new privileges.
- **T1505.001 Server Software Component: SQL Stored Procedures** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used various MS-SQL stored procedures.
- **T1543.003 Create or Modify System Process: Windows Service** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used an arbitrary system service to load at system boot for persistence for Industroyer. They also replaced the ImagePath registry value of a Windows service with a new backdoor binary.
- **T1554 Compromise Host Software Binary** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used a trojanized version of Windows Notepad to add a layer of persistence for Industroyer.
- **T1570 Lateral Tool Transfer** — During the 2016 Ukraine Electric Power Attack, Sandworm Team used `move` to transfer files to a network share.
- **T1685.001 Disable or Modify Tools: Disable or Modify Windows Event Log** — During the 2016 Ukraine Electric Power Attack, Sandworm Team disabled event logging on compromised systems.
- **T1701.001 Command and Scripting Interpreter: PowerShell** — During the 2016 Ukraine Electric Power Attack, Sandworm Team utilized VBS and batch scripts for file movement and as wrappers for PowerShell execution.
- **T1701.002 Command and Scripting Interpreter: Windows Command Shell** — During the 2016 Ukraine Electric Power Attack, Sandworm Team utilized VBS and batch scripts for file movement and as wrappers for PowerShell execution.
- **T1701.004 Command and Scripting Interpreter: Visual Basic** — During the 2016 Ukraine Electric Power Attack, Sandworm Team utilized VBS and batch scripts for file movement and as wrappers for PowerShell execution.

## Software used

- **S0604 Industroyer** — Within the 2016 Ukraine Electric Power Attack, Industroyer was used to target and disrupt the Ukrainian power grid substation components.

## Attributed to

- **G0034 Sandworm Team**
