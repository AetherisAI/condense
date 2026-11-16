# G0034 — Sandworm Team

- **Type:** group
- **Domain:** Enterprise ATT&CK, ICS ATT&CK, Mobile ATT&CK
- **Also known as:** ELECTRUM, Telebots, IRON VIKING, BlackEnergy (Group), Quedagh, Voodoo Bear, IRIDIUM, Seashell Blizzard, FROZENBARENTS, APT44
- **ATT&CK URL:** https://attack.mitre.org/groups/G0034
- **Last modified:** 2026-07-31

## Description

Sandworm Team is a destructive threat group that has been attributed to Russia's General Staff Main Intelligence Directorate (GRU) Main Center for Special Technologies (GTsST) military unit 74455. This group has been active since at least 2009.

In October 2020, the US indicted six GRU Unit 74455 officers associated with Sandworm Team for the following cyber operations: the 2015 and 2016 attacks against Ukrainian electrical companies and government organizations, the 2017 worldwide NotPetya attack, targeting of the 2017 French presidential campaign, the 2018 Olympic Destroyer attack against the Winter Olympic Games, the 2018 operation against the Organisation for the Prohibition of Chemical Weapons, and attacks against the country of Georgia in 2018 and 2019. Some of these were conducted with the assistance of GRU Unit 26165, which is also referred to as APT28.

## Techniques used

- **T0819 Exploit Public-Facing Application** — Sandworm Team actors exploited vulnerabilities in GE's Cimplicity HMI and Advantech/Broadwin WebAccess HMI software which had been directly exposed to the internet.
- **T0884 Connection Proxy** — Sandworm Team establishes an internal proxy prior to the installation of backdoors within the network.
- **T1003.001 OS Credential Dumping: LSASS Memory** — Sandworm Team has used its plainpwd tool, a modified version of Mimikatz, and comsvcs.dll to dump Windows credentials from system memory.
- **T1003.003 OS Credential Dumping: NTDS** — Sandworm Team has used `ntdsutil.exe` to back up the Active Directory database, likely for credential access.
- **T1005 Data from Local System** — Sandworm Team has exfiltrated internal documents, files, and other data from compromised hosts.
- **T1018 Remote System Discovery** — Sandworm Team has used a tool to query Active Directory using LDAP, discovering information about computers listed in AD.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — Sandworm Team has copied payloads to the `ADMIN$` share of remote systems and run `net use` to connect to network shares.
- **T1027 Obfuscated Files or Information** — Sandworm Team has used Base64 encoding within malware variants.
- **T1027.010 Obfuscated Files or Information: Command Obfuscation** — Sandworm Team has used ROT13 encoding, AES encryption and compression with the zlib library for their Python-based backdoor.
- **T1033 System Owner/User Discovery** — Sandworm Team has collected the username from a compromised host.
- **T1036 Masquerading** — Sandworm Team masqueraded malicious installers as Windows update packages to evade defense and entice users to execute binaries.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — Sandworm Team has avoided detection by naming a malicious binary explorer.exe.
- **T1040 Network Sniffing** — Sandworm Team has used intercepter-NG to sniff passwords in network traffic.
- **T1041 Exfiltration Over C2 Channel** — Sandworm Team has sent system information to its C2 server using HTTP.
- **T1047 Windows Management Instrumentation** — Sandworm Team has used Impacket’s WMIexec module for remote code execution and VBScript to run WMI queries.
- **T1049 System Network Connections Discovery** — Sandworm Team had gathered user, IP address, and server data related to RDP sessions on a compromised host. It has also accessed network diagram files useful for understanding how a host's network was configured.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — Sandworm Team leveraged SHARPIVORY, a .NET dropper that writes embedded payload to disk and uses scheduled tasks to persist on victim machines.
- **T1056.001 Input Capture: Keylogging** — Sandworm Team has used a keylogger to capture keystrokes by using the SetWindowsHookEx function.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — Sandworm Team has used PowerShell scripts to run a credential harvesting tool in memory to evade defenses.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — Sandworm Team has created VBScripts to run an SSH server.
- **T1070.004 Indicator Removal: File Deletion** — Sandworm Team has used backdoors that can delete files used in an attack from an infected system.
- **T1071.001 Application Layer Protocol: Web Protocols** — Sandworm Team's BCS-server tool connects to the designated C2 server via HTTP.
- **T1072 Software Deployment Tools** — Sandworm Team has used the commercially available tool RemoteExec for agentless remote code execution.
- **T1078 Valid Accounts** — Sandworm Team have used previously acquired legitimate credentials prior to attacks.
- **T1078.002 Valid Accounts: Domain Accounts** — Sandworm Team has used stolen credentials to access administrative accounts within the domain.
- **T1082 System Information Discovery** — Sandworm Team used a backdoor to enumerate information about the infected system's operating system.
- **T1083 File and Directory Discovery** — Sandworm Team has enumerated files on a compromised host.
- **T1087.002 Account Discovery: Domain Account** — Sandworm Team has used a tool to query Active Directory using LDAP, discovering information about usernames listed in AD.
- **T1087.003 Account Discovery: Email Account** — Sandworm Team used malware to enumerate email settings, including usernames and passwords, from the M.E.Doc application.
- **T1090 Proxy** — Sandworm Team's BCS-server tool can create an internal proxy server to redirect traffic from the adversary-controlled C2 to internal servers which may not be connected to the internet, but are interconnected locally.
- **T1102.002 Web Service: Bidirectional Communication** — Sandworm Team has used the Telegram Bot API from Telegram Messenger to send and receive commands to its Python backdoor. Sandworm Team also used legitimate M.E.Doc software update check requests for sending and receiving commands and hosted malicious payloads on putdrive.com.
- **T1105 Ingress Tool Transfer** — Sandworm Team has pushed additional malicious tools onto an infected system to steal user credentials, move laterally, and destroy data.
- **T1106 Native API** — Sandworm Team uses Prestige to disable and restore file system redirection by using the following functions: `Wow64DisableWow64FsRedirection()` and `Wow64RevertWow64FsRedirection()`.
- **T1132.001 Data Encoding: Standard Encoding** — Sandworm Team's BCS-server tool uses base64 encoding and HTML tags for the communication traffic between the C2 server.
- **T1133 External Remote Services** — Sandworm Team has used Dropbear SSH with a hardcoded backdoor password to maintain persistence within the target network. Sandworm Team has also used VPN tunnels established in legitimate software company infrastructure to gain access to internal networks of that software company's users.
- **T1140 Deobfuscate/Decode Files or Information** — Sandworm Team's VBS backdoor can decode Base64-encoded data and save it to the %TEMP% folder. The group also decrypted received information using the Triple DES algorithm and decompresses it using GZip.
- **T1190 Exploit Public-Facing Application** — Sandworm Team exploits public-facing applications for initial access and to acquire infrastructure, such as exploitation of the EXIM mail transfer agent in Linux systems.
- **T1195 Supply Chain Compromise** — Sandworm Team staged compromised versions of legitimate software installers on forums to achieve initial, untargetetd access in victim environments.
- **T1195.002 Supply Chain Compromise: Compromise Software Supply Chain** — Sandworm Team has distributed NotPetya by compromising the legitimate Ukrainian accounting software M.E.Doc and replacing a legitimate software update with a malicious one.
- **T1199 Trusted Relationship** — Sandworm Team has used dedicated network connections from one victim organization to gain unauthorized access to a separate organization. Additionally, Sandworm Team has accessed Internet service providers and telecommunication entities that provide mobile connectivity.
- **T1203 Exploitation for Client Execution** — Sandworm Team has exploited vulnerabilities in Microsoft PowerPoint via OLE objects (CVE-2014-4114) and Microsoft Word via crafted TIFF images (CVE-2013-3906).
- **T1204.001 User Execution: Malicious Link** — Sandworm Team has tricked unwitting recipients into clicking on malicious hyperlinks within emails crafted to resemble trustworthy senders.
- **T1204.002 User Execution: Malicious File** — Sandworm Team has tricked unwitting recipients into clicking on spearphishing attachments and enabling malicious macros embedded within files.
- **T1213.006 Data from Information Repositories: Databases** — Sandworm Team exfiltrates data of interest from enterprise databases using Adminer.
- **T1218.011 System Binary Proxy Execution: Rundll32** — Sandworm Team used a backdoor which could execute a supplied DLL using rundll32.exe.
- **T1219 Remote Access Tools** — Sandworm Team has used remote administration tools or remote industrial control system client software for execution and to maliciously release electricity breakers.
- **T1409 Stored Application Data** — Sandworm Team can collect encrypted Telegram and Signal communications.
- **T1485 Data Destruction** — Sandworm Team has used CaddyWiper, SDelete, and the BlackEnergy KillDisk component to overwrite files on victim systems. Additionally, Sandworm Team has used the JUNKMAIL tool to overwrite files with null bytes.
- **T1486 Data Encrypted for Impact** — Sandworm Team has used Prestige ransomware to encrypt data at targeted organizations in transportation and related logistics industries in Ukraine and Poland.
- **T1489 Service Stop** — Sandworm Team attempts to stop the MSSQL Windows service to ensure successful encryption of locked files.
- **T1490 Inhibit System Recovery** — Sandworm Team uses Prestige to delete the backup catalog from the target system using: `C:\Windows\System32\wbadmin.exe delete catalog -quiet` and to delete volume shadow copies using: `C:\Windows\System32\vssadmin.exe delete shadows /all /quiet`.
- **T1491.002 Defacement: External Defacement** — Sandworm Team defaced approximately 15,000 websites belonging to Georgian government, non-government, and private sector organizations in 2019.
- **T1499 Endpoint Denial of Service** — Sandworm Team temporarily disrupted service to Georgian government, non-government, and private sector websites after compromising a Georgian web hosting provider in 2019.
- **T1505.003 Server Software Component: Web Shell** — Sandworm Team has used webshells including P.A.S. Webshell to maintain access to victim networks.
- **T1539 Steal Web Session Cookie** — Sandworm Team used information stealer malware to collect browser session cookies.
- **T1555.003 Credentials from Password Stores: Credentials from Web Browsers** — Sandworm Team's CredRaptor tool can collect saved passwords from various internet browsers.
- **T1561.002 Disk Wipe: Disk Structure Wipe** — Sandworm Team has used the BlackEnergy KillDisk component to corrupt the infected system's master boot record.
- **T1566.001 Phishing: Spearphishing Attachment** — Sandworm Team has delivered malicious Microsoft Office and ZIP file attachments via spearphishing emails.
- **T1566.002 Phishing: Spearphishing Link** — Sandworm Team has crafted phishing emails containing malicious hyperlinks.
- **T1570 Lateral Tool Transfer** — Sandworm Team has used `move` to transfer files to a network share and has copied payloads--such as Prestige ransomware--to an Active Directory Domain Controller and distributed via the Default Domain Group Policy Object. Additionally, Sandworm Team has transferred an ISO file into the OT network to gain initial access.
- **T1571 Non-Standard Port** — Sandworm Team has used port 6789 to accept connections on the group's SSH server.
- **T1583 Acquire Infrastructure** — Sandworm Team used various third-party email campaign management services to deliver phishing emails.
- **T1583.001 Acquire Infrastructure: Domains** — Sandworm Team has registered domain names and created URLs that are often designed to mimic or spoof legitimate websites, such as email login pages, online file sharing and storage websites, and password reset pages, while also hosting these items on legitimate, compromised network infrastructure.
- **T1583.004 Acquire Infrastructure: Server** — Sandworm Team has leased servers from resellers instead of leasing infrastructure directly from hosting companies to enable its operations.
- **T1584.004 Compromise Infrastructure: Server** — Sandworm Team compromised legitimate Linux servers running the EXIM mail transfer agent for use in subsequent campaigns.
- **T1584.005 Compromise Infrastructure: Botnet** — Sandworm Team has used a large-scale botnet to target Small Office/Home Office (SOHO) network devices.
- **T1585.001 Establish Accounts: Social Media Accounts** — Sandworm Team has established social media accounts to disseminate victim internal-only documents and other sensitive data.
- **T1585.002 Establish Accounts: Email Accounts** — Sandworm Team has created email accounts that mimic legitimate organizations for its spearphishing operations.
- **T1586.001 Compromise Accounts: Social Media Accounts** — Sandworm Team creates credential capture webpages to compromise existing, legitimate social media accounts.
- **T1587.001 Develop Capabilities: Malware** — Sandworm Team has developed malware for its operations, including malicious mobile applications and destructive malware such as NotPetya and Olympic Destroyer.
- **T1588.002 Obtain Capabilities: Tool** — Sandworm Team has acquired open-source tools for their operations, including Invoke-PSImage, which was used to establish an encrypted channel from a compromised host to Sandworm Team's C2 server in preparation for the 2018 Winter Olympics attack, as well as Impacket and RemoteExec, which were used in their 2022 Prestige operations. Additionally, Sandworm Team has used Empire, Cobalt Strike and PoshC2.
- **T1588.006 Obtain Capabilities: Vulnerabilities** — In 2017, Sandworm Team conducted technical research related to vulnerabilities associated with websites used by the Korean Sport and Olympic Committee, a Korean power company, and a Korean airport.
- **T1589.002 Gather Victim Identity Information: Email Addresses** — Sandworm Team has obtained valid emails addresses while conducting research against target organizations that were subsequently used in spearphishing campaigns.
- **T1589.003 Gather Victim Identity Information: Employee Names** — Sandworm Team's research of potential victim organizations included the identification and collection of employee information.
- **T1590.001 Gather Victim Network Information: Domain Properties** — Sandworm Team conducted technical reconnaissance of the Parliament of Georgia's official internet domain prior to its 2019 attack.
- **T1591.002 Gather Victim Org Information: Business Relationships** — In preparation for its attack against the 2018 Winter Olympics, Sandworm Team conducted online research of partner organizations listed on an official PyeongChang Olympics partnership site.
- **T1592.002 Gather Victim Host Information: Software** — Sandworm Team has researched software code to enable supply-chain operations, most notably for the 2017 NotPetya attack. Sandworm Team also collected a list of computers using specific software as part of its targeting efforts.
- **T1593 Search Open Websites/Domains** — Sandworm Team researched Ukraine's unique legal entity identifier (called an "EDRPOU" number), including running queries on the EDRPOU website, in preparation for the NotPetya attack. Sandworm Team has also researched third-party websites to help it craft credible spearphishing emails.
- **T1594 Search Victim-Owned Websites** — Sandworm Team has conducted research against potential victim websites as part of its operational planning.
- **T1595.002 Active Scanning: Vulnerability Scanning** — Sandworm Team has scanned network infrastructure for vulnerabilities as part of its operational planning.
- **T1598.003 Phishing for Information: Spearphishing Link** — Sandworm Team has crafted spearphishing emails with hyperlinks designed to trick unwitting recipients into revealing their account credentials.
- **T1608.001 Stage Capabilities: Upload Malware** — Sandworm Team staged compromised versions of legitimate software installers in forums to enable initial access to executing user.
- **T1660 Phishing** — Sandworm Team used SMS-based phishing to target victims with malicious links.
- **T1676 Linked Devices** — Sandworm Team has used the linked devices feature to connect Signal accounts on devices captured on the battlefield to adversary-controlled infrastructure for follow-on exploitation.
- **T1701.001 Command and Scripting Interpreter: PowerShell** — Sandworm Team uses the MS-SQL server xp_cmdshell command, and PowerShell to execute commands.
- **T1701.002 Command and Scripting Interpreter: Windows Command Shell** — Sandworm Team uses the MS-SQL server xp_cmdshell command, and PowerShell to execute commands.

## Software used

- **S0002 Mimikatz**
- **S0029 PsExec**
- **S0039 Net**
- **S0089 BlackEnergy**
- **S0154 Cobalt Strike** — Sandworm Team has used multiple publicly available tools during operations, such as Cobalt Strike.
- **S0195 SDelete** — Sandworm Team has used SDelete for wartime operations in 2022-2023.
- **S0231 Invoke-PSImage**
- **S0342 GreyEnergy**
- **S0343 Exaramel for Windows**
- **S0357 Impacket**
- **S0363 Empire** — Sandworm Team has used multiple publicly available tools during operations, such as Empire.
- **S0365 Olympic Destroyer**
- **S0368 NotPetya**
- **S0378 PoshC2** — Sandworm Team has used multiple publicly available tools during operations, such as PoshC2.
- **S0401 Exaramel for Linux**
- **S0555 CHEMISTGAMES**
- **S0598 P.A.S. Webshell**
- **S0604 Industroyer**
- **S0606 Bad Rabbit**
- **S0607 KillDisk**
- **S0687 Cyclops Blink**
- **S1010 VPNFilter** — VPNFilter is associated with Sandworm Team operations based on reporting on VPNFilter replacement software, Cyclops Blink.
- **S1058 Prestige**
- **S1072 Industroyer2**
- **S1125 AcidRain** — Sandworm Team is linked to AcidRain deployment during the ViaSat KA-SAT incident in 2022.
- **S1167 AcidPour** — AcidPour is associated with Sandworm Team.
- **S1189 Neo-reGeorg**
- **S1190 Kapeka** — Kapeka is associated with Sandworm Team operations and previous malware variants such as GreyEnergy.

## Campaigns

- **C0025 2016 Ukraine Electric Power Attack**
- **C0028 2015 Ukraine Electric Power Attack**
- **C0034 2022 Ukraine Electric Power Attack**
