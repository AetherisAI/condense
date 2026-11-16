# G0065 — Leviathan

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **Also known as:** MUDCARP, Kryptonite Panda, Gadolinium, BRONZE MOHAWK, TEMP.Jumper, APT40, TEMP.Periscope, Gingham Typhoon
- **ATT&CK URL:** https://attack.mitre.org/groups/G0065
- **Last modified:** 2026-07-31

## Description

Leviathan is a Chinese state-sponsored cyber espionage group that has been attributed to the Ministry of State Security's (MSS) Hainan State Security Department and an affiliated front company. Active since at least 2009, Leviathan has targeted the following sectors: academia, aerospace/aviation, biomedical, defense industrial base, government, healthcare, manufacturing, maritime, and transportation across the US, Canada, Australia, Europe, the Middle East, and Southeast Asia.

## Techniques used

- **T1003 OS Credential Dumping** — Leviathan has used publicly available tools to dump password hashes, including HOMEFRY.
- **T1003.001 OS Credential Dumping: LSASS Memory** — Leviathan has used publicly available tools to dump password hashes, including ProcDump and WCE.
- **T1021.001 Remote Services: Remote Desktop Protocol** — Leviathan has targeted RDP credentials and used it to move through the victim environment.
- **T1021.004 Remote Services: SSH** — Leviathan used ssh for internal reconnaissance.
- **T1027.001 Obfuscated Files or Information: Binary Padding** — Leviathan has inserted garbage characters into code, presumably to avoid anti-virus detection.
- **T1027.003 Obfuscated Files or Information: Steganography** — Leviathan has used steganography to hide stolen data inside other files stored on Github.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — Leviathan has obfuscated code using base64.
- **T1027.015 Obfuscated Files or Information: Compression** — Leviathan has obfuscated code using gzip compression.
- **T1041 Exfiltration Over C2 Channel** — Leviathan has exfiltrated data over its C2 channel.
- **T1047 Windows Management Instrumentation** — Leviathan has used WMI for execution.
- **T1055.001 Process Injection: Dynamic-link Library Injection** — Leviathan has utilized techniques like reflective DLL loading to write a DLL into memory and load a shell that provides backdoor access to the victim.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — Leviathan has used PowerShell for execution.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — Leviathan has used VBScript.
- **T1074.001 Data Staged: Local Data Staging** — Leviathan has used C:\Windows\Debug and C:\Perflogs as staging directories.
- **T1074.002 Data Staged: Remote Data Staging** — Leviathan has staged data remotely prior to exfiltration.
- **T1078 Valid Accounts** — Leviathan has obtained valid accounts to gain initial access.
- **T1090.003 Proxy: Multi-hop Proxy** — Leviathan has used multi-hop proxies to disguise the source of their malicious traffic.
- **T1102.003 Web Service: One-Way Communication** — Leviathan has received C2 instructions from user profiles created on legitimate websites such as Github and TechNet.
- **T1105 Ingress Tool Transfer** — Leviathan has downloaded additional scripts and files from adversary-controlled servers.
- **T1133 External Remote Services** — Leviathan has used external remote services such as virtual private networks (VPN) to gain initial access.
- **T1140 Deobfuscate/Decode Files or Information** — Leviathan has used a DLL known as SeDll to decrypt and execute other JavaScript backdoors.
- **T1189 Drive-by Compromise** — Leviathan has infected victims using watering holes.
- **T1190 Exploit Public-Facing Application** — Leviathan has used exploits against publicly-disclosed vulnerabilities for initial access into victim networks.
- **T1197 BITS Jobs** — Leviathan has used BITSAdmin to download additional tools.
- **T1203 Exploitation for Client Execution** — Leviathan has exploited multiple Microsoft Office and .NET vulnerabilities for execution, including CVE-2017-0199, CVE-2017-8759, and CVE-2017-11882.
- **T1204.001 User Execution: Malicious Link** — Leviathan has sent spearphishing email links attempting to get a user to click.
- **T1204.002 User Execution: Malicious File** — Leviathan has sent spearphishing attachments attempting to get a user to click.
- **T1218.010 System Binary Proxy Execution: Regsvr32** — Leviathan has used regsvr32 for execution.
- **T1505.003 Server Software Component: Web Shell** — Leviathan relies on web shells for an initial foothold as well as persistence into the victim's systems.
- **T1534 Internal Spearphishing** — Leviathan has conducted internal spearphishing within the victim's environment for lateral movement.
- **T1546.003 Event Triggered Execution: Windows Management Instrumentation Event Subscription** — Leviathan has used WMI for persistence.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — Leviathan has used JavaScript to create a shortcut file in the Startup folder that points to its main backdoor.
- **T1547.009 Boot or Logon Autostart Execution: Shortcut Modification** — Leviathan has used JavaScript to create a shortcut file in the Startup folder that points to its main backdoor.
- **T1553.002 Subvert Trust Controls: Code Signing** — Leviathan has used stolen code signing certificates to sign malware.
- **T1559.002 Inter-Process Communication: Dynamic Data Exchange** — Leviathan has utilized OLE as a method to insert malicious content inside various phishing documents.
- **T1560 Archive Collected Data** — Leviathan has archived victim's data prior to exfiltration.
- **T1566.001 Phishing: Spearphishing Attachment** — Leviathan has sent spearphishing emails with malicious attachments, including .rtf, .doc, and .xls files.
- **T1566.002 Phishing: Spearphishing Link** — Leviathan has sent spearphishing emails with links, often using a fraudulent lookalike domain and stolen branding.
- **T1567.002 Exfiltration Over Web Service: Exfiltration to Cloud Storage** — Leviathan has used an uploader known as LUNCHMONEY that can exfiltrate files to Dropbox.
- **T1572 Protocol Tunneling** — Leviathan has used protocol tunneling to further conceal C2 communications and infrastructure.
- **T1583.001 Acquire Infrastructure: Domains** — Leviathan has established domains that impersonate legitimate entities to use for targeting efforts.
- **T1584.004 Compromise Infrastructure: Server** — Leviathan has used compromised legitimate websites as command and control nodes for operations.
- **T1584.008 Compromise Infrastructure: Network Devices** — Leviathan has used compromised networking devices, such as small office/home office (SOHO) devices, as operational command and control infrastructure.
- **T1585.001 Establish Accounts: Social Media Accounts** — Leviathan has created new social media accounts for targeting efforts.
- **T1585.002 Establish Accounts: Email Accounts** — Leviathan has created new email accounts for targeting efforts.
- **T1586.001 Compromise Accounts: Social Media Accounts** — Leviathan has compromised social media accounts to conduct social engineering attacks.
- **T1586.002 Compromise Accounts: Email Accounts** — Leviathan has compromised email accounts to conduct social engineering attacks.
- **T1587.004 Develop Capabilities: Exploits** — Leviathan has rapidly transformed and adapted public exploit proof-of-concept code for new vulnerabilities and utilized them against target networks.
- **T1589.001 Gather Victim Identity Information: Credentials** — Leviathan has collected compromised credentials to use for targeting efforts.
- **T1595.002 Active Scanning: Vulnerability Scanning** — Leviathan has conducted reconnaissance against target networks of interest looking for vulnerable, end-of-life, or no longer maintainted devices against which to rapidly deploy exploits.

## Software used

- **S0005 Windows Credential Editor**
- **S0020 China Chopper**
- **S0021 Derusbi**
- **S0032 gh0st RAT**
- **S0039 Net**
- **S0069 BLACKCOFFEE**
- **S0110 at**
- **S0154 Cobalt Strike**
- **S0183 Tor**
- **S0190 BITSAdmin**
- **S0194 PowerSploit**
- **S0228 NanHaiShu**
- **S0229 Orz**
- **S0232 HOMEFRY**
- **S0233 MURKYTOP**
- **S0363 Empire**
- **S0642 BADFLICK**

## Campaigns

- **C0049 Leviathan Australian Intrusions** — Leviathan Australian Intrusions was conducted by the Leviathan threat actor.
