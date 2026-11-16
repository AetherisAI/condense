# G1001 — HEXANE

- **Type:** group
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Also known as:** Lyceum, Siamesekitten, Spirlin
- **ATT&CK URL:** https://attack.mitre.org/groups/G1001
- **Last modified:** 2026-07-31

## Description

HEXANE is a cyber espionage threat group that has targeted oil & gas, telecommunications, aviation, and internet service provider organizations since at least 2017. Targeted companies have been located in the Middle East and Africa, including Israel, Saudi Arabia, Kuwait, Morocco, and Tunisia. HEXANE's TTPs appear similar to APT33 and OilRig but due to differences in victims and tools it is tracked as a separate entity.

## Techniques used

- **T1010 Application Window Discovery** — HEXANE has used a PowerShell-based keylogging tool to capture the window title.
- **T1016 System Network Configuration Discovery** — HEXANE has used Ping and `tracert` for network discovery.
- **T1016.001 System Network Configuration Discovery: Internet Connection Discovery** — HEXANE has used tools including BITSAdmin to test internet connectivity from compromised hosts.
- **T1018 Remote System Discovery** — HEXANE has used `net view` to enumerate domain machines.
- **T1021.001 Remote Services: Remote Desktop Protocol** — HEXANE has used remote desktop sessions for lateral movement.
- **T1027.010 Obfuscated Files or Information: Command Obfuscation** — HEXANE has used Base64-encoded scripts.
- **T1033 System Owner/User Discovery** — HEXANE has run `whoami` on compromised machines to identify the current user.
- **T1049 System Network Connections Discovery** — HEXANE has used netstat to monitor connections to specific ports.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — HEXANE has used a scheduled task to establish persistence for a keylogger.
- **T1056.001 Input Capture: Keylogging** — HEXANE has used a PowerShell-based keylogger named `kl.ps1`.
- **T1057 Process Discovery** — HEXANE has enumerated processes on targeted systems.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — HEXANE has used PowerShell-based tools and scripts for discovery and collection on compromised hosts.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — HEXANE has used a VisualBasic script named `MicrosoftUpdator.vbs` for execution of a PowerShell keylogger.
- **T1069.001 Permission Groups Discovery: Local Groups** — HEXANE has run `net localgroup` to enumerate local groups.
- **T1082 System Information Discovery** — HEXANE has collected the hostname of a compromised machine.
- **T1102.002 Web Service: Bidirectional Communication** — HEXANE has used cloud services, including OneDrive, for C2.
- **T1105 Ingress Tool Transfer** — HEXANE has downloaded additional payloads and malicious scripts onto a compromised host.
- **T1110 Brute Force** — HEXANE has used brute force attacks to compromise valid credentials.
- **T1110.003 Brute Force: Password Spraying** — HEXANE has used password spraying attacks to obtain valid credentials.
- **T1204.002 User Execution: Malicious File** — HEXANE has relied on victim's executing malicious file attachments delivered via email or embedded within actor-controlled websites to deliver malware.
- **T1518 Software Discovery** — HEXANE has enumerated programs installed on an infected machine.
- **T1534 Internal Spearphishing** — HEXANE has conducted internal spearphishing attacks against executives, HR, and IT personnel to gain information and access.
- **T1546.003 Event Triggered Execution: Windows Management Instrumentation Event Subscription** — HEXANE has used WMI event subscriptions for persistence.
- **T1555 Credentials from Password Stores** — HEXANE has run `cmdkey` on victim machines to identify stored credentials.
- **T1555.003 Credentials from Password Stores: Credentials from Web Browsers** — HEXANE has used a Mimikatz-based tool and a PowerShell script to steal passwords from Google Chrome.
- **T1567.002 Exfiltration Over Web Service: Exfiltration to Cloud Storage** — HEXANE has used cloud services, including OneDrive, for data exfiltration.
- **T1583.001 Acquire Infrastructure: Domains** — HEXANE has registered and operated domains for campaigns, often using a security or web technology theme or impersonating the targeted organization.
- **T1583.002 Acquire Infrastructure: DNS Server** — HEXANE has set up custom DNS servers to send commands to compromised hosts via TXT records.
- **T1585.001 Establish Accounts: Social Media Accounts** — HEXANE has established fraudulent LinkedIn accounts impersonating HR department employees to target potential victims with fake job offers.
- **T1585.002 Establish Accounts: Email Accounts** — HEXANE has established email accounts for use in domain registration including for ProtonMail addresses.
- **T1586.002 Compromise Accounts: Email Accounts** — HEXANE has used compromised accounts to send spearphishing emails.
- **T1588.002 Obtain Capabilities: Tool** — HEXANE has acquired, and sometimes customized, open source tools such as Mimikatz, Empire, VNC remote access software, and DIG.net.
- **T1589 Gather Victim Identity Information** — HEXANE has identified specific potential victims at targeted organizations.
- **T1589.002 Gather Victim Identity Information: Email Addresses** — HEXANE has targeted executives, human resources staff, and IT personnel for spearphishing.
- **T1591.004 Gather Victim Org Information: Identify Roles** — HEXANE has identified executives, HR, and IT staff at victim organizations for further targeting.
- **T1608.001 Stage Capabilities: Upload Malware** — HEXANE has staged malware on fraudulent websites set up to impersonate targeted organizations.

## Software used

- **S0002 Mimikatz**
- **S0097 Ping**
- **S0100 ipconfig**
- **S0104 netstat**
- **S0190 BITSAdmin**
- **S0363 Empire**
- **S0378 PoshC2**
- **S1014 DanBot**
- **S1015 Milan**
- **S1019 Shark**
- **S1020 Kevin**
- **S1021 DnsSystem**
