# G0066 — Elderwood

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **Also known as:** Elderwood Gang, Beijing Group, Sneaky Panda
- **ATT&CK URL:** https://attack.mitre.org/groups/G0066
- **Last modified:** 2026-07-31

## Description

Elderwood is a suspected Chinese cyber espionage group that was reportedly responsible for the 2009 Google intrusion known as Operation Aurora. The group has targeted defense organizations, supply chain manufacturers, human rights and nongovernmental organizations (NGOs), and IT service providers.

## Techniques used

- **T1027.002 Obfuscated Files or Information: Software Packing** — Elderwood has packed malware payloads before delivery to victims.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — Elderwood has encrypted documents and malicious executables.
- **T1105 Ingress Tool Transfer** — The Ritsol backdoor trojan used by Elderwood can download files onto a compromised host from a remote location.
- **T1189 Drive-by Compromise** — Elderwood has delivered zero-day exploits and malware to victims by injecting malicious code into specific public Web pages visited by targets within a particular sector.
- **T1203 Exploitation for Client Execution** — Elderwood has used exploitation of endpoint software, including Microsoft Internet Explorer Adobe Flash vulnerabilities, to gain execution. They have also used zero-day exploits.
- **T1204.001 User Execution: Malicious Link** — Elderwood has leveraged multiple types of spearphishing in order to attempt to get a user to open links.
- **T1204.002 User Execution: Malicious File** — Elderwood has leveraged multiple types of spearphishing in order to attempt to get a user to open attachments.
- **T1566.001 Phishing: Spearphishing Attachment** — Elderwood has delivered zero-day exploits and malware to victims via targeted emails containing malicious attachments.
- **T1566.002 Phishing: Spearphishing Link** — Elderwood has delivered zero-day exploits and malware to victims via targeted emails containing a link to malicious content hosted on an uncommon Web server.

## Software used

- **S0012 PoisonIvy**
- **S0203 Hydraq**
- **S0204 Briba**
- **S0205 Naid**
- **S0206 Wiarp**
- **S0207 Vasport**
- **S0208 Pasam**
- **S0210 Nerex**
- **S0211 Linfo**
