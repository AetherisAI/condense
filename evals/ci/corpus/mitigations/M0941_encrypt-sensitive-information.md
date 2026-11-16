# M0941 — Encrypt Sensitive Information

- **Type:** mitigation
- **Domain:** ICS ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/mitigations/M0941
- **Last modified:** 2026-05-12

## Description

Protect sensitive data-at-rest with strong encryption.

## Techniques addressed

- **T0811 Data from Information Repositories** — Information which is sensitive to the operation and architecture of the process environment may be encrypted to ensure confidentiality and restrict access to only those who need to know.
- **T0864 Transient Cyber Asset** — Consider implementing full disk encryption, especially if engineering workstations are transient assets that are more likely to be lost, stolen, or tampered with.
- **T0873 Project File Infection** — When at rest, project files should be encrypted to prevent unauthorized changes.
- **T0873.001 Project File Infection: Siemens Project File Format** — When at rest, project files should be encrypted to prevent unauthorized changes.
- **T0882 Theft of Operational Information** — Encrypt any operational data with strong confidentiality requirements, including organizational trade-secrets, recipes, and other intellectual property (IP).
- **T0893 Data from Local System** — Information which is sensitive to the operation and architecture of the process environment may be encrypted to ensure confidentiality and restrict access to only those who need to know.
- **T1693 Modify Firmware** — The encryption of firmware should be considered to prevent adversaries from identifying possible vulnerabilities within the firmware.
- **T1693.001 Modify Firmware: System Firmware** — The encryption of firmware should be considered to prevent adversaries from identifying possible vulnerabilities within the firmware.
- **T1693.002 Modify Firmware: Module Firmware** — The encryption of firmware should be considered to prevent adversaries from identifying possible vulnerabilities within the firmware.
