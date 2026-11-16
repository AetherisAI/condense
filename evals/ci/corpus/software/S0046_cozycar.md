# S0046 — CozyCar

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Also known as:** CozyDuke, CozyBear, Cozer, EuroAPT
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0046
- **Last modified:** 2024-04-11

## Description

CozyCar is malware that was used by APT29 from 2010 to 2015. It is a modular malware platform, and its backdoor component can be instructed to download and execute a variety of modules with different functionality.

## Techniques used

- **T1003.001 OS Credential Dumping: LSASS Memory** — CozyCar has executed Mimikatz to harvest stored credentials from the victim and further victim penetration.
- **T1003.002 OS Credential Dumping: Security Account Manager** — Password stealer and NTLM stealer modules in CozyCar harvest stored credentials from the victim, including credentials used as part of Windows NTLM user authentication.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — The payload of CozyCar is encrypted with simple XOR with a rotating key. The CozyCar configuration file has been encrypted with RC4 keys.
- **T1036.003 Masquerading: Rename Legitimate Utilities** — The CozyCar dropper has masqueraded a copy of the infected system's rundll32.exe executable that was moved to the malware's install directory and renamed according to a predefined configuration file.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — One persistence mechanism used by CozyCar is to register itself as a scheduled task.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — A module in CozyCar allows arbitrary commands to be executed by invoking `C:\Windows\System32\cmd.exe`.
- **T1071.001 Application Layer Protocol: Web Protocols** — CozyCar's main method of communicating with its C2 servers is using HTTP or HTTPS.
- **T1082 System Information Discovery** — A system info module in CozyCar gathers information on the victim host’s configuration.
- **T1102.002 Web Service: Bidirectional Communication** — CozyCar uses Twitter as a backup C2 channel to Twitter accounts specified in its configuration file.
- **T1218.011 System Binary Proxy Execution: Rundll32** — The CozyCar dropper copies the system file rundll32.exe to the install location for the malware, then uses the copy of rundll32.exe to load and execute the main CozyCar component.
- **T1497 Virtualization/Sandbox Evasion** — Some versions of CozyCar will check to ensure it is not being executed inside a virtual machine or a known malware analysis sandbox environment. If it detects that it is, it will exit.
- **T1518.001 Software Discovery: Security Software Discovery** — The main CozyCar dropper checks whether the victim has an anti-virus product installed. If the installed product is on a predetermined list, the dropper will exit.
- **T1543.003 Create or Modify System Process: Windows Service** — One persistence mechanism used by CozyCar is to register itself as a Windows service.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — One persistence mechanism used by CozyCar is to set itself to be executed at system startup by adding a Registry value under one of the following Registry keys: <br>`HKLM\Software\Microsoft\Windows\CurrentVersion\Run\` <br>`HKCU\Software\Microsoft\Windows\CurrentVersion\Run\` <br>`HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run` <br>`HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run`

## Used by

- **G0016 APT29** (group)
