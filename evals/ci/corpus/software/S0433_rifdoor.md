# S0433 — Rifdoor

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0433
- **Last modified:** 2024-04-11

## Description

Rifdoor is a remote access trojan (RAT) that shares numerous code similarities with HotCroissant.

## Techniques used

- **T1016 System Network Configuration Discovery** — Rifdoor has the ability to identify the IP address of the compromised host.
- **T1027.001 Obfuscated Files or Information: Binary Padding** — Rifdoor has added four additional bytes of data upon launching, then saved the changed version as `C:\ProgramData\Initech\Initech.exe`.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — Rifdoor has encrypted strings with a single byte XOR algorithm.
- **T1033 System Owner/User Discovery** — Rifdoor has the ability to identify the username on the compromised host.
- **T1082 System Information Discovery** — Rifdoor has the ability to identify the Windows version on the compromised host.
- **T1204.002 User Execution: Malicious File** — Rifdoor has been executed from malicious Excel or Word documents containing macros.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — Rifdoor has created a new registry entry at `HKEY_CURRENT_USERS\Software\Microsoft\Windows\CurrentVersion\Run\Graphics` with a value of `C:\ProgramData\Initech\Initech.exe /run`.
- **T1566.001 Phishing: Spearphishing Attachment** — Rifdoor has been distributed in e-mails with malicious Excel or Word documents.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — Rifdoor has encrypted command and control (C2) communications with a stream cipher.

## Used by

- **G0138 Andariel** (group)
