# S0252 — Brave Prince

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0252
- **Last modified:** 2025-04-16

## Description

Brave Prince is a Korean-language implant that was first observed in the wild in December 2017. It contains similar code and behavior to Gold Dragon, and was seen along with Gold Dragon and RunningRAT in operations surrounding the 2018 Pyeongchang Winter Olympics.

## Techniques used

- **T1012 Query Registry** — Brave Prince gathers information about the Registry.
- **T1016 System Network Configuration Discovery** — Brave Prince gathers network configuration information as well as the ARP cache.
- **T1048.003 Exfiltration Over Alternative Protocol: Exfiltration Over Unencrypted Non-C2 Protocol** — Some Brave Prince variants have used South Korea's Daum email service to exfiltrate information, and later variants have posted the data to a web server via an HTTP post command.
- **T1057 Process Discovery** — Brave Prince lists the running processes.
- **T1082 System Information Discovery** — Brave Prince collects hard drive content and system configuration information.
- **T1083 File and Directory Discovery** — Brave Prince gathers file and directory information from the victim’s machine.
- **T1685 Disable or Modify Tools** — Brave Prince terminates antimalware processes.

## Used by

- **G0094 Kimsuky** (group)
