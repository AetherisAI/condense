# G1017 — Volt Typhoon

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **Also known as:** BRONZE SILHOUETTE, Vanguard Panda, DEV-0391, UNC3236, Voltzite, Insidious Taurus, DazedToad
- **ATT&CK URL:** https://attack.mitre.org/groups/G1017
- **Last modified:** 2026-07-31

## Description

Volt Typhoon is a People's Republic of China (PRC) state-sponsored actor that has been active since at least 2021, primarily targeting critical infrastructure organizations in the US and its territories including Guam. Volt Typhoon's targeting and pattern of behavior have been assessed as pre-positioning to enable lateral movement to operational technology (OT) assets for potential destructive or disruptive attacks. Volt Typhoon has emphasized stealth in operations using web shells, living-off-the-land (LOTL) binaries, hands on keyboard activities, and stolen credentials.. The group has leveraged compromised SOHO routers to proxy command and control traffic and obscure its infrastructure, activity associated with the KV botnet.. 

Reporting indicates a separate initial access cluster, SYLVANITE, has been observed exploiting internet-facing edge devices and transferring access to Volt Typhoon, also tracked as VOLTZITE, for follow-on operations.

## Techniques used

- **T1003.001 OS Credential Dumping: LSASS Memory** — Volt Typhoon has attempted to access hashed credentials from the LSASS process memory space.
- **T1003.003 OS Credential Dumping: NTDS** — Volt Typhoon has used ntds.util to create domain controller installation media containing usernames and password hashes.
- **T1005 Data from Local System** — Volt Typhoon has stolen files from a sensitive file server and the Active Directory database from targeted environments, and used Wevtutil to extract event log information.
- **T1006 Direct Volume Access** — Volt Typhoon has executed the Windows-native `vssadmin` command to create volume shadow copies.
- **T1007 System Service Discovery** — Volt Typhoon has used `net start` to list running services.
- **T1010 Application Window Discovery** — Volt Typhoon has collected window title information from compromised systems.
- **T1012 Query Registry** — Volt Typhoon has queried the Registry on compromised systems, `reg query hklm\software\`, for information on installed software including PuTTY.
- **T1016 System Network Configuration Discovery** — Volt Typhoon has executed multiple commands to enumerate network topology and settings including `ipconfig`, `netsh interface firewall show all`, and `netsh interface portproxy show all`.
- **T1016.001 System Network Configuration Discovery: Internet Connection Discovery** — Volt Typhoon has employed Ping to check network connectivity.
- **T1018 Remote System Discovery** — Volt Typhoon has used multiple methods, including Ping, to enumerate systems on compromised networks.
- **T1021.001 Remote Services: Remote Desktop Protocol** — Volt Typhoon has moved laterally to the Domain Controller via RDP using a compromised account with domain administrator privileges.
- **T1027.002 Obfuscated Files or Information: Software Packing** — Volt Typhoon has used the Ultimate Packer for Executables (UPX) to obfuscate the FRP client files BrightmetricAgent.exe and SMSvcService.ex) and the port scanning utility ScanLine.
- **T1033 System Owner/User Discovery** — Volt Typhoon has used public tools and executed the PowerShell command `Get-EventLog security -instanceid 4624` to identify associated user and computer account names.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — Volt Typhoon has used legitimate looking filenames for compressed copies of the ntds.dit database and used names including cisco_up.exe, cl64.exe, vm3dservice.exe, watchdogd.exe, Win.exe, WmiPreSV.exe, and WmiPrvSE.exe for the Earthworm and Fast Reverse Proxy tools.
- **T1036.008 Masquerading: Masquerade File Type** — Volt Typhoon has appended copies of the ntds.dit database with a .gif file extension.
- **T1046 Network Service Discovery** — Volt Typhoon has used commercial tools, LOTL utilities, and appliances already present on the system for network service discovery.
- **T1047 Windows Management Instrumentation** — Volt Typhoon has leveraged WMIC for execution, remote system discovery, and to create and use temporary directories.
- **T1049 System Network Connections Discovery** — Volt Typhoon has used `netstat -ano` on compromised hosts to enumerate network connections.
- **T1056.001 Input Capture: Keylogging** — Volt Typhoon has created and accessed a file named rult3uil.log on compromised domain controllers to capture keypresses and command execution.
- **T1057 Process Discovery** — Volt Typhoon has enumerated running processes on targeted systems including through the use of Tasklist.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — Volt Typhoon has used PowerShell including for remote system discovery.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — Volt Typhoon has used the Windows command line to perform hands-on-keyboard activities in targeted environments including for discovery.
- **T1059.004 Command and Scripting Interpreter: Unix Shell** — Volt Typhoon has used Brightmetricagent.exe which contains a command- line interface (CLI) library that can leverage command shells including Z Shell (zsh).
- **T1068 Exploitation for Privilege Escalation** — Volt Typhoon has gained initial access by exploiting privilege escalation vulnerabilities in the operating system or network services.
- **T1069 Permission Groups Discovery** — Volt Typhoon has used commercial tools, LOTL utilities, and appliances already present on the system for group and user discovery.
- **T1069.001 Permission Groups Discovery: Local Groups** — Volt Typhoon has run `net localgroup administrators` in compromised environments to enumerate accounts.
- **T1069.002 Permission Groups Discovery: Domain Groups** — Volt Typhoon has run `net group` in compromised environments to discover domain groups.
- **T1070.004 Indicator Removal: File Deletion** — Volt Typhoon has run `rd /S` to delete their working directories and deleted systeminfo.dat from `C:\Users\Public\Documentsfiles`.
- **T1070.007 Indicator Removal: Clear Network Connection History and Configurations** — Volt Typhoon has inspected server logs to remove their IPs.
- **T1074 Data Staged** — Volt Typhoon has staged collected data in password-protected archives.
- **T1074.001 Data Staged: Local Data Staging** — Volt Typhoon has saved stolen files including the `ntds.dit` database and the `SYSTEM` and `SECURITY` Registry hives locally to the `C:\Windows\Temp\` directory.
- **T1078 Valid Accounts** — Volt Typhoon relies primarily on valid credentials for persistence.
- **T1078.002 Valid Accounts: Domain Accounts** — Volt Typhoon has used compromised domain accounts to authenticate to devices on compromised networks.
- **T1083 File and Directory Discovery** — Volt Typhoon has enumerated directories containing vulnerability testing and cyber related content and facilities data such as construction drawings.
- **T1087.001 Account Discovery: Local Account** — Volt Typhoon has executed `net user` and `quser` to enumerate local account information.
- **T1087.002 Account Discovery: Domain Account** — Volt Typhoon has run `net group /dom` and `net group "Domain Admins" /dom` in compromised environments for account discovery.
- **T1090 Proxy** — Volt Typhoon has used compromised devices and customized versions of open source tools such as FRP (Fast Reverse Proxy), Earthworm, and Impacket to proxy network traffic.
- **T1090.001 Proxy: Internal Proxy** — Volt Typhoon has used the built-in netsh `port proxy` command to create proxies on compromised systems to facilitate access.
- **T1090.003 Proxy: Multi-hop Proxy** — Volt Typhoon has used multi-hop proxies for command-and-control infrastructure.
- **T1105 Ingress Tool Transfer** — Volt Typhoon has downloaded an outdated version of comsvcs.dll to a compromised domain controller in a non-standard folder.
- **T1112 Modify Registry** — Volt Typhoon has used `netsh` to create a PortProxy Registry modification on a compromised server running the Paessler Router Traffic Grapher (PRTG).
- **T1113 Screen Capture** — Volt Typhoon has obtained a screenshot of the victim's system using the gdi32.dll and gdiplus.dll libraries.
- **T1120 Peripheral Device Discovery** — Volt Typhoon has obtained victim's screen dimension and display device information.
- **T1124 System Time Discovery** — Volt Typhoon has obtained the victim's system timezone.
- **T1133 External Remote Services** — Volt Typhoon has used VPNs to connect to victim environments and enable post-exploitation actions.
- **T1140 Deobfuscate/Decode Files or Information** — Volt Typhoon has used Base64-encoded data to transfer payloads and commands, including deobfuscation via certutil.
- **T1190 Exploit Public-Facing Application** — Volt Typhoon has gained initial access through exploitation of multiple vulnerabilities in internet-facing software and appliances such as Fortinet, Ivanti (formerly Pulse Secure), NETGEAR, Citrix, and Cisco.
- **T1217 Browser Information Discovery** — Volt Typhoon has targeted the browsing history of network administrators.
- **T1218 System Binary Proxy Execution** — Volt Typhoon has used native tools and processes including living off the land binaries or “LOLBins" to maintain and expand access to the victim networks.
- **T1497.001 Virtualization/Sandbox Evasion: System Checks** — Volt Typhoon has run system checks to determine if they were operating in a virtualized environment.
- **T1505.003 Server Software Component: Web Shell** — Volt Typhoon has used webshells, including ones named AuditReport.jspx and iisstart.aspx, in compromised environments.
- **T1518 Software Discovery** — Volt Typhoon has queried the Registry on compromised systems for information on installed software.
- **T1552 Unsecured Credentials** — Volt Typhoon has obtained credentials insecurely stored on targeted network appliances.
- **T1552.004 Unsecured Credentials: Private Keys** — Volt Typhoon has accessed a Local State file that contains the AES key used to encrypt passwords stored in the Chrome browser.
- **T1555 Credentials from Password Stores** — Volt Typhoon has attempted to obtain credentials from OpenSSH, realvnc, and PuTTY.
- **T1555.003 Credentials from Password Stores: Credentials from Web Browsers** — Volt Typhoon has targeted network administrator browser data including browsing history and stored credentials.
- **T1560.001 Archive Collected Data: Archive via Utility** — Volt Typhoon has archived the ntds.dit database as a multi-volume password-protected archive with 7-Zip.
- **T1570 Lateral Tool Transfer** — Volt Typhoon has copied web shells between servers in targeted environments.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — Volt Typhoon has used a version of the Awen web shell that employed AES encryption and decryption for C2 communications.
- **T1584.003 Compromise Infrastructure: Virtual Private Server** — Volt Typhoon has compromised Virtual Private Servers (VPS) to proxy C2 traffic.
- **T1584.004 Compromise Infrastructure: Server** — Volt Typhoon has used compromised Paessler Router Traffic Grapher (PRTG) servers from other organizations for C2.
- **T1584.005 Compromise Infrastructure: Botnet** — Volt Typhoon has used compromised Cisco and NETGEAR end-of-life SOHO routers implanted with KV Botnet malware to support operations.
- **T1584.008 Compromise Infrastructure: Network Devices** — Volt Typhoon has compromised small office and home office (SOHO) network edge devices, many of which were located in the same geographic area as the victim, to proxy network traffic.
- **T1587.004 Develop Capabilities: Exploits** — Volt Typhoon has exploited zero-day vulnerabilities for initial access.
- **T1588.002 Obtain Capabilities: Tool** — Volt Typhoon has used legitimate network and forensic tools and customized versions of open-source tools for C2.
- **T1588.006 Obtain Capabilities: Vulnerabilities** — Volt Typhoon has used publicly available exploit code for initial access.
- **T1589 Gather Victim Identity Information** — Volt Typhoon has gathered victim identify information during pre-compromise reconnaissance.
- **T1589.002 Gather Victim Identity Information: Email Addresses** — Volt Typhoon has targeted the personal emails of key network and IT staff at victim organizations.
- **T1590 Gather Victim Network Information** — Volt Typhoon has conducted extensive pre-compromise reconnaissance to learn about the target organization’s network.
- **T1590.004 Gather Victim Network Information: Network Topology** — Volt Typhoon has conducted extensive reconnaissance of victim networks including identifying network topologies.
- **T1590.006 Gather Victim Network Information: Network Security Appliances** — Volt Typhoon has identified target network security measures as part of pre-compromise reconnaissance.
- **T1591 Gather Victim Org Information** — Volt Typhoon has conducted extensive reconnaissance pre-compromise to gain information about the targeted organization.
- **T1591.004 Gather Victim Org Information: Identify Roles** — Volt Typhoon has identified key network and IT staff members pre-compromise at targeted organizations.
- **T1592 Gather Victim Host Information** — Volt Typhoon has conducted pre-compromise reconnaissance for victim host information.
- **T1593 Search Open Websites/Domains** — Volt Typhoon has conducted pre-compromise web searches for victim information.
- **T1594 Search Victim-Owned Websites** — Volt Typhoon has conducted pre-compromise reconnaissance on victim-owned sites.
- **T1596.005 Search Open Technical Databases: Scan Databases** — Volt Typhoon has used FOFA, Shodan, and Censys to search for exposed victim infrastructure.
- **T1614 System Location Discovery** — Volt Typhoon has obtained the victim's system current location.
- **T1654 Log Enumeration** — Volt Typhoon has used `wevtutil.exe` and the PowerShell command `Get-EventLog security` to enumerate Windows logs to search for successful logons.
- **T1680 Local Storage Discovery** — Volt Typhoon has discovered file system types, drive names, size, and free space on compromised systems.
- **T1685.005 Disable or Modify Tools: Clear Windows Event Logs** — Volt Typhoon has selectively cleared Windows Event Logs, system logs, and other technical artifacts to remove evidence of intrusion activity.

## Software used

- **S0002 Mimikatz**
- **S0029 PsExec**
- **S0039 Net**
- **S0057 Tasklist**
- **S0075 Reg**
- **S0096 Systeminfo**
- **S0097 Ping**
- **S0100 ipconfig**
- **S0104 netstat**
- **S0106 cmd**
- **S0108 netsh**
- **S0160 certutil**
- **S0357 Impacket**
- **S0359 Nltest**
- **S0645 Wevtutil**
- **S1144 FRP**
- **S1154 VersaMem** — VersaMem was used by Volt Typhoon as part of Versa Director Zero Day Exploitation.

## Campaigns

- **C0035 KV Botnet Activity** — Volt Typhoon used KV Botnet Activity to build intermediate communication chains between operators and victims, such as identified access to victims in Guam.
- **C0039 Versa Director Zero Day Exploitation** — Versa Director Zero Day Exploitation was conducted by Volt Typhoon between June and August 2024.
