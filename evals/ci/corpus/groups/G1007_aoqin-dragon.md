# G1007 — Aoqin Dragon

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/groups/G1007
- **Last modified:** 2026-07-31

## Description

Aoqin Dragon is a suspected Chinese cyber espionage threat group that has been active since at least 2013. Aoqin Dragon has primarily targeted government, education, and telecommunication organizations in Australia, Cambodia, Hong Kong, Singapore, and Vietnam. Security researchers noted a potential association between Aoqin Dragon and UNC94, based on malware, infrastructure, and targets.

## Techniques used

- **T1027.002 Obfuscated Files or Information: Software Packing** — Aoqin Dragon has used the Themida packer to obfuscate malicious payloads.
- **T1036 Masquerading** — Aoqin Dragon has used fake icons including antivirus and external drives to disguise malicious payloads.
- **T1083 File and Directory Discovery** — Aoqin Dragon has run scripts to identify file formats including Microsoft Word.
- **T1091 Replication Through Removable Media** — Aoqin Dragon has used a dropper that employs a worm infection strategy using a removable device to breach a secure network environment.
- **T1203 Exploitation for Client Execution** — Aoqin Dragon has exploited CVE-2012-0158 and CVE-2010-3333 for execution against targeted systems.
- **T1204.002 User Execution: Malicious File** — Aoqin Dragon has lured victims into opening weaponized documents, fake external drives, and fake antivirus to execute malicious payloads.
- **T1570 Lateral Tool Transfer** — Aoqin Dragon has spread malware in target networks by copying modules to folders masquerading as removable devices.
- **T1587.001 Develop Capabilities: Malware** — Aoqin Dragon has used custom malware, including Mongall and Heyoka Backdoor, in their operations.
- **T1588.002 Obtain Capabilities: Tool** — Aoqin Dragon obtained the Heyoka open source exfiltration tool and subsequently modified it for their operations.

## Software used

- **S1026 Mongall**
- **S1027 Heyoka Backdoor**
