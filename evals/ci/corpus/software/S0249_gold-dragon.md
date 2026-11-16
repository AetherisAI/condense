# S0249 — Gold Dragon

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0249
- **Last modified:** 2024-05-06

## Description

Gold Dragon is a Korean-language, data gathering implant that was first observed in the wild in South Korea in July 2017. Gold Dragon was used along with Brave Prince and RunningRAT in operations targeting organizations associated with the 2018 Pyeongchang Winter Olympics.

## Techniques used

- **T1012 Query Registry** — Gold Dragon enumerates registry keys with the command `regkeyenum` and obtains information for the Registry key `HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`.
- **T1033 System Owner/User Discovery** — Gold Dragon collects the endpoint victim's username and uses it as a basis for downloading additional components from the C2 server.
- **T1057 Process Discovery** — Gold Dragon checks the running processes on the victim’s machine.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — Gold Dragon uses cmd.exe to execute commands for discovery.
- **T1070.004 Indicator Removal: File Deletion** — Gold Dragon deletes one of its files, 2.hwp, from the endpoint after establishing persistence.
- **T1071.001 Application Layer Protocol: Web Protocols** — Gold Dragon uses HTTP for communication to the control servers.
- **T1074.001 Data Staged: Local Data Staging** — Gold Dragon stores information gathered from the endpoint in a file named 1.hwp.
- **T1082 System Information Discovery** — Gold Dragon collects endpoint information using the `systeminfo` command.
- **T1083 File and Directory Discovery** — Gold Dragon lists the directories for Desktop, program files, and the user’s recently accessed files.
- **T1105 Ingress Tool Transfer** — Gold Dragon can download additional components from the C2 server.
- **T1518.001 Software Discovery: Security Software Discovery** — Gold Dragon checks for anti-malware products and processes.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — Gold Dragon establishes persistence in the Startup folder.
- **T1560 Archive Collected Data** — Gold Dragon encrypts data using Base64 before being sent to the command and control server.
- **T1685 Disable or Modify Tools** — Gold Dragon terminates anti-malware processes if they’re found running on the system.

## Used by

- **G0094 Kimsuky** (group)
