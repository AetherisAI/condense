# T1646 — Exfiltration Over C2 Channel

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Exfiltration
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1646
- **Last modified:** 2026-05-12

## Description

Adversaries may steal data by exfiltrating it over an existing command and control channel. Stolen data is encoded into the normal communications channel using the same protocol as command and control communications.

## Detection strategies

- **DET0615 Detection of Exfiltration Over C2 Channel**
  - AN1671 (Android): Exfiltration Over C2 Channel can be difficult to detect, and therefore enterprises may be better served focusing on detection at other stages of adversarial behavior.
  - AN1672 (iOS): Exfiltration Over C2 Channel can be difficult to detect, and therefore enterprises may be better served focusing on detection at other stages of adversarial behavior.

## Procedure examples

- **C0016 Operation Dust Storm** (campaign) — During Operation Dust Storm, the threat actors used Android backdoors that would send information and data from a victim's mobile device to the C2 servers.
- **C0033 C0033** (campaign) — During C0033, PROMETHIUM used StrongPity to exfiltrate to the C2 server using HTTPS.
- **S0326 RedDrop** (software) — RedDrop uses standard HTTP for exfiltration.
- **S0399 Pallas** (software) — Pallas exfiltrates data using HTTP.
- **S0418 ViceLeaker** (software) — ViceLeaker uses HTTP data exfiltration.
- **S0421 GolfSpy** (software) — GolfSpy exfiltrates data using HTTP POST requests.
- **S0424 Triada** (software) — Triada utilized HTTP to exfiltrate data through POST requests to the command and control server.
- **S0490 XLoader for iOS** (software) — XLoader for iOS has exfiltrated data using HTTP requests.
- **S0507 eSurv** (software) — eSurv has exfiltrated data using HTTP PUT requests.
- **S0551 GoldenEagle** (software) — GoldenEagle has exfiltrated data via both SMTP and HTTP.
- **S1054 Drinik** (software) — Drinik can send stolen data back to the C2 server.
- **S1055 SharkBot** (software) — SharkBot can exfiltrate captured user credentials and event logs back to the C2 server.
- **S1061 AbstractEmu** (software) — AbstractEmu can send large amounts of device data over its C2 channel, including the device’s manufacturer, model, version and serial number, telephone number, and IP address.
- **S1067 FluBot** (software) — FluBot can send contact lists to its C2 server.
- **S1077 Hornbill** (software) — Hornbill can exfiltrate data back to the C2 server using HTTP.
- **S1079 BOULDSPY** (software) — BOULDSPY has exfiltrated cached data from infected devices.
- **S1080 Fakecalls** (software) — Fakecalls can send exfiltrated data back to the C2 server.
- **S1082 Sunbird** (software) — Sunbird can exfiltrate compressed ZIP files containing gathered info to C2 infrastructure.
- **S1083 Chameleon** (software) — Chameleon has sent stolen data over HTTP.
- **S1093 FlyTrap** (software) — FlyTrap can use HTTP to exfiltrate data to the C2 server.
- **S1094 BRATA** (software) — BRATA has exfiltrated data to the C2 server using HTTP requests.
- **S1095 AhRat** (software) — AhRat can exfiltrate collected data to the C2, such as audio recordings and files.
- **S1185 LightSpy** (software) — LightSpy has exfiltrated collected data to the C2.
- **S1215 Binary Validator** (software) — Binary Validator has exfiltrated collected data to the C2 server.
- **S1225 CherryBlos** (software) — CherryBlos has exfiltrated credentials collected from pictures that have been analyzed using optical character recognition (OCR).
- **S1231 GodFather** (software) — GodFather has exfiltrated sensitive information over C2.
- **S1241 RatMilad** (software) — RatMilad has exfiltrated collected data to the C2.
- **S9004 Crocodilus** (software) — Crocodilus has the ability to send stolen data to C2.
- **S9005 DocSwap** (software) — DocSwap has used a hardcoded IP address and port for C2 and exfiltration over socket communication.
- **S9006 VajraSpy** (software) — VajraSpy has exfiltrated captured data to C2 via POST requests.
- **S9040 NGate** (software) — NGate has exfiltrated the victim’s payment card PIN to the C2 server via HTTP.
