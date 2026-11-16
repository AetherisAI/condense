# S0283 — jRAT

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Also known as:** JSocket, AlienSpy, Frutas, Sockrat, Unrecom, jFrutas, Adwind, jBiFrost, Trojan.Maljava
- **Platforms:** Linux, Windows, macOS, Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0283
- **Last modified:** 2023-10-03

## Description

jRAT is a cross-platform, Java-based backdoor originally available for purchase in 2012. Variants of jRAT have been distributed via a software-as-a-service platform, similar to an online subscription model.

## Techniques used

- **T1007 System Service Discovery** — jRAT can list local services.
- **T1016 System Network Configuration Discovery** — jRAT can gather victim internal and external IPs.
- **T1021.001 Remote Services: Remote Desktop Protocol** — jRAT can support RDP control.
- **T1027 Obfuscated Files or Information** — jRAT’s Java payload is encrypted with AES. Additionally, backdoor files are encrypted using DES as a stream cipher. Later variants of jRAT also incorporated AV evasion methods such as Java bytecode obfuscation via the commercial Allatori obfuscation tool.
- **T1027.002 Obfuscated Files or Information: Software Packing** — jRAT payloads have been packed.
- **T1029 Scheduled Transfer** — jRAT can be configured to reconnect at certain intervals.
- **T1037.005 Boot or Logon Initialization Scripts: Startup Items** — jRAT can list and manage startup entries.
- **T1047 Windows Management Instrumentation** — jRAT uses WMIC to identify anti-virus products installed on the victim’s machine and to obtain firewall details.
- **T1049 System Network Connections Discovery** — jRAT can list network connections.
- **T1056.001 Input Capture: Keylogging** — jRAT has the capability to log keystrokes from the victim’s machine, both offline and online.
- **T1057 Process Discovery** — jRAT can query and kill system processes.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — jRAT has command line access.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — jRAT has been distributed as HTA files with VBScript.
- **T1059.007 Command and Scripting Interpreter: JavaScript** — jRAT has been distributed as HTA files with JScript.
- **T1070.004 Indicator Removal: File Deletion** — jRAT has a function to delete files from the victim’s machine.
- **T1082 System Information Discovery** — jRAT collects information about the OS (version, build type, install date) as well as system up-time upon receiving a connection from a backdoor.
- **T1083 File and Directory Discovery** — jRAT can browse file systems.
- **T1090 Proxy** — jRAT can serve as a SOCKS proxy server.
- **T1105 Ingress Tool Transfer** — jRAT can download and execute files.
- **T1113 Screen Capture** — jRAT has the capability to take screenshots of the victim’s machine.
- **T1115 Clipboard Data** — jRAT can capture clipboard data.
- **T1120 Peripheral Device Discovery** — jRAT can map UPnP ports.
- **T1123 Audio Capture** — jRAT can capture microphone recordings.
- **T1125 Video Capture** — jRAT has the capability to capture video from a webcam.
- **T1518.001 Software Discovery: Security Software Discovery** — jRAT can list security software, such as by using WMIC to identify anti-virus products installed on the victim’s machine and to obtain firewall details.
- **T1552.001 Unsecured Credentials: Credentials In Files** — jRAT can capture passwords from common chat applications such as MSN Messenger, AOL, Instant Messenger, and and Google Talk.
- **T1552.004 Unsecured Credentials: Private Keys** — jRAT can steal keys for VPNs and cryptocurrency wallets.
- **T1555.003 Credentials from Password Stores: Credentials from Web Browsers** — jRAT can capture passwords from common web browsers such as Internet Explorer, Google Chrome, and Firefox.

## Used by

- **G1018 TA2541** (group)
