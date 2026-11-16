# S0465 — CARROTBALL

- **Type:** software (tool)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0465
- **Last modified:** 2025-04-25

## Description

CARROTBALL is an FTP downloader utility that has been in use since at least 2019. CARROTBALL has been used as a downloader to install SYSCON.

## Techniques used

- **T1027 Obfuscated Files or Information** — CARROTBALL has used a custom base64 alphabet to decode files.
- **T1071.002 Application Layer Protocol: File Transfer Protocols** — CARROTBALL has the ability to use FTP in C2 communications.
- **T1105 Ingress Tool Transfer** — CARROTBALL has the ability to download and install a remote payload.
- **T1204.002 User Execution: Malicious File** — CARROTBALL has been executed through users being lured into opening malicious e-mail attachments.
