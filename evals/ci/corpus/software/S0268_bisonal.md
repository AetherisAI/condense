# S0268 — Bisonal

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0268
- **Last modified:** 2024-04-11

## Description

Bisonal is a remote access tool (RAT) that has been used by Tonto Team against public and private sector organizations in Russia, South Korea, and Japan since at least December 2010.

## Techniques used

- **T1005 Data from Local System** — Bisonal has collected information from a compromised host.
- **T1012 Query Registry** — Bisonal has used the RegQueryValueExA function to retrieve proxy information in the Registry.
- **T1016 System Network Configuration Discovery** — Bisonal can execute `ipconfig` on the victim’s machine.
- **T1027.001 Obfuscated Files or Information: Binary Padding** — Bisonal has appended random binary data to the end of itself to generate a large binary.
- **T1027.002 Obfuscated Files or Information: Software Packing** — Bisonal has used the MPRESS packer and similar tools for obfuscation.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — Bisonal's DLL file and non-malicious decoy file are encrypted with RC4 and some function name strings are obfuscated.
- **T1036 Masquerading** — Bisonal dropped a decoy payload with a .jpg extension that contained a malicious Visual Basic script.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — Bisonal has renamed malicious code to `msacm32.dll` to hide within a legitimate library; earlier versions were disguised as `winhelp`.
- **T1041 Exfiltration Over C2 Channel** — Bisonal has added the exfiltrated data to the URL over the C2 channel.
- **T1057 Process Discovery** — Bisonal can obtain a list of running processes on the victim’s machine.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — Bisonal has launched cmd.exe and used the ShellExecuteW() API function to execute commands on the system.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — Bisonal's dropper creates VBS scripts on the victim’s machine.
- **T1070.004 Indicator Removal: File Deletion** — Bisonal will delete its dropper and VBS scripts from the victim’s machine.
- **T1071.001 Application Layer Protocol: Web Protocols** — Bisonal has used HTTP for C2 communications.
- **T1082 System Information Discovery** — Bisonal has used commands and API calls to gather system information.
- **T1083 File and Directory Discovery** — Bisonal can retrieve a file listing from the system.
- **T1090 Proxy** — Bisonal has supported use of a proxy server.
- **T1095 Non-Application Layer Protocol** — Bisonal has used raw sockets for network communication.
- **T1105 Ingress Tool Transfer** — Bisonal has the capability to download files to execute on the victim’s machine.
- **T1106 Native API** — Bisonal has used the Windows API to communicate with the Service Control Manager to execute a thread.
- **T1112 Modify Registry** — Bisonal has deleted Registry keys to clean up its prior activity.
- **T1124 System Time Discovery** — Bisonal can check the system time set on the infected host.
- **T1132.001 Data Encoding: Standard Encoding** — Bisonal has encoded binary data with Base64 and ASCII.
- **T1137.006 Office Application Startup: Add-ins** — Bisonal has been loaded through a `.wll` extension added to the ` %APPDATA%\microsoft\word\startup\` repository.
- **T1140 Deobfuscate/Decode Files or Information** — Bisonal has decoded strings in the malware using XOR and RC4.
- **T1204.002 User Execution: Malicious File** — Bisonal has relied on users to execute malicious file attachments delivered via spearphishing emails.
- **T1218.011 System Binary Proxy Execution: Rundll32** — Bisonal has used rundll32.exe to execute as part of the Registry Run key it adds: `HKEY_CURRENT_USER \Software\Microsoft\Windows\CurrentVersion\Run\”vert” = “rundll32.exe c:\windows\temp\pvcu.dll , Qszdez”`.
- **T1497 Virtualization/Sandbox Evasion** — Bisonal can check to determine if the compromised system is running on VMware.
- **T1497.003 Virtualization/Sandbox Evasion: Time Based Checks** — Bisonal has checked if the malware is running in a virtual environment with the anti-debug function GetTickCount() to compare the timing.
- **T1543.003 Create or Modify System Process: Windows Service** — Bisonal has been modified to be used as a Windows service.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — Bisonal has added itself to the Registry key `HKEY_CURRENT_USER\Software\Microsoft\CurrentVersion\Run\` for persistence.
- **T1566.001 Phishing: Spearphishing Attachment** — Bisonal has been delivered as malicious email attachments.
- **T1568 Dynamic Resolution** — Bisonal has used a dynamic DNS service for C2.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — Bisonal variants reported on in 2014 and 2015 used a simple XOR cipher for C2. Some Bisonal samples encrypt C2 communications with RC4.

## Used by

- **G0131 Tonto Team** (group)
