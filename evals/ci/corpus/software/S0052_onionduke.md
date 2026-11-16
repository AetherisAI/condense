# S0052 — OnionDuke

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0052
- **Last modified:** 2025-04-25

## Description

OnionDuke is malware that was used by APT29 from 2013 to 2015.

## Techniques used

- **T1003 OS Credential Dumping** — OnionDuke steals credentials from its victims.
- **T1071.001 Application Layer Protocol: Web Protocols** — OnionDuke uses HTTP and HTTPS for C2.
- **T1102.003 Web Service: One-Way Communication** — OnionDuke uses Twitter as a backup C2.
- **T1140 Deobfuscate/Decode Files or Information** — OnionDuke can use a custom decryption algorithm to decrypt strings.
- **T1499 Endpoint Denial of Service** — OnionDuke has the capability to use a Denial of Service module.

## Used by

- **G0016 APT29** (group)
