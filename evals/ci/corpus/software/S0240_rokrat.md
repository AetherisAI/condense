# S0240 — ROKRAT

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0240
- **Last modified:** 2025-04-25

## Description

ROKRAT is a cloud-based remote access tool (RAT) used by APT37 to target victims in South Korea. APT37 has used ROKRAT during several campaigns from 2016 through 2021.

## Techniques used

- **T1005 Data from Local System** — ROKRAT can collect host data and specific file types.
- **T1010 Application Window Discovery** — ROKRAT can use the `GetForegroundWindow` and `GetWindowText` APIs to discover where the user is typing.
- **T1012 Query Registry** — ROKRAT can access the `HKLM\System\CurrentControlSet\Services\mssmbios\Data\SMBiosData` Registry key to obtain the System manufacturer value to identify the machine type.
- **T1027 Obfuscated Files or Information** — ROKRAT can encrypt data prior to exfiltration by using an RSA public key.
- **T1033 System Owner/User Discovery** — ROKRAT can collect the username from a compromised host.
- **T1041 Exfiltration Over C2 Channel** — ROKRAT can send collected files back over same C2 channel.
- **T1055 Process Injection** — ROKRAT can use `VirtualAlloc`, `WriteProcessMemory`, and then `CreateRemoteThread` to execute shellcode within the address space of `Notepad.exe`.
- **T1056.001 Input Capture: Keylogging** — ROKRAT can use `SetWindowsHookEx` and `GetKeyNameText` to capture keystrokes.
- **T1057 Process Discovery** — ROKRAT can list the current running processes on the system.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — ROKRAT has used Visual Basic for execution.
- **T1070.004 Indicator Removal: File Deletion** — ROKRAT can request to delete files.
- **T1071.001 Application Layer Protocol: Web Protocols** — ROKRAT can use HTTP and HTTPS for command and control communication.
- **T1082 System Information Discovery** — ROKRAT can gather the hostname and the OS version to ensure it doesn’t run on a Windows XP or Windows Server 2003 systems.
- **T1083 File and Directory Discovery** — ROKRAT has the ability to gather a list of files and directories on the infected system.
- **T1102.002 Web Service: Bidirectional Communication** — ROKRAT has used legitimate social networking sites and cloud platforms (including but not limited to Twitter, Yandex, Dropbox, and Mediafire) for C2 communications.
- **T1105 Ingress Tool Transfer** — ROKRAT can retrieve additional malicious payloads from its C2 server.
- **T1106 Native API** — ROKRAT can use a variety of API calls to execute shellcode.
- **T1112 Modify Registry** — ROKRAT can modify the `HKEY_CURRENT_USER\Software\Microsoft\Office\` registry key so it can bypass the VB object model (VBOM) on a compromised host.
- **T1113 Screen Capture** — ROKRAT can capture screenshots of the infected system using the `gdi32` library.
- **T1115 Clipboard Data** — ROKRAT can extract clipboard data from a compromised host.
- **T1123 Audio Capture** — ROKRAT has an audio capture and eavesdropping module.
- **T1140 Deobfuscate/Decode Files or Information** — ROKRAT can decrypt strings using the victim's hostname as the key.
- **T1204.002 User Execution: Malicious File** — ROKRAT has relied upon users clicking on a malicious attachment delivered through spearphishing.
- **T1480.001 Execution Guardrails: Environmental Keying** — ROKRAT relies on a specific victim hostname to execute and decrypt important strings.
- **T1497.001 Virtualization/Sandbox Evasion: System Checks** — ROKRAT can check for VMware-related files and DLLs related to sandboxes.
- **T1555.003 Credentials from Password Stores: Credentials from Web Browsers** — ROKRAT can steal credentials stored in Web browsers by querying the sqlite database.
- **T1555.004 Credentials from Password Stores: Windows Credential Manager** — ROKRAT can steal credentials by leveraging the Windows Vault mechanism.
- **T1566.001 Phishing: Spearphishing Attachment** — ROKRAT has been delivered via spearphishing emails that contain a malicious Hangul Office or Microsoft Word document.
- **T1567.002 Exfiltration Over Web Service: Exfiltration to Cloud Storage** — ROKRAT can send collected data to cloud storage services such as PCloud.
- **T1622 Debugger Evasion** — ROKRAT can check for debugging tools.

## Used by

- **G0067 APT37** (group)
