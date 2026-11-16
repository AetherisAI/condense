# S0302 — Twitoor

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S0302
- **Last modified:** 2026-09-02

## Description

Twitoor is a dropper application capable of receiving commands from social media.

## Techniques used

- **T1476 Deliver Malicious Application via Other Means** — Twitoor has the ability to install adversary-specified applications.
- **T1481.003 Web Service: One-Way Communication** — Twitoor can be controlled via Twitter.
- **T1521 Encrypted Channel** — Twitoor encrypts its C2 communication.
- **T1628.001 Hide Artifacts: Suppress Application Icon** — Twitoor can hide its presence on the system.
