# G0049 — OilRig

- **Type:** group
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Also known as:** COBALT GYPSY, IRN2, APT34, Helix Kitten, Evasive Serpens, Hazel Sandstorm, EUROPIUM, ITG13, Earth Simnavaz, Crambus, TA452
- **ATT&CK URL:** https://attack.mitre.org/groups/G0049
- **Last modified:** 2026-07-31

## Description

OilRig is a suspected Iranian threat group that has targeted Middle Eastern and international victims since at least 2014. The group has targeted a variety of sectors, including financial, government, energy, chemical, and telecommunications. It appears the group carries out supply chain attacks, leveraging the trust relationship between organizations to attack their primary targets. The group works on behalf of the Iranian government based on infrastructure details that contain references to Iran, use of Iranian infrastructure, and targeting that aligns with nation-state interests.

## Techniques used

- **T0817 Drive-by Compromise** — OilRig has been seen utilizing watering hole attacks to collect credentials which could be used to gain access into ICS networks.
- **T0859 Valid Accounts** — OilRig utilized stolen credentials to gain access to victim machines.
- **T0865 Spearphishing Attachment** — OilRig used spearphishing emails with malicious Microsoft Excel spreadsheet attachments.
- **T0869 Standard Application Layer Protocol** — OilRig communicated with its command and control using HTTP requests.
- **T1003.001 OS Credential Dumping: LSASS Memory** — OilRig has used credential dumping tools such as Mimikatz to steal credentials to accounts logged into the compromised system and to Outlook Web Access.
- **T1003.004 OS Credential Dumping: LSA Secrets** — OilRig has used credential dumping tools such as LaZagne to steal credentials to accounts logged into the compromised system and to Outlook Web Access.
- **T1003.005 OS Credential Dumping: Cached Domain Credentials** — OilRig has used credential dumping tools such as LaZagne to steal credentials to accounts logged into the compromised system and to Outlook Web Access.
- **T1005 Data from Local System** — OilRig has used PowerShell to upload files from compromised systems.
- **T1007 System Service Discovery** — OilRig has used `sc query` on a victim to gather information about services.
- **T1008 Fallback Channels** — OilRig malware ISMAgent falls back to its DNS tunneling mechanism if it is unable to reach the C2 server over HTTP.
- **T1012 Query Registry** — OilRig has used `reg query “HKEY_CURRENT_USER\Software\Microsoft\Terminal Server Client\Default”` on a victim to query the Registry.
- **T1016 System Network Configuration Discovery** — OilRig has run `ipconfig /all` on a victim.
- **T1021.001 Remote Services: Remote Desktop Protocol** — OilRig has used Remote Desktop Protocol for lateral movement. The group has also used tunneling tools to tunnel RDP into the environment.
- **T1021.004 Remote Services: SSH** — OilRig has used Putty to access compromised systems.
- **T1025 Data from Removable Media** — OilRig has used Wireshark’s usbcapcmd utility to capture USB traffic.
- **T1027.005 Obfuscated Files or Information: Indicator Removal from Tools** — OilRig has tested malware samples to determine AV detection and subsequently modified the samples to ensure AV evasion.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — OilRig has encrypted and encoded data in its malware, including by using base64.
- **T1033 System Owner/User Discovery** — OilRig has run `whoami` on a victim.
- **T1036 Masquerading** — OilRig has used .doc file extensions to mask malicious executables.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — OilRig has named a downloaded copy of the Plink tunneling utility as \ProgramData\Adobe.exe.
- **T1046 Network Service Discovery** — OilRig has used the publicly available tool SoftPerfect Network Scanner as well as a custom tool called GOLDIRONY to conduct network scanning.
- **T1047 Windows Management Instrumentation** — OilRig has used WMI for execution.
- **T1048.003 Exfiltration Over Alternative Protocol: Exfiltration Over Unencrypted Non-C2 Protocol** — OilRig has exfiltrated data via Microsoft Exchange and over FTP separately from its primary C2 channel over DNS.
- **T1049 System Network Connections Discovery** — OilRig has used `netstat -an` on a victim to get a listing of network connections.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — OilRig has created scheduled tasks that run a VBScript to execute a payload on victim machines.
- **T1056.001 Input Capture: Keylogging** — OilRig has employed keyloggers including KEYPUNCH and LONGWATCH.
- **T1057 Process Discovery** — OilRig has run `tasklist` on a victim's machine and used infostealers to capture processes.
- **T1059 Command and Scripting Interpreter** — OilRig has used various types of scripting for execution.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — OilRig has used PowerShell scripts for execution, including use of a macro to run a PowerShell command to decode file contents.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — OilRig has used macros to deliver malware such as QUADAGENT and OopsIE. OilRig has used batch scripts.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — OilRig has used VBScript macros for execution on compromised hosts.
- **T1068 Exploitation for Privilege Escalation** — OilRig has exploited the Windows Kernel Elevation of Privilege vulnerability, CVE-2024-30088.
- **T1069.001 Permission Groups Discovery: Local Groups** — OilRig has used `net localgroup administrators` to find local administrators on compromised systems.
- **T1069.002 Permission Groups Discovery: Domain Groups** — OilRig has used `net group /domain`, `net group “domain admins” /domain`, and `net group “Exchange Trusted Subsystem” /domain` to find domain group permission settings.
- **T1070.004 Indicator Removal: File Deletion** — OilRig has deleted files associated with their payload after execution.
- **T1071.001 Application Layer Protocol: Web Protocols** — OilRig has used HTTP for C2.
- **T1071.004 Application Layer Protocol: DNS** — OilRig has used DNS for C2 including the publicly available `requestbin.net` tunneling service.
- **T1078 Valid Accounts** — OilRig has used compromised credentials to access other systems on a victim network.
- **T1078.002 Valid Accounts: Domain Accounts** — OilRig has used an exfiltration tool named STEALHOOK to retreive valid domain credentials.
- **T1082 System Information Discovery** — OilRig has run `hostname` and `systeminfo` on a victim.
- **T1087.001 Account Discovery: Local Account** — OilRig has run `net user`, `net user /domain`, `net group “domain admins” /domain`, and `net group “Exchange Trusted Subsystem” /domain` to get account listings on a victim.
- **T1087.002 Account Discovery: Domain Account** — OilRig has run `net user`, `net user /domain`, `net group “domain admins” /domain`, and `net group “Exchange Trusted Subsystem” /domain` to get account listings on a victim.
- **T1105 Ingress Tool Transfer** — OilRig had downloaded remote files onto victim infrastructure.
- **T1110 Brute Force** — OilRig has used brute force techniques to obtain credentials.
- **T1112 Modify Registry** — OilRig has used reg.exe to modify system configuration.
- **T1113 Screen Capture** — OilRig has a tool called CANDYKING to capture a screenshot of user's desktop.
- **T1115 Clipboard Data** — OilRig has used infostealer tools to copy clipboard data.
- **T1119 Automated Collection** — OilRig has used automated collection.
- **T1120 Peripheral Device Discovery** — OilRig has used tools to identify if a mouse is connected to a targeted system.
- **T1133 External Remote Services** — OilRig uses remote services such as VPN, Citrix, or OWA to persist in an environment.
- **T1137.004 Office Application Startup: Outlook Home Page** — OilRig has abused the Outlook Home Page feature for persistence. OilRig has also used CVE-2017-11774 to roll back the initial patch designed to protect against Home Page abuse.
- **T1140 Deobfuscate/Decode Files or Information** — A OilRig macro has run a PowerShell command to decode file contents. OilRig has also used certutil to decode base64-encoded files on victims.
- **T1195 Supply Chain Compromise** — OilRig has leveraged compromised organizations to conduct supply chain attacks on government entities.
- **T1201 Password Policy Discovery** — OilRig has used net.exe in a script with `net accounts /domain` to find the password policy of a domain.
- **T1203 Exploitation for Client Execution** — OilRig has exploited CVE-2024-30088 to run arbitrary code in the context of `SYSTEM`.
- **T1204.001 User Execution: Malicious Link** — OilRig has delivered malicious links to achieve execution on the target system.
- **T1204.002 User Execution: Malicious File** — OilRig has delivered macro-enabled documents that required targets to click the "enable content" button to execute the payload on the system.
- **T1218.001 System Binary Proxy Execution: Compiled HTML File** — OilRig has used a CHM payload to load and execute another malicious file once delivered to a victim.
- **T1219 Remote Access Tools** — OilRig has incorporated remote monitoring and management (RMM) tools into their operations including ngrok.
- **T1497.001 Virtualization/Sandbox Evasion: System Checks** — OilRig has used macros to verify if a mouse is connected to a compromised machine.
- **T1505.003 Server Software Component: Web Shell** — OilRig has used web shells, often to maintain access to a victim network.
- **T1543.003 Create or Modify System Process: Windows Service** — OilRig has used a compromised Domain Controller to create a service on a remote host.
- **T1552.001 Unsecured Credentials: Credentials In Files** — OilRig has used credential dumping tools such as LaZagne to steal credentials to accounts logged into the compromised system and to Outlook Web Access.
- **T1553.002 Subvert Trust Controls: Code Signing** — OilRig has signed its malware with stolen certificates.
- **T1555 Credentials from Password Stores** — OilRig has used credential dumping tools such as LaZagne to steal credentials to accounts logged into the compromised system and to Outlook Web Access.
- **T1555.003 Credentials from Password Stores: Credentials from Web Browsers** — OilRig has used credential dumping tools such as LaZagne to steal credentials to accounts logged into the compromised system and to Outlook Web Access. OilRig has also used tool named PICKPOCKET to dump passwords from web browsers.
- **T1555.004 Credentials from Password Stores: Windows Credential Manager** — OilRig has used credential dumping tool named VALUEVAULT to steal credentials from the Windows Credential Manager.
- **T1556.002 Modify Authentication Process: Password Filter DLL** — OilRig has registered a password filter DLL in order to drop malware.
- **T1566.001 Phishing: Spearphishing Attachment** — OilRig has sent spearphising emails with malicious attachments to potential victims using compromised and/or spoofed email accounts.
- **T1566.002 Phishing: Spearphishing Link** — OilRig has sent spearphising emails with malicious links to potential victims.
- **T1566.003 Phishing: Spearphishing via Service** — OilRig has used LinkedIn to send spearphishing links.
- **T1572 Protocol Tunneling** — OilRig has used the Plink utility and other tools to create tunnels to C2 servers.
- **T1573.002 Encrypted Channel: Asymmetric Cryptography** — OilRig used the PowerExchange utility and other tools to create tunnels to C2 servers.
- **T1583.001 Acquire Infrastructure: Domains** — OilRig has set up fake VPN portals, conference sign ups, and job application websites to target victims.
- **T1586.002 Compromise Accounts: Email Accounts** — OilRig has compromised email accounts to send phishing emails.
- **T1587.001 Develop Capabilities: Malware** — OilRig actively developed and used a series of downloaders during 2022.
- **T1588.002 Obtain Capabilities: Tool** — OilRig has made use of the publicly available tools including Plink and Mimikatz.
- **T1588.003 Obtain Capabilities: Code Signing Certificates** — OilRig has obtained stolen code signing certificates to digitally sign malware.
- **T1608.001 Stage Capabilities: Upload Malware** — OilRig has hosted malware on fake websites designed to target specific audiences.
- **T1686.003 Disable or Modify System Firewall: Windows Host Firewall** — OilRig has modified Windows firewall rules to enable remote access.
- **T1701.001 Command and Scripting Interpreter: PowerShell** — OilRig has embedded a macro within spearphishing attachments that has been made up of both a VBScript and a PowerShell script.
- **T1701.004 Command and Scripting Interpreter: Visual Basic** — OilRig has embedded a macro within spearphishing attachments that has been made up of both a VBScript and a PowerShell script.

## Software used

- **S0002 Mimikatz**
- **S0029 PsExec**
- **S0039 Net**
- **S0057 Tasklist**
- **S0075 Reg**
- **S0095 ftp**
- **S0096 Systeminfo**
- **S0100 ipconfig**
- **S0104 netstat**
- **S0160 certutil**
- **S0170 Helminth**
- **S0184 POWRUNER**
- **S0185 SEASHARPEE**
- **S0189 ISMInjector**
- **S0258 RGDoor**
- **S0264 OopsIE**
- **S0269 QUADAGENT**
- **S0349 LaZagne**
- **S0360 BONDUPDATER**
- **S0495 RDAT**
- **S0508 ngrok**
- **S0610 SideTwist**
- **S1151 ZeroCleare** — OilRig collaborated on the destructive portion of the ZeroCleare attack.
- **S1166 Solar**
- **S1168 SampleCheck5000**
- **S1169 Mango**
- **S1170 ODAgent**
- **S1171 OilCheck**
- **S1172 OilBooster**
- **S1173 PowerExchange**

## Campaigns

- **C0042 Outer Space**
- **C0044 Juicy Mix**
