# C0012 — Operation CuckooBees

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **First seen:** 2019-12-01
- **Last seen:** 2022-05-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0012
- **Last modified:** 2026-07-31

## Description

Operation CuckooBees was a cyber espionage campaign targeting technology and manufacturing companies in East Asia, Western Europe, and North America since at least 2019. Security researchers noted the goal of Operation CuckooBees, which was still ongoing as of May 2022, was likely the theft of proprietary information, research and development documents, source code, and blueprints for various technologies. Researchers assessed Operation CuckooBees was conducted by actors affiliated with Winnti Group, APT41, and BARIUM.

## Techniques used

- **T1003.002 OS Credential Dumping: Security Account Manager** — During Operation CuckooBees, the threat actors leveraged a custom tool to dump OS credentials and used following commands: `reg save HKLM\\SYSTEM system.hiv`, `reg save HKLM\\SAM sam.hiv`, and `reg save HKLM\\SECURITY security.hiv`, to dump SAM, SYSTEM and SECURITY hives.
- **T1005 Data from Local System** — During Operation CuckooBees, the threat actors collected data, files, and other information from compromised networks.
- **T1007 System Service Discovery** — During Operation CuckooBees, the threat actors used the `net start` command as part of their initial reconnaissance.
- **T1016 System Network Configuration Discovery** — During Operation CuckooBees, the threat actors used `ipconfig`, `nbtstat`, `tracert`, `route print`, and `cat /etc/hosts` commands.
- **T1018 Remote System Discovery** — During Operation CuckooBees, the threat actors used the `net view` and `ping` commands as part of their advanced reconnaissance.
- **T1027.010 Obfuscated Files or Information: Command Obfuscation** — During Operation CuckooBees, the threat actors executed an encoded VBScript file.
- **T1027.011 Obfuscated Files or Information: Fileless Storage** — During Operation CuckooBees, the threat actors stroed payloads in Windows CLFS (Common Log File System) transactional logs.
- **T1033 System Owner/User Discovery** — During Operation CuckooBees, the threat actors used the `query user` and `whoami` commands as part of their advanced reconnaissance.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — During Operation CuckooBees, the threat actors renamed a malicious executable to `rundll32.exe` to allow it to blend in with other Windows system files.
- **T1049 System Network Connections Discovery** — During Operation CuckooBees, the threat actors used the `net session`, `net use`, and `netstat` commands as part of their advanced reconnaissance.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — During Operation CuckooBees, the threat actors used scheduled tasks to execute batch scripts for lateral movement with the following command: `SCHTASKS /Create /S <IP Address> /U <Username> /p <Password> /SC ONCE /TN test /TR <Path to a Batch File> /ST <Time> /RU SYSTEM.`
- **T1057 Process Discovery** — During Operation CuckooBees, the threat actors used the `tasklist` command as part of their advanced reconnaissance.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — During Operation CuckooBees, the threat actors used batch scripts to perform reconnaissance.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — During Operation CuckooBees, the threat actors executed an encoded VBScript file using `wscript` and wrote the decoded output to a text file.
- **T1069.001 Permission Groups Discovery: Local Groups** — During Operation CuckooBees, the threat actors used the `net group` command as part of their advanced reconnaissance.
- **T1071.001 Application Layer Protocol: Web Protocols** — During Operation CuckooBees, the threat actors enabled HTTP and HTTPS listeners.
- **T1078.002 Valid Accounts: Domain Accounts** — During Operation CuckooBees, the threat actors used compromised domain administrator credentials as part of their lateral movement.
- **T1082 System Information Discovery** — During Operation CuckooBees, the threat actors used the `systeminfo` command to gather details about a compromised system.
- **T1083 File and Directory Discovery** — During Operation CuckooBees, the threat actors used `dir c:\\` to search for files.
- **T1087.001 Account Discovery: Local Account** — During Operation CuckooBees, the threat actors used the `net user` command to gather account information.
- **T1087.002 Account Discovery: Domain Account** — During Operation CuckooBees, the threat actors used the `dsquery` and `dsget` commands to get domain environment information and to query users in administrative groups.
- **T1120 Peripheral Device Discovery** — During Operation CuckooBees, the threat actors used the `fsutil fsinfo drives` command as part of their advanced reconnaissance.
- **T1124 System Time Discovery** — During Operation CuckooBees, the threat actors used the `net time` command as part of their advanced reconnaissance.
- **T1133 External Remote Services** — During Operation CuckooBees, the threat actors enabled WinRM over HTTP/HTTPS as a backup persistence mechanism using the following command: `cscript //nologo "C:\Windows\System32\winrm.vbs" set winrm/config/service@{EnableCompatibilityHttpsListener="true"}`.
- **T1135 Network Share Discovery** — During Operation CuckooBees, the threat actors used the `net share` command as part of their advanced reconnaissance.
- **T1190 Exploit Public-Facing Application** — During Operation CuckooBees, the threat actors exploited multiple vulnerabilities in externally facing servers.
- **T1201 Password Policy Discovery** — During Operation CuckooBees, the threat actors used the `net accounts` command as part of their advanced reconnaissance.
- **T1505.003 Server Software Component: Web Shell** — During Operation CuckooBees, the threat actors generated a web shell within a vulnerable Enterprise Resource Planning Web Application Server as a persistence mechanism.
- **T1543.003 Create or Modify System Process: Windows Service** — During Operation CuckooBees, the threat actors modified the `IKEEXT` and `PrintNotify` Windows services for persistence.
- **T1547.006 Boot or Logon Autostart Execution: Kernel Modules and Extensions** — During Operation CuckooBees, attackers used a signed kernel rootkit to establish additional persistence.
- **T1560.001 Archive Collected Data: Archive via Utility** — During Operation CuckooBees, the threat actors used the Makecab utility to compress and a version of WinRAR to create password-protected archives of stolen data prior to exfiltration.
- **T1574.001 Hijack Execution Flow: DLL** — During Operation CuckooBees, the threat actors used the legitimate Windows services `IKEEXT` and `PrintNotify` to side-load malicious DLLs.
- **T1588.002 Obtain Capabilities: Tool** — For Operation CuckooBees, the threat actors obtained publicly-available JSP code that was used to deploy a webshell onto a compromised server.

## Software used

- **S0096 Systeminfo**
- **S0105 dsquery**
