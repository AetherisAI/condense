# S1076 — QUIETCANARY

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Also known as:** Tunnus
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S1076
- **Last modified:** 2025-04-16

## Description

QUIETCANARY is a backdoor tool written in .NET that has been used since at least 2022 to gather and exfiltrate data from victim networks.

## Techniques used

- **T1012 Query Registry** — QUIETCANARY has the ability to retrieve information from the Registry.
- **T1016 System Network Configuration Discovery** — QUIETCANARY can identify the default proxy setting on a compromised host.
- **T1071.001 Application Layer Protocol: Web Protocols** — QUIETCANARY can use HTTPS for C2 communications.
- **T1074 Data Staged** — QUIETCANARY has the ability to stage data prior to exfiltration.
- **T1106 Native API** — QUIETCANARY can call `System.Net.HttpWebRequest` to identify the default proxy configured on the victim computer.
- **T1132.001 Data Encoding: Standard Encoding** — QUIETCANARY can base64 encode C2 communications.
- **T1140 Deobfuscate/Decode Files or Information** — QUIETCANARY can use a custom parsing routine to decode the command codes and additional parameters from the C2 before executing them.
- **T1564.003 Hide Artifacts: Hidden Window** — QUIETCANARY can execute processes in a hidden window.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — QUIETCANARY can RC4 encrypt C2 communications.

## Used by

- **C0026 C0026** (campaign) — During C0026, the threat actors used QUIETCANARY to gather and exfiltrate data.
