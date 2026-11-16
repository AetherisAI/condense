# S1130 — Raspberry Robin

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S1130
- **Last modified:** 2024-07-23

## Description

Raspberry Robin is initial access malware first identified in September 2021, and active through early 2024. The malware is notable for spreading via infected USB devices containing a malicious LNK object that, on execution, retrieves remote hosted payloads for installation. Raspberry Robin has been widely used against various industries and geographies, and as a precursor to information stealer, ransomware, and other payloads such as SocGholish, Cobalt Strike, IcedID, and Bumblebee. The DLL componenet in the Raspberry Robin infection chain is also referred to as "Roshtyak." The name "Raspberry Robin" is used to refer to both the malware as well as the threat actor associated with its use, although the Raspberry Robin operators are also tracked as `Storm-0856` by some vendors.

## Techniques used

- **T1027 Obfuscated Files or Information** — Raspberry Robin uses mixed-case letters for filenames and commands to evade detection.
- **T1027.002 Obfuscated Files or Information: Software Packing** — Raspberry Robin contains multiple payloads that are packed for defense evasion purposes and unpacked on runtime.
- **T1033 System Owner/User Discovery** — Raspberry Robin determines whether it is successfully running on a victim system by querying the running account information to determine if it is running in Session 0, indicating running with elevated privileges.
- **T1036.004 Masquerading: Masquerade Task or Service** — Raspberry Robin will execute its payload prior to initializing command and control traffic by impersonating one of several legitimate program names such as dllhost.exe, regsvr32.exe, or rundll32.exe.
- **T1036.008 Masquerading: Masquerade File Type** — Raspberry Robin has historically been delivered via infected USB drives containing a malicious LNK object masquerading as a legitimate folder.
- **T1047 Windows Management Instrumentation** — Raspberry Robin can execute via LNK containing a command to run a legitimate executable, such as wmic.exe, to download a malicious Windows Installer (MSI) package.
- **T1055.012 Process Injection: Process Hollowing** — Raspberry Robin will execute a legitimate process, then suspend it to inject code for a Tor client into the process, followed by resumption of the process to enable Tor client execution.
- **T1057 Process Discovery** — Raspberry Robin can identify processes running on the victim machine, such as security software, during execution.
- **T1059 Command and Scripting Interpreter** — Raspberry Robin variants can be delivered via highly obfuscated Windows Script Files (WSF) for initial execution.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — Raspberry Robin uses cmd.exe to read and execute a file stored on an infected USB device as part of initial installation.
- **T1070.004 Indicator Removal: File Deletion** — Raspberry Robin can delete its initial delivery script from disk during execution.
- **T1070.009 Indicator Removal: Clear Persistence** — Raspberry Robin uses a `RunOnce` Registry key for persistence, where the key is removed after its use on reboot then re-added by the malware after it resumes execution.
- **T1071 Application Layer Protocol** — Raspberry Robin is capable of contacting the TOR network for delivering second-stage payloads.
- **T1071.001 Application Layer Protocol: Web Protocols** — Raspberry Robin uses outbound HTTP requests containing victim information for retrieving second stage payloads. Variants of Raspberry Robin can download archive files (such as 7-Zip files) via the victim web browser for second stage execution.
- **T1082 System Information Discovery** — Raspberry Robin performs several system checks as part of anti-analysis mechanisms, including querying the operating system build number, processor vendor and type, video controller, and CPU temperature.
- **T1083 File and Directory Discovery** — Raspberry Robin will check to see if the initial executing script is located on the user's Desktop as an anti-analysis check.
- **T1091 Replication Through Removable Media** — Raspberry Robin has historically used infected USB media to spread to new victims.
- **T1102 Web Service** — Raspberry Robin second stage payloads can be hosted as RAR files, containing a malicious EXE and DLL, on Discord servers.
- **T1105 Ingress Tool Transfer** — Raspberry Robin retrieves its second stage payload in a variety of ways such as through msiexec.exe abuse, or running the curl command to download the payload to the victim's `%AppData%` folder.
- **T1140 Deobfuscate/Decode Files or Information** — Raspberry Robin contains several layers of obfuscation to hide malicious code from detection and analysis.
- **T1204 User Execution** — Raspberry Robin execution can rely on users directly interacting with malicious LNK files.
- **T1218.007 System Binary Proxy Execution: Msiexec** — Raspberry Robin uses msiexec.exe for post-installation communication to command and control infrastructure. Msiexec.exe is executed referencing a remote resource for second-stage payload retrieval and execution.
- **T1218.008 System Binary Proxy Execution: Odbcconf** — Raspberry Robin uses the Windows utility odbcconf.exe to execute malicious commands, using the `regsvr` flag to execute DLLs and bypass application control mechanisms that are not monitoring for odbcconf.exe abuse.
- **T1218.010 System Binary Proxy Execution: Regsvr32** — Raspberry Robin uses regsvr32.exe execution without any command line parameters for command and control requests to IP addresses associated with Tor nodes.
- **T1218.011 System Binary Proxy Execution: Rundll32** — Raspberry Robin uses rundll32 execution without any command line parameters to contact command and control infrastructure, such as IP addresses associated with Tor nodes.
- **T1480 Execution Guardrails** — Raspberry Robin will check for the presence of several security products on victim machines and will avoid UAC bypass mechanisms if they are identified. Raspberry Robin can use specific cookie values in HTTP requests to command and control infrastructure to validate that requests for second stage payloads originate from the initial downloader script.
- **T1497 Virtualization/Sandbox Evasion** — Raspberry Robin contains real and fake second-stage payloads following initial execution, with the real payload only delivered if the malware determines it is not running in a virtualized environment.
- **T1497.001 Virtualization/Sandbox Evasion: System Checks** — Raspberry Robin performs a variety of system environment checks to determine if it is running in a virtualized or sandboxed environment, such as querying CPU temperature information and network card MAC address information.
- **T1518.001 Software Discovery: Security Software Discovery** — Raspberry Robin attempts to identify security software running on the victim machine, such as BitDefender, Avast, and Kaspersky.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — Raspberry Robin will use a Registry key to achieve persistence through reboot, setting a RunOnce key such as: `HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce {random value name} = “rundll32 shell32 ShellExec_RunDLLA REGSVR /u /s “{dropped copy path and file name}”” `.
- **T1548 Abuse Elevation Control Mechanism** — Raspberry Robin implements a variation of the `ucmDccwCOMMethod` technique abusing the Windows AutoElevate backdoor to bypass UAC while elevating privileges.
- **T1548.002 Abuse Elevation Control Mechanism: Bypass User Account Control** — Raspberry Robin will use the legitimate Windows utility fodhelper.exe to run processes at elevated privileges without requiring a User Account Control prompt.
- **T1559 Inter-Process Communication** — Raspberry Robin contains an embedded custom Tor network client that communicates with the primary payload via shared process memory.
- **T1559.001 Inter-Process Communication: Component Object Model** — Raspberry Robin creates an elevated COM object for `CMLuaUtil` and uses this to set a registry value that points to the malicious LNK file during execution.
- **T1571 Non-Standard Port** — Raspberry Robin will communicate via HTTP over port 8080 for command and control traffic.
- **T1574 Hijack Execution Flow** — Raspberry Robin will drop a copy of itself to a subfolder in `%Program Data%` or `%Program Data%\\Microsoft\\` to attempt privilege elevation and defense evasion if not running in Session 0.
- **T1574.001 Hijack Execution Flow: DLL** — Raspberry Robin can use legitimate, signed EXE files paired with malicious DLL files to load and run malicious payloads while bypassing defenses.
- **T1583.001 Acquire Infrastructure: Domains** — Raspberry Robin uses newly-registered domains containing only a few characters for command and controll purposes, such as "`v0[.]cx`".
- **T1583.008 Acquire Infrastructure: Malvertising** — Raspberry Robin variants have been delivered via malicious advertising items that, when interacted with, download a malicious archive file containing the initial payload, hosted on services such as Discord.
- **T1622 Debugger Evasion** — Raspberry Robin leverages anti-debugging mechanisms through the use of `ThreadHideFromDebugger`.
- **T1685 Disable or Modify Tools** — Raspberry Robin can add an exception to Microsoft Defender that excludes the entire main drive from anti-malware scanning to evade detection.
