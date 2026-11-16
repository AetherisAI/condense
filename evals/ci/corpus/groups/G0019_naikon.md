# G0019 — Naikon

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/groups/G0019
- **Last modified:** 2026-07-31

## Description

Naikon is assessed to be a state-sponsored cyber espionage group attributed to the Chinese People’s Liberation Army’s (PLA) Chengdu Military Region Second Technical Reconnaissance Bureau (Military Unit Cover Designator 78020). Active since at least 2010, Naikon has primarily conducted operations against government, military, and civil organizations in Southeast Asia, as well as against international bodies such as the United Nations Development Programme (UNDP) and the Association of Southeast Asian Nations (ASEAN). 

While Naikon shares some characteristics with APT30, the two groups do not appear to be exact matches.

## Techniques used

- **T1016 System Network Configuration Discovery** — Naikon uses commands such as `netsh interface show` to discover network interface settings.
- **T1018 Remote System Discovery** — Naikon has used a netbios scanner for remote machine identification.
- **T1036.004 Masquerading: Masquerade Task or Service** — Naikon renamed a malicious service `taskmgr` to appear to be a legitimate version of Task Manager.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — Naikon has disguised malicious programs as Google Chrome, Adobe, and VMware executables.
- **T1046 Network Service Discovery** — Naikon has used the LadonGo scanner to scan target networks.
- **T1047 Windows Management Instrumentation** — Naikon has used WMIC.exe for lateral movement.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — Naikon has used schtasks.exe for lateral movement in compromised networks.
- **T1078.002 Valid Accounts: Domain Accounts** — Naikon has used administrator credentials for lateral movement in compromised networks.
- **T1137.006 Office Application Startup: Add-ins** — Naikon has used the RoyalRoad exploit builder to drop a second stage loader, intel.wll, into the Word Startup folder on the compromised host.
- **T1204.002 User Execution: Malicious File** — Naikon has convinced victims to open malicious attachments to execute malware.
- **T1518.001 Software Discovery: Security Software Discovery** — Naikon uses commands such as `netsh advfirewall firewall` to discover local firewall settings.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — Naikon has modified a victim's Windows Run registry to establish persistence.
- **T1566.001 Phishing: Spearphishing Attachment** — Naikon has used malicious e-mail attachments to deliver malware.
- **T1574.001 Hijack Execution Flow: DLL** — Naikon has used DLL side-loading to load malicious DLL's into legitimate executables.

## Software used

- **S0029 PsExec**
- **S0039 Net**
- **S0055 RARSTONE**
- **S0057 Tasklist**
- **S0058 SslMM**
- **S0059 WinMM**
- **S0060 Sys10**
- **S0061 HDoor**
- **S0095 ftp**
- **S0096 Systeminfo**
- **S0097 Ping**
- **S0108 netsh**
- **S0456 Aria-body**
- **S0629 RainyDay**
- **S0630 Nebulae**
