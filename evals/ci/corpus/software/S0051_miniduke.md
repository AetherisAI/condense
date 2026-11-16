# S0051 — MiniDuke

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0051
- **Last modified:** 2025-04-25

## Description

MiniDuke is malware that was used by APT29 from 2010 to 2015. The MiniDuke toolset consists of multiple downloader and backdoor components. The loader has been used with other MiniDuke components as well as in conjunction with CosmicDuke and PinchDuke.

## Techniques used

- **T1008 Fallback Channels** — MiniDuke uses Google Search to identify C2 servers if its primary C2 method via Twitter is not working.
- **T1027 Obfuscated Files or Information** — MiniDuke can use control flow flattening to obscure code.
- **T1071.001 Application Layer Protocol: Web Protocols** — MiniDuke uses HTTP and HTTPS for command and control.
- **T1082 System Information Discovery** — MiniDuke can gather the hostname on a compromised machine.
- **T1083 File and Directory Discovery** — MiniDuke can enumerate local drives.
- **T1090.001 Proxy: Internal Proxy** — MiniDuke can can use a named pipe to forward communications from one compromised machine with internet access to other compromised machines.
- **T1102.001 Web Service: Dead Drop Resolver** — Some MiniDuke components use Twitter to initially obtain the address of a C2 server or as a backup if no hard-coded C2 server responds.
- **T1105 Ingress Tool Transfer** — MiniDuke can download additional encrypted backdoors onto the victim via GIF files.
- **T1568.002 Dynamic Resolution: Domain Generation Algorithms** — MiniDuke can use DGA to generate new Twitter URLs for C2.

## Used by

- **C0023 Operation Ghost** (campaign) — For Operation Ghost, APT29 used MiniDuke as a second-stage backdoor.
- **G0016 APT29** (group)
