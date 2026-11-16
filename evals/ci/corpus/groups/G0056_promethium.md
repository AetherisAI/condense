# G0056 — PROMETHIUM

- **Type:** group
- **Domain:** Enterprise ATT&CK, Mobile ATT&CK
- **Also known as:** StrongPity
- **ATT&CK URL:** https://attack.mitre.org/groups/G0056
- **Last modified:** 2026-07-31

## Description

PROMETHIUM is an activity group focused on espionage that has been active since at least 2012. The group has conducted operations globally with a heavy emphasis on Turkish targets. PROMETHIUM has demonstrated similarity to another activity group called NEODYMIUM due to overlapping victim and campaign characteristics.

## Techniques used

- **T1036.004 Masquerading: Masquerade Task or Service** — PROMETHIUM has named services to appear legitimate.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — PROMETHIUM has disguised malicious installer files by bundling them with legitimate software installers.
- **T1078.003 Valid Accounts: Local Accounts** — PROMETHIUM has created admin accounts on a compromised host.
- **T1189 Drive-by Compromise** — PROMETHIUM has used watering hole attacks to deliver malicious versions of legitimate installers.
- **T1204.002 User Execution: Malicious File** — PROMETHIUM has attempted to get users to execute compromised installation files for legitimate software including compression applications, security software, browsers, file recovery applications, and other tools and utilities.
- **T1205.001 Traffic Signaling: Port Knocking** — PROMETHIUM has used a script that configures the knockd service and firewall to only accept C2 connections from systems that use a specified sequence of knock ports.
- **T1543.003 Create or Modify System Process: Windows Service** — PROMETHIUM has created new services and modified existing services for persistence.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — PROMETHIUM has used Registry run keys to establish persistence.
- **T1553.002 Subvert Trust Controls: Code Signing** — PROMETHIUM has signed code with self-signed certificates.
- **T1587.002 Develop Capabilities: Code Signing Certificates** — PROMETHIUM has created self-signed certificates to sign malicious installers.
- **T1587.003 Develop Capabilities: Digital Certificates** — PROMETHIUM has created self-signed digital certificates for use in HTTPS C2 traffic.

## Software used

- **S0178 Truvasys**
- **S0491 StrongPity**

## Campaigns

- **C0033 C0033**
