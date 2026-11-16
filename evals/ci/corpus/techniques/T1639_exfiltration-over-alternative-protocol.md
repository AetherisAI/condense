# T1639 — Exfiltration Over Alternative Protocol

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Exfiltration
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1639
- **Last modified:** 2025-10-24

## Description

Adversaries may steal data by exfiltrating it over a different protocol than that of the existing command and control channel. The data may also be sent to an alternate network location from the main command and control server. 

Alternate protocols include FTP, SMTP, HTTP/S, DNS, SMB, or any other network protocol not being used as the main command and control channel. Different protocol channels could also include Web services such as cloud storage. Adversaries may opt to also encrypt and/or obfuscate these alternate channels.

## Sub-techniques

- **T1639.001 Exfiltration Over Alternative Protocol: Exfiltration Over Unencrypted Non-C2 Protocol**

## Detection strategies

- **DET0698 Detection of Exfiltration Over Alternative Protocol**
  - AN1813 (Android): Exfiltration Over Alternative Protocols can be difficult to detect, and therefore enterprises may be better served focusing on detection at other stages of adversarial behavior.
  - AN1814 (iOS): Exfiltration Over Alternative Protocols can be difficult to detect, and therefore enterprises may be better served focusing on detection at other stages of adversarial behavior.

## Procedure examples

- **S1056 TianySpy** (software) — TianySpy can exfiltrate collected user data, including credentials and authorized cookies, via email.
