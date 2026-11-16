# G0032 — Lazarus Group

- **Type:** group
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Also known as:** Labyrinth Chollima, HIDDEN COBRA, Guardians of Peace, ZINC, NICKEL ACADEMY, Diamond Sleet
- **ATT&CK URL:** https://attack.mitre.org/groups/G0032
- **Last modified:** 2026-07-31

## Description

Lazarus Group is a North Korean state-sponsored cyber threat group attributed to the Reconnaissance General Bureau (RGB). Lazarus Group has been active since at least 2009 and is reportedly responsible for the November 2014 destructive wiper attack on Sony Pictures Entertainment, identified by Novetta as part of Operation Blockbuster. Malware used by Lazarus Group correlates to other reported campaigns, including Operation Flame, Operation 1Mission, Operation Troy, DarkSeoul, and Ten Days of Rain.

North Korea’s cyber operations have shown a consistent pattern of adaptation, forming and reorganizing units as national priorities shift. These units frequently share personnel, infrastructure, malware, and tradecraft, making it difficult to attribute specific operations with high confidence. Public reporting often uses “Lazarus Group” as an umbrella term for multiple North Korean cyber operators conducting espionage, destructive attacks, and financially motivated campaigns.

## Techniques used

- **T0865 Spearphishing Attachment** — Lazarus Group has been observed targeting organizations using spearphishing documents with embedded malicious payloads. Highly targeted spear phishing campaigns have been conducted against a U.S. electric grid company.
- **T1001.003 Data Obfuscation: Protocol or Service Impersonation** — Lazarus Group malware also uses a unique form of communication encryption known as FakeTLS that mimics TLS but uses a different encryption method, potentially evading SSL traffic inspection/decryption.
- **T1005 Data from Local System** — Lazarus Group has collected data and files from compromised networks.
- **T1008 Fallback Channels** — Lazarus Group malware SierraAlfa sends data to one of the hard-coded C2 servers chosen at random, and if the transmission fails, chooses a new C2 server to attempt the transmission again.
- **T1010 Application Window Discovery** — Lazarus Group malware IndiaIndia obtains and sends to its C2 server the title of the window for each running process. The KilaAlfa keylogger also reports the title of the window in the foreground.
- **T1012 Query Registry** — Lazarus Group malware IndiaIndia checks Registry keys within HKCU and HKLM to determine if certain applications are present, including SecureCRT, Terminal Services, RealVNC, TightVNC, UltraVNC, Radmin, mRemote, TeamViewer, FileZilla, pcAnyware, and Remote Desktop. Another Lazarus Group malware sample checks for the presence of the following Registry key:`HKEY_CURRENT_USER\Software\Bitcoin\Bitcoin-Qt`.
- **T1016 System Network Configuration Discovery** — Lazarus Group malware IndiaIndia obtains and sends to its C2 server information about the first network interface card’s configuration, including IP address, gateways, subnet mask, DHCP information, and whether WINS is available.
- **T1021.001 Remote Services: Remote Desktop Protocol** — Lazarus Group malware SierraCharlie uses RDP for propagation.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — Lazarus Group malware SierraAlfa accesses the `ADMIN$` share via SMB to conduct lateral movement.
- **T1021.004 Remote Services: SSH** — Lazarus Group used SSH and the PuTTy PSCP utility to gain access to a restricted segment of a compromised network.
- **T1027.007 Obfuscated Files or Information: Dynamic API Resolution** — Lazarus Group has used a custom hashing method to resolve APIs used in shellcode.
- **T1027.009 Obfuscated Files or Information: Embedded Payloads** — Lazarus Group has distributed malicious payloads embedded in PNG files.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — Lazarus Group has used multiple types of encryption and encoding for their payloads, including AES, Caracachs, RC4, XOR, Base64, and other tricks such as creating aliases in code for Native API function names.
- **T1033 System Owner/User Discovery** — Various Lazarus Group malware enumerates logged-on users.
- **T1036.003 Masquerading: Rename Legitimate Utilities** — Lazarus Group has renamed system utilities such as `wscript.exe` and `mshta.exe`.
- **T1036.004 Masquerading: Masquerade Task or Service** — Lazarus Group has used a scheduled task named `SRCheck` to mask the execution of a malicious .dll.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — Lazarus Group has renamed malicious code to disguise it as Microsoft's narrator and other legitimate files.
- **T1041 Exfiltration Over C2 Channel** — Lazarus Group has exfiltrated data and files over a C2 channel through its various tools and malware.
- **T1046 Network Service Discovery** — Lazarus Group has used nmap from a router VM to scan ports on systems within the restricted segment of an enterprise network.
- **T1047 Windows Management Instrumentation** — Lazarus Group has used WMIC for discovery as well as to execute payloads for persistence and lateral movement.
- **T1048.003 Exfiltration Over Alternative Protocol: Exfiltration Over Unencrypted Non-C2 Protocol** — Lazarus Group malware SierraBravo-Two generates an email message via SMTP containing information about newly infected victims.
- **T1049 System Network Connections Discovery** — Lazarus Group has used `net use` to identify and establish a network connection with a remote host.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — Lazarus Group has used `schtasks` for persistence including through the periodic execution of a remote XSL script or a dropped VBS payload.
- **T1055.001 Process Injection: Dynamic-link Library Injection** — A Lazarus Group malware sample performs reflective DLL injection.
- **T1056.001 Input Capture: Keylogging** — Lazarus Group malware KiloAlfa contains keylogging functionality.
- **T1057 Process Discovery** — Several Lazarus Group malware families gather a list of running processes on a victim system and send it to their C2 server. A Destover-like variant used by Lazarus Group also gathers process times.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — Lazarus Group has used PowerShell to execute commands and malicious code.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — Lazarus Group malware uses cmd.exe to execute commands on a compromised host. A Destover-like variant used by Lazarus Group uses a batch file mechanism to delete its binaries from the system.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — Lazarus Group has used VBA and embedded macros in Word documents to execute malicious code.
- **T1070 Indicator Removal** — Lazarus Group has restored malicious KernelCallbackTable code to its original state after the process execution flow has been hijacked.
- **T1070.003 Indicator Removal: Clear Command History** — Lazarus Group has routinely deleted log files on a compromised router, including automatic log deletion through the use of the logrotate utility.
- **T1070.004 Indicator Removal: File Deletion** — Lazarus Group malware has deleted files in various ways, including "suicide scripts" to delete malware binaries from the victim. Lazarus Group also uses secure file deletion to delete files from the victim.
- **T1070.006 Indicator Removal: Timestomp** — Several Lazarus Group malware families use timestomping, including modifying the last write timestamp of a specified Registry key to a random date, as well as copying the timestamp for legitimate .exe files (such as calc.exe or mspaint.exe) to its dropped files.
- **T1071.001 Application Layer Protocol: Web Protocols** — Lazarus Group has conducted C2 over HTTP and HTTPS.
- **T1074.001 Data Staged: Local Data Staging** — Lazarus Group malware IndiaIndia saves information gathered about the victim to a file that is saved in the %TEMP% directory, then compressed, encrypted, and uploaded to a C2 server.
- **T1078 Valid Accounts** — Lazarus Group has used administrator credentials to gain access to restricted network segments.
- **T1082 System Information Discovery** — Several Lazarus Group malware families collect information on the type and version of the victim OS, as well as the victim computer name and CPU information.
- **T1083 File and Directory Discovery** — Lazarus Group malware can use a common function to identify target files by their extension, and some also enumerate files and directories, including a Destover-like variant that lists files and gathers information for all drives.
- **T1090.001 Proxy: Internal Proxy** — Lazarus Group has used a compromised router to serve as a proxy between a victim network's corporate and restricted segments.
- **T1090.002 Proxy: External Proxy** — Lazarus Group has used multiple proxies to obfuscate network traffic from victims.
- **T1098 Account Manipulation** — Lazarus Group malware WhiskeyDelta-Two contains a function that attempts to rename the administrator’s account.
- **T1102.002 Web Service: Bidirectional Communication** — Lazarus Group has used GitHub as C2, pulling hosted image payloads then committing command execution output to files in specific directories.
- **T1104 Multi-Stage Channels** — Lazarus Group has used multi-stage malware components that inject later stages into separate processes.
- **T1105 Ingress Tool Transfer** — Lazarus Group has downloaded files, malware, and tools from its C2 onto a compromised host.
- **T1106 Native API** — Lazarus Group has used the Windows API `ObtainUserAgentString` to obtain the User-Agent from a compromised host to connect to a C2 server. Lazarus Group has also used various, often lesser known, functions to perform various types of Discovery and Process Injection.
- **T1110.003 Brute Force: Password Spraying** — Lazarus Group malware attempts to connect to Windows shares for lateral movement by using a generated list of usernames, which center around permutations of the username Administrator, and weak passwords.
- **T1124 System Time Discovery** — A Destover-like implant used by Lazarus Group can obtain the current system time and send it to the C2 server.
- **T1132.001 Data Encoding: Standard Encoding** — A Lazarus Group malware sample encodes data with base64.
- **T1134.002 Access Token Manipulation: Create Process with Token** — Lazarus Group keylogger KiloAlfa obtains user tokens from interactive sessions to execute itself with API call `CreateProcessAsUserA` under that user's context.
- **T1140 Deobfuscate/Decode Files or Information** — Lazarus Group has used shellcode within macros to decrypt and manually map DLLs and shellcode into memory at runtime.
- **T1189 Drive-by Compromise** — Lazarus Group delivered RATANKBA and other malicious code to victims via a compromised legitimate website.
- **T1202 Indirect Command Execution** — Lazarus Group persistence mechanisms have used `forfiles.exe` to execute .htm files.
- **T1203 Exploitation for Client Execution** — Lazarus Group has exploited Adobe Flash vulnerability CVE-2018-4878 for execution.
- **T1204.002 User Execution: Malicious File** — Lazarus Group has attempted to get users to launch a malicious Microsoft Word attachment delivered via a spearphishing email.
- **T1218 System Binary Proxy Execution** — Lazarus Group lnk files used for persistence have abused the Windows Update Client (`wuauclt.exe`) to execute a malicious DLL.
- **T1218.005 System Binary Proxy Execution: Mshta** — Lazarus Group has used `mshta.exe` to execute HTML pages downloaded by initial access documents.
- **T1218.011 System Binary Proxy Execution: Rundll32** — Lazarus Group has used rundll32 to execute malicious payloads on a compromised host.
- **T1485 Data Destruction** — Lazarus Group has used a custom secure delete function to overwrite file contents with data from heap memory.
- **T1489 Service Stop** — Lazarus Group has stopped the MSExchangeIS service to render Exchange contents inaccessible to users.
- **T1491.001 Defacement: Internal Defacement** — Lazarus Group replaced the background wallpaper of systems with a threatening image after rendering the system unbootable with a Disk Structure Wipe.
- **T1529 System Shutdown/Reboot** — Lazarus Group has rebooted systems after destroying files and wiping the MBR on infected systems.
- **T1542.003 Pre-OS Boot: Bootkit** — Lazarus Group malware WhiskeyAlfa-Three modifies sector 0 of the Master Boot Record (MBR) to ensure that the malware will persist even if a victim machine shuts down.
- **T1543.003 Create or Modify System Process: Windows Service** — Several Lazarus Group malware families install themselves as new services.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — Lazarus Group has maintained persistence by loading malicious code into a startup folder or by adding a Registry Run key.
- **T1547.009 Boot or Logon Autostart Execution: Shortcut Modification** — Lazarus Group malware has maintained persistence on a system by creating a LNK shortcut in the user’s Startup folder.
- **T1553.002 Subvert Trust Controls: Code Signing** — Lazarus Group has digitally signed malware and utilities to evade detection.
- **T1557.001 Adversary-in-the-Middle: Name Resolution Poisoning and SMB Relay** — Lazarus Group executed Responder using the command `[Responder file path] -i [IP address] -rPv` on a compromised host to harvest credentials and move laterally.
- **T1560 Archive Collected Data** — Lazarus Group has compressed exfiltrated data with RAR and used RomeoDelta malware to archive specified directories in .zip format, encrypt the .zip file, and upload it to C2.
- **T1560.002 Archive Collected Data: Archive via Library** — Lazarus Group malware IndiaIndia saves information gathered about the victim to a file that is compressed with Zlib, encrypted, and uploaded to a C2 server.
- **T1560.003 Archive Collected Data: Archive via Custom Method** — A Lazarus Group malware sample encrypts data using a simple byte based XOR operation prior to exfiltration.
- **T1561.001 Disk Wipe: Disk Content Wipe** — Lazarus Group has used malware like WhiskeyAlfa to overwrite the first 64MB of every drive with a mix of static and random buffers. A similar process is then used to wipe content in logical drives and, finally, attempt to wipe every byte of every sector on every drive. WhiskeyBravo can be used to overwrite the first 4.9MB of physical drives. WhiskeyDelta can overwrite the first 132MB or 1.5MB of each drive with random data from heap memory.
- **T1561.002 Disk Wipe: Disk Structure Wipe** — Lazarus Group malware SHARPKNOT overwrites and deletes the Master Boot Record (MBR) on the victim's machine and has possessed MBR wiper malware since at least 2009.
- **T1564.001 Hide Artifacts: Hidden Files and Directories** — Lazarus Group has used a VBA Macro to set its file attributes to System and Hidden and has named files with a dot prefix to hide them from the Finder application.
- **T1566.001 Phishing: Spearphishing Attachment** — Lazarus Group has targeted victims with spearphishing emails containing malicious Microsoft Word documents.
- **T1566.002 Phishing: Spearphishing Link** — Lazarus Group has sent malicious links to victims via email.
- **T1566.003 Phishing: Spearphishing via Service** — Lazarus Group has used social media platforms, including LinkedIn and Twitter, to send spearphishing messages.
- **T1571 Non-Standard Port** — Some Lazarus Group malware uses a list of ordered port numbers to choose a port for C2 traffic, creating port-protocol mismatches.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — Several Lazarus Group malware families encrypt C2 traffic using custom code that uses XOR with an ADD operation and XOR with a SUB operation. Another Lazarus Group malware sample XORs C2 traffic. Other Lazarus Group malware uses Caracachs encryption to encrypt C2 payloads. Lazarus Group has also used AES to encrypt C2 traffic.
- **T1574.001 Hijack Execution Flow: DLL** — Lazarus Group has replaced `win_fw.dll`, an internal component that is executed during IDA Pro installation, with a malicious DLL to download and execute a payload. Lazarus Group utilized DLL side-loading to execute malicious payloads through abuse of the legitimate processes `wsmprovhost.exe` and `dfrgui.exe`.
- **T1574.013 Hijack Execution Flow: KernelCallbackTable** — Lazarus Group has abused the `KernelCallbackTable` to hijack process control flow and execute shellcode.
- **T1583.001 Acquire Infrastructure: Domains** — Lazarus Group has acquired domains related to their campaigns to act as distribution points and C2 channels.
- **T1583.006 Acquire Infrastructure: Web Services** — Lazarus Group has hosted malicious downloads on Github.
- **T1584.004 Compromise Infrastructure: Server** — Lazarus Group has compromised servers to stage malicious tools.
- **T1585.001 Establish Accounts: Social Media Accounts** — Lazarus Group has created new Twitter accounts to conduct social engineering against potential victims.
- **T1585.002 Establish Accounts: Email Accounts** — Lazarus Group has created new email accounts for spearphishing operations.
- **T1587.001 Develop Capabilities: Malware** — Lazarus Group has developed custom malware for use in their operations.
- **T1588.002 Obtain Capabilities: Tool** — Lazarus Group has obtained a variety of tools for their operations, including Responder and PuTTy PSCP.
- **T1588.004 Obtain Capabilities: Digital Certificates** — Lazarus Group has obtained SSL certificates for their C2 domains.
- **T1589.002 Gather Victim Identity Information: Email Addresses** — Lazarus Group collected email addresses belonging to various departments of a targeted organization which were used in follow-on phishing campaigns.
- **T1591 Gather Victim Org Information** — Lazarus Group has studied publicly available information about a targeted organization to tailor spearphishing efforts against specific departments and/or individuals.
- **T1620 Reflective Code Loading** — Lazarus Group has changed memory protection permissions then overwritten in memory DLL function code with shellcode, which was later executed via KernelCallbackTable hijacking. Lazarus Group has also used shellcode within macros to decrypt and manually map DLLs into memory at runtime.
- **T1680 Local Storage Discovery** — A Destover-like variant used by Lazarus Group collects disk space information and sends it to its C2 server.
- **T1685 Disable or Modify Tools** — Lazarus Group malware TangoDelta attempts to terminate various processes associated with McAfee. Additionally, Lazarus Group malware SHARPKNOT disables the Microsoft Windows System Event Notification and Alerter services..
- **T1686.003 Disable or Modify System Firewall: Windows Host Firewall** — Various Lazarus Group malware modifies the Windows firewall to allow incoming connections or disable it entirely using netsh.

## Software used

- **S0103 route**
- **S0108 netsh**
- **S0174 Responder**
- **S0180 Volgmer**
- **S0181 FALLCHILL**
- **S0238 Proxysvc**
- **S0239 Bankshot**
- **S0241 RATANKBA**
- **S0245 BADCALL**
- **S0246 HARDRAIN**
- **S0263 TYPEFRAME**
- **S0271 KEYMARBLE**
- **S0347 AuditCred**
- **S0364 RawDisk**
- **S0366 WannaCry**
- **S0376 HOPLIGHT**
- **S0431 HotCroissant**
- **S0497 Dacls**
- **S0498 Cryptoistic**
- **S0520 BLINDINGCAN**
- **S0567 Dtrack**
- **S0584 AppleJeus**
- **S0586 TAINTEDSCRIBE**
- **S0593 ECCENTRICBANDWAGON**
- **S0665 ThreatNeedle**
- **S1182 MagicRAT** — MagicRAT is exclusively associated with Lazarus Group operations in 2022.

## Campaigns

- **C0022 Operation Dream Job**
