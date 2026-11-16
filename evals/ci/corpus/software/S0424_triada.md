# S0424 — Triada

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0424
- **Last modified:** 2025-04-25

## Description

Triada was first reported in 2016 as a second stage malware. Later versions in 2019 appeared with new techniques and as an initial downloader of other Trojan apps.

## Techniques used

- **T1407 Download New Code at Runtime** — Triada utilizes a backdoor in a Play Store app to install additional trojanized apps from the Command and Control server.
- **T1418 Software Discovery** — Triada is able to modify code within the com.android.systemui application to gain access to `GET_REAL_TASKS` permissions. This permission enables access to information about applications currently on the foreground and other recently used apps.
- **T1474.003 Supply Chain Compromise: Compromise Software Supply Chain** — Triada was added into the Android system by a third-party vendor identified as Yehuo or Blazefire during the production process.
- **T1532 Archive Collected Data** — Triada encrypts data prior to exfiltration.
- **T1631.001 Process Injection: Ptrace System Calls** — Triada injects code into the Zygote process to effectively include itself in all forked processes. Additionally, code is injected into the Android Play Store App, web browser applications, and the system UI application.
- **T1636.004 Protected User Data: SMS Messages** — Triada variants capture transaction data from SMS-based in-app purchases.
- **T1643 Generate Traffic from Victim** — Triada can redirect ad banner URLs on websites visited by the user to specific ad URLs.
- **T1646 Exfiltration Over C2 Channel** — Triada utilized HTTP to exfiltrate data through POST requests to the command and control server.
