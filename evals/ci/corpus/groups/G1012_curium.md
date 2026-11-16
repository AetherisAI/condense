# G1012 — CURIUM

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **Also known as:** Crimson Sandstorm, TA456, Tortoise Shell, Yellow Liderc
- **ATT&CK URL:** https://attack.mitre.org/groups/G1012
- **Last modified:** 2026-07-31

## Description

CURIUM is an Iranian threat group, first reported in September 2019 and active since at least July 2018, targeting IT service providers in the Middle East. CURIUM has since invested in building relationships with potential targets via social media over a period of months to establish trust and confidence before sending malware. Security researchers note CURIUM has demonstrated great patience and persistence by chatting with potential targets daily and sending benign files to help lower their security consciousness.

## Techniques used

- **T1005 Data from Local System** — CURIUM has exfiltrated data from a compromised machine.
- **T1041 Exfiltration Over C2 Channel** — CURIUM has used IMAP and SMTPS for exfiltration via tools such as IMAPLoader.
- **T1048.002 Exfiltration Over Alternative Protocol: Exfiltration Over Asymmetric Encrypted Non-C2 Protocol** — CURIUM has used SMTPS to exfiltrate collected data from victims.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — CURIUM has leveraged PowerShell scripts for initial process execution and data gathering in victim environments.
- **T1082 System Information Discovery** — CURIUM deploys information gathering tools focused on capturing IP configuration, running application, system information, and network connectivity information.
- **T1124 System Time Discovery** — CURIUM deployed mechanisms to check system time information following strategic website compromise attacks.
- **T1189 Drive-by Compromise** — CURIUM has used strategic website compromise to infect victims with malware such as IMAPLoader.
- **T1204.002 User Execution: Malicious File** — CURIUM has lured users into opening malicious files delivered via social media.
- **T1505.003 Server Software Component: Web Shell** — CURIUM has been linked to web shells following likely server compromise as an initial access vector into victim networks.
- **T1566.001 Phishing: Spearphishing Attachment** — CURIUM has used phishing with malicious attachments for initial access to victim environments.
- **T1566.003 Phishing: Spearphishing via Service** — CURIUM has used social media to deliver malicious files to victims.
- **T1583.001 Acquire Infrastructure: Domains** — CURIUM created domains to facilitate strategic website compromise and credential capture activities.
- **T1583.003 Acquire Infrastructure: Virtual Private Server** — CURIUM created virtual private server instances to facilitate use of malicious domains and other items.
- **T1583.004 Acquire Infrastructure: Server** — CURIUM has created dedicated servers for command and control and exfiltration purposes.
- **T1584.006 Compromise Infrastructure: Web Services** — CURIUM has compromised legitimate websites to enable strategic website compromise attacks.
- **T1585.001 Establish Accounts: Social Media Accounts** — CURIUM has established a network of fictitious social media accounts, including on Facebook and LinkedIn, to establish relationships with victims, often posing as an attractive woman.
- **T1585.002 Establish Accounts: Email Accounts** — CURIUM has created dedicated email accounts for use with tools such as IMAPLoader.
- **T1598.003 Phishing for Information: Spearphishing Link** — CURIUM used malicious links to adversary-controlled resources for credential harvesting.
- **T1608.004 Stage Capabilities: Drive-by Target** — CURIUM used strategic website compromise to fingerprint then target victims.

## Software used

- **S1152 IMAPLoader** — IMAPLoader was deployed by CURIUM as a post-exploitation payload from strategic website compromise.
