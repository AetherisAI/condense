# S0054 — CloudDuke

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Also known as:** MiniDionis, CloudLook
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0054
- **Last modified:** 2025-04-25

## Description

CloudDuke is malware that was used by APT29 in 2015.

## Techniques used

- **T1071.001 Application Layer Protocol: Web Protocols** — One variant of CloudDuke uses HTTP and HTTPS for C2.
- **T1102.002 Web Service: Bidirectional Communication** — One variant of CloudDuke uses a Microsoft OneDrive account to exchange commands and stolen data with its operators.
- **T1105 Ingress Tool Transfer** — CloudDuke downloads and executes additional malware from either a Web address or a Microsoft OneDrive account.

## Used by

- **G0016 APT29** (group)
