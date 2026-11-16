# G0138 — Andariel

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **Also known as:** Silent Chollima, PLUTONIUM, Onyx Sleet
- **ATT&CK URL:** https://attack.mitre.org/groups/G0138
- **Last modified:** 2026-07-31

## Description

Andariel is a North Korean state-sponsored threat group that has been active since at least 2009. Andariel has primarily focused its operations--which have included destructive attacks--against South Korean government agencies, military organizations, and a variety of domestic companies; they have also conducted cyber financial operations against ATMs, banks, and cryptocurrency exchanges. Andariel's notable activity includes Operation Black Mine, Operation GoldenAxe, and Campaign Rifle.

Andariel is considered a sub-set of Lazarus Group, and has been attributed to North Korea's Reconnaissance General Bureau.

North Korean group definitions are known to have significant overlap, and some security researchers report all North Korean state-sponsored cyber activity under the name Lazarus Group instead of tracking clusters or subgroups.

## Techniques used

- **T1005 Data from Local System** — Andariel has collected large numbers of files from compromised network systems for later extraction.
- **T1027.003 Obfuscated Files or Information: Steganography** — Andariel has hidden malicious executables within PNG files.
- **T1049 System Network Connections Discovery** — Andariel has used the `netstat -naop tcp` command to display TCP connections on a victim's machine.
- **T1057 Process Discovery** — Andariel has used `tasklist` to enumerate processes and find a specific string.
- **T1105 Ingress Tool Transfer** — Andariel has downloaded additional tools and malware onto compromised hosts.
- **T1189 Drive-by Compromise** — Andariel has used watering hole attacks, often with zero-day exploits, to gain initial access to victims within a specific IP range.
- **T1203 Exploitation for Client Execution** — Andariel has exploited numerous ActiveX vulnerabilities, including zero-days.
- **T1204.002 User Execution: Malicious File** — Andariel has attempted to lure victims into enabling malicious macros within email attachments.
- **T1566.001 Phishing: Spearphishing Attachment** — Andariel has conducted spearphishing campaigns that included malicious Word or Excel attachments.
- **T1588.001 Obtain Capabilities: Malware** — Andariel has used a variety of publicly-available remote access Trojans (RATs) for its operations.
- **T1590.005 Gather Victim Network Information: IP Addresses** — Andariel has limited its watering hole attacks to specific IP address ranges.
- **T1592.002 Gather Victim Host Information: Software** — Andariel has inserted a malicious script within compromised websites to collect potential victim information such as browser type, system language, Flash Player version, and other data.

## Software used

- **S0032 gh0st RAT**
- **S0433 Rifdoor**
