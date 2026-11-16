# S0160 — certutil

- **Type:** software (tool)
- **Domain:** Enterprise ATT&CK
- **Also known as:** certutil.exe
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0160
- **Last modified:** 2026-05-12

## Description

certutil is a command-line utility that can be used to obtain certificate authority information and configure Certificate Services.

## Techniques used

- **T1105 Ingress Tool Transfer** — certutil can be used to download files from a given URL.
- **T1140 Deobfuscate/Decode Files or Information** — certutil has been used to decode binaries hidden inside certificate files as Base64 information.
- **T1553.004 Subvert Trust Controls: Install Root Certificate** — certutil can be used to install browser root certificates as a precursor to performing Adversary-in-the-Middle between connections to banking websites. Example command: `certutil -addstore -f -user ROOT ProgramData\cert512121.der`.
- **T1560.001 Archive Collected Data: Archive via Utility** — certutil may be used to Base64 encode collected data.

## Used by

- **C0040 APT41 DUST** (campaign) — APT41 DUST used certutil to load and execute DUSTPAN.
- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, the adversaries decoded a Base64-encoded ZIP archive using the built-in certutil.
- **G0007 APT28** (group)
- **G0010 Turla** (group)
- **G0027 Threat Group-3390** (group)
- **G0030 Lotus Blossom** (group) — Lotus Blossom has used certutil during operations.
- **G0045 menuPass** (group)
- **G0049 OilRig** (group)
- **G0075 Rancor** (group)
- **G0094 Kimsuky** (group) — Kimsuky has utilized certutil to decode a malicious payload.
- **G0096 APT41** (group)
- **G0126 Higaisa** (group)
- **G1006 Earth Lusca** (group)
- **G1016 FIN13** (group)
- **G1017 Volt Typhoon** (group)
- **G1051 Medusa Group** (group) — Medusa Group has utilized certutil to download additional tools within victim environments.
