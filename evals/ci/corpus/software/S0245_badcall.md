# S0245 — BADCALL

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0245
- **Last modified:** 2026-05-12

## Description

BADCALL is a Trojan malware variant used by the group Lazarus Group.

## Techniques used

- **T1001.003 Data Obfuscation: Protocol or Service Impersonation** — BADCALL uses a FakeTLS method during C2.
- **T1016 System Network Configuration Discovery** — BADCALL collects the network adapter information.
- **T1082 System Information Discovery** — BADCALL collects the computer name and host name on the compromised system.
- **T1090 Proxy** — BADCALL functions as a proxy server between the victim and C2 server.
- **T1112 Modify Registry** — BADCALL modifies the firewall Registry key `SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\StandardProfileGloballyOpenPorts\\List`.
- **T1571 Non-Standard Port** — BADCALL communicates on ports 443 and 8000 with a FakeTLS method.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — BADCALL encrypts C2 traffic using an XOR/ADD cipher.
- **T1686.003 Disable or Modify System Firewall: Windows Host Firewall** — BADCALL disables the Windows firewall before binding to a port.

## Used by

- **G0032 Lazarus Group** (group)
