# G1055 — VOID MANTICORE

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **Also known as:** COBALT MYSTIQUE, Handala Hack, Homeland Justice, Karma, Karmabelow80, BANISHED KITTEN, Red Sandstorm
- **ATT&CK URL:** https://attack.mitre.org/groups/G1055
- **Last modified:** 2026-07-31

## Description

VOID MANTICORE is a threat group assessed to operate on behalf of Iran’s Ministry of Intelligence and Security (MOIS). Active since at least mid-2022, VOID MANTICORE has targeted government entities, critical infrastructure, and private sector organizations across Albania, Israel, and the United States. VOID MANTICORE conducts destructive cyber operations, combining wiper attacks with hack-and-leak campaigns. The group has operated under multiple public-facing personas, including HomeLand Justice in operations against Albania, Karma and Karma Below in campaigns targeting Israeli organizations, and Handala Hack, its current primary persona, which has claimed activity against Israeli and U.S. entities, including a March 2026 attack against Stryker Corporation. VOID MANTICORE has been observed collaborating with Scarred Manticore, which has been linked to initial access operations preceding VOID MANTICORE’s activity.

## Techniques used

- **T1003.001 OS Credential Dumping: LSASS Memory** — VOID MANTICORE has dumped LSASS credentials using `comsvcs.dll` via `rundll32.exe`.
- **T1005 Data from Local System** — VOID MANTICORE has collected cached data and files from within the victim environment.
- **T1021.001 Remote Services: Remote Desktop Protocol** — VOID MANTICORE has used RDP to move laterally within the victim environment.
- **T1027.015 Obfuscated Files or Information: Compression** — VOID MANTICORE has compressed their payloads by leveraging zip files.
- **T1036.004 Masquerading: Masquerade Task or Service** — VOID MANTICORE has masqueraded as commonly used programs and services on Windows hosts.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — VOID MANTICORE has masqueraded malicious payloads to resemble legitimate applications. VOID MANTICORE has leveraged malicious payloads that use nomenclature associated with common applications that include Pictory, KeePass, WhatsApp, and Telegram.
- **T1041 Exfiltration Over C2 Channel** — VOID MANTICORE malware has exfiltrated collected data via Telegram bot C2 channels using encrypted communications.
- **T1047 Windows Management Instrumentation** — VOID MANTICORE has utilized WMIC to log into the victim host and create a process `process call create “cmd.exe /c copy \\?\\GLOBALROOT\Device\HarddiskVolumeShadowCopy1\windows\system32\config\system c:\users\public”`.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — VOID MANTICORE has utilized PowerShell to execute malware in victim environments.
- **T1059.006 Command and Scripting Interpreter: Python** — VOID MANTICORE has utilized Python scripts to execute its malicious payloads.
- **T1071.001 Application Layer Protocol: Web Protocols** — VOID MANTICORE has utilized HTTPS for communication to C2 domains.
- **T1072 Software Deployment Tools** — VOID MANTICORE has leveraged legitimate built-in features of cloud-based management platforms to include mobile device management (MDM) and Remote Monitoring and Management (RMM) solutions. VOID MANTICORE has also initiated built-in remote wipe instructions using a privileged account within Microsoft Intune.
- **T1074 Data Staged** — VOID MANTICORE has staged compressed files in specified locations prior to exfiltration over C2.
- **T1078 Valid Accounts** — VOID MANTICORE has leveraged valid accounts to log into VPN infrastructure. VOID MANTICORE has used compromised valid credentials to gain access to management infrastructure and enterprise control systems. VOID MANTICORE has also validated and tested authentication using compromised credentials prior to malicious actions.
- **T1078.002 Valid Accounts: Domain Accounts** — VOID MANTICORE has used previously compromised Domain Administrator credentials to maintain persistent access.
- **T1078.004 Valid Accounts: Cloud Accounts** — VOID MANTICORE has leveraged privileged cloud accounts to access cloud-based management consoles to include Microsoft Intune. VOID MANTICORE has also compromised existing accounts within the Microsoft Entra ID environment.
- **T1082 System Information Discovery** — VOID MANTICORE has gathered system information and disseminated it back to C2.
- **T1087.002 Account Discovery: Domain Account** — VOID MANTICORE has utilized ADRecon to enumerate the active directory environment.
- **T1098 Account Manipulation** — VOID MANTICORE has leveraged access to administrative control systems to achieve disruptive effects, consistent with administrative account abuse or privilege escalation within existing access.
- **T1102 Web Service** — VOID MANTICORE has utilized Telegram API for C2.
- **T1105 Ingress Tool Transfer** — VOID MANTICORE has deployed additional payloads from dedicated C2 servers. VOID MANTICORE has also downloaded legitimate tools and software from publicly available services. VOID MANTICORE had utilized VeraCrypt a legitimate disk encrypting utility that was downloaded directly from the website.
- **T1110 Brute Force** — VOID MANTICORE has conducted brute-force attempts against organizational VPN infrastructure.
- **T1110.001 Brute Force: Password Guessing** — VOID MANTICORE has conducted password guessing to gain initial access.
- **T1110.004 Brute Force: Credential Stuffing** — VOID MANTICORE has utilized credential stuffing attacks to obtain initial access to victim environments.
- **T1113 Screen Capture** — VOID MANTICORE has captured screen content during an active Zoom session.
- **T1114.002 Email Collection: Remote Email Collection** — VOID MANTICORE has gathered victim email-content from victim servers.
- **T1119 Automated Collection** — VOID MANTICORE conducted large-scale data exfiltration in the Stryker operation, consistent with automated or scripted collection against enterprise systems.
- **T1123 Audio Capture** — VOID MANTICORE has gathered audio during a Zoom session.
- **T1125 Video Capture** — VOID MANTICORE has collected video from compromised victim devices.
- **T1133 External Remote Services** — VOID MANTICORE has leveraged public facing VPN infrastructure to gain initial access to victim environments.
- **T1190 Exploit Public-Facing Application** — VOID MANTICORE has exploited public facing vulnerabilities within victim environments to include SharePoint CVE-2019-0604.
- **T1199 Trusted Relationship** — VOID MANTICORE has targeted IT and service providers in an effort to obtain credentials, relying largely on compromised VPN accounts for initial access.
- **T1204.002 User Execution: Malicious File** — VOID MANTICORE has delivered malicious payloads that initiate through user execution to include interaction with a masqueraded file. VOID MANTICORE has used trojanized application lures to induce targets into executing malware enabling persistent surveillance.
- **T1213.002 Data from Information Repositories: Sharepoint** — VOID MANTICORE has accessed victim’s public facing SharePoint servers and exfiltrated data.
- **T1219.002 Remote Access Tools: Remote Desktop Software** — VOID MANTICORE has installed NetBird on victim devices to create a mesh network that facilitated control of several victim devices at once.
- **T1484.001 Domain or Tenant Policy Modification: Group Policy Modification** — VOID MANTICORE had utilized Group Policy logon scripts to distribute the malicious payloads to victim devices through the execution of a batch file.
- **T1485 Data Destruction** — VOID MANTICORE has conducted data wiping attacks on compromised systems. VOID MANTICORE has also manually deleted files from compromised hosts, to include selecting all files and then deleting them.
- **T1486 Data Encrypted for Impact** — VOID MANTICORE has utilized legitimate disk encryption utilities to increase likelihood of encrypting system drives and reduce system recovery efforts.
- **T1490 Inhibit System Recovery** — VOID MANTICORE has deleted virtual machines directly from the virtualization platform.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — VOID MANTICORE has created Windows Registry entries to autorun stage two malware payloads to maintain persistence.
- **T1552.002 Unsecured Credentials: Credentials in Registry** — VOID MANTICORE had exported credentials from registry hives to include those stored in HKLM.
- **T1560.001 Archive Collected Data: Archive via Utility** — VOID MANTICORE has stored collected data in a password protected compressed file prior to exfiltration.
- **T1561.001 Disk Wipe: Disk Content Wipe** — VOID MANTICORE has utilized a disk wiping utility to facilitate destructive actions on victim servers. VOID MANTICORE has also utilized legitimate remote disk wiping commands.
- **T1561.002 Disk Wipe: Disk Structure Wipe** — VOID MANTICORE has deployed custom wipers that overwrite system files and the host devices master boot records (MBR) to corrupt or destroy files.
- **T1564.003 Hide Artifacts: Hidden Window** — VOID MANTICORE has utilized PowerShell scripts that run without notifying the user of its execution to include `-nop -w hidden- ep bypass -enc`.
- **T1566 Phishing** — VOID MANTICORE has emailed victims threatening messages. VOID MANTICORE has used phishing as an initial access vector.
- **T1572 Protocol Tunneling** — VOID MANTICORE has used tunneling tools to facilitate destructive attacks on compromised devices.
- **T1583.001 Acquire Infrastructure: Domains** — VOID MANTICORE has registered domains for messaging purposes. VOID MANTICORE has created typosquatted domains and sub-domains in attempts to avoid detection or draw suspicion. VOID MANTICORE has also purchased domains leveraging cryptocurrency platforms to include LiteCoin and Ramzinex. VOID MANTICORE has registered and rotated domains to support public-facing dissemination infrastructure, replacing disrupted domains with new registrations.
- **T1583.003 Acquire Infrastructure: Virtual Private Server** — VOID MANTICORE has utilized VPS solutions for C2.
- **T1583.004 Acquire Infrastructure: Server** — VOID MANTICORE has leveraged backend servers within Iran.
- **T1583.006 Acquire Infrastructure: Web Services** — VOID MANTICORE has obtained access to commercial VPN services to launch malicious activity. VOID MANTICORE has also leveraged Starlink internet services. VOID MANTICORE has used operator-controlled Telegram bots and channels as C2 infrastructure.
- **T1585.001 Establish Accounts: Social Media Accounts** — VOID MANTICORE has created Telegram Accounts. VOID MANTICORE has also leveraged online personas such as Handala Hack, Karma, and Homeland Justice on social media to include Telegram. VOID MANTICORE has established and maintained social media accounts on Twitter/X and Telegram to amplify operational claims and stolen data disclosures.
- **T1585.002 Establish Accounts: Email Accounts** — VOID MANTICORE has created email accounts to send threatening messages to victims to include ‘Handala_Team[@]outlook[.]com’.
- **T1587.001 Develop Capabilities: Malware** — VOID MANTICORE has utilized custom-malware and wipers to include BiBi Wiper.
- **T1588.001 Obtain Capabilities: Malware** — VOID MANTICORE has developed or obtained trojanized applications used for persistent surveillance of targeted individuals.
- **T1588.002 Obtain Capabilities: Tool** — VOID MANTICORE has obtained and utilized commercial VPN services, open-source software and publicly available offensive security tools to facilitate malicious activities.
- **T1589 Gather Victim Identity Information** — VOID MANTICORE has gathered details on their intended victims to aid in social engineering efforts for leveraging tailored themes of attacks.
- **T1595.002 Active Scanning: Vulnerability Scanning** — VOID MANTICORE has scanned victim environments for susceptibility to vulnerability exploitation.
- **T1651 Cloud Administration Command** — VOID MANTICORE has abused built-in remote wipe or factory reset commands to wipe devices managed within an organization’s Cloud management solution impacting laptops, servers, and mobile devices.
- **T1657 Financial Theft** — VOID MANTICORE has conducted data exfiltration and posted stolen information on data leak sites for the purposes of financial and political extortion. VOID MANTICORE has also sold stolen data to prospective buyers for cryptocurrency.
- **T1679 Selective Exclusion** — VOID MANTICORE has avoided interacting with specific directories in order to reduce the likelihood of detection.
- **T1684.001 Social Engineering: Impersonation** — VOID MANTICORE has impersonated individuals familiar to the victim and technical support associated with social messaging services.
- **T1686.003 Disable or Modify System Firewall: Windows Host Firewall** — VOID MANTICORE has disabled Windows Defender protections to allow for follow-on activities within the compromised host.

## Campaigns

- **C0038 HomeLand Justice**
