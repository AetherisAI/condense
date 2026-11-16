# S9046 — IOControl

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/software/S9046
- **Last modified:** 2026-10-20

## Description

IOControl is a Linux backdoor compiled for 32-bit ARM devices that has been used to target IoT and OT devices in Israel and the United States, including IP cameras, routers, firewalls, PLCs, HMIs, and Orpak and Gasboy fuel management systems. Affected vendors include Baicells, D-Link, Hikvision, Phoenix Contact, Red Lion, Teltonika, and Unitronics. IOControl has been used by CyberAv3ngers which is suspected to be affiliated with the Iranian Government Islamic Revolutionary Guard Corps (IRGC).

## Techniques used

- **T0846.001 Remote System Discovery: Port Scan** — IOCONTROL has conducted port scans on a network.
- **T0869.001 Standard Application Layer Protocol: DNS** — IOCONTROL has used DNS over HTTPS (DoH) via CloudFlare’s API to translate hostnames to IP addresses.
- **T0869.002 Standard Application Layer Protocol: Publish/Subscribe Protocols** — IOCONTROL connects to C2 servers using the MQTT protocol over port 1883 and 8883 (encrypted via SSL/TLS). The command-and-control servers are resolved using DNS-over-HTTPS (DoH).
- **T1027.002 Obfuscated Files or Information: Software Packing** — IOCONTROL has used the Ultimate Packer for eXecutables (UPX) to pack the malware.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — IOCONTROL has used the Advanced Encryption Standard 256-bit Cypher Block Chaining (AES-256-CBC) algorithm to encrypt its configuration files which are used to store information like file paths and IP addresses to connect to.
- **T1033 System Owner/User Discovery** — IOCONTROL has used the `whoami` command to get the current user on the system.
- **T1037.004 Boot or Logon Initialization Scripts: RC Scripts** — IOCONTROL has used an RC script (`/etc/rc3.d/S93InitSystemd.sh`) to establish persistence on a system across restarts.
- **T1070.004 Indicator Removal: File Deletion** — IOCONTROL has removed the malware binary and associated log file (i.e., `/tmp/iocontrol.log`) from a system upon command.
- **T1070.009 Indicator Removal: Clear Persistence** — IOCONTROL has removed malware persistence from a system upon command.
- **T1082 System Information Discovery** — IOCONTROL has used the `uname -v` and `uname –r` commands to obtain kernel version and release information as well as the `hostname` command to obtain the hostname of the system.
- **T1124 System Time Discovery** — IOCONTROL has used the `date` and `timezone` commands to gather the system date and time information.
- **T1140 Deobfuscate/Decode Files or Information** — IOCONTROL has used the AES-256-CBC algorithm to decrypt configuration files associated with the malware.
- **T1701.003 Command and Scripting Interpreter: Unix Shell** — IOCONTROL has executed arbitrary commands using system calls as well as scripts with the UNIX Shell.
