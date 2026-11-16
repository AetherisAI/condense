# C0014 — Operation Wocao

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **First seen:** 2017-12-01
- **Last seen:** 2019-12-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0014
- **Last modified:** 2026-07-31

## Description

Operation Wocao was a cyber espionage campaign that targeted organizations around the world, including in Brazil, China, France, Germany, Italy, Mexico, Portugal, Spain, the United Kingdom, and the United States. The suspected China-based actors compromised government organizations and managed service providers, as well as aviation, construction, energy, finance, health care, insurance, offshore engineering, software development, and transportation companies.

Security researchers assessed the Operation Wocao actors used similar TTPs and tools as APT20, suggesting a possible overlap. Operation Wocao was named after an observed command line entry by one of the threat actors, possibly out of frustration from losing webshell access.

## Techniques used

- **T1001 Data Obfuscation** — During Operation Wocao, threat actors encrypted IP addresses used for "Agent" proxy hops with RC4.
- **T1003.001 OS Credential Dumping: LSASS Memory** — During Operation Wocao, threat actors used ProcDump to dump credentials from memory.
- **T1003.006 OS Credential Dumping: DCSync** — During Operation Wocao, threat actors used Mimikatz's DCSync to dump credentials from the memory of the targeted system.
- **T1005 Data from Local System** — During Operation Wocao, threat actors exfiltrated files and directories of interest from the targeted system.
- **T1007 System Service Discovery** — During Operation Wocao, threat actors used the `tasklist` command to search for one of its backdoors.
- **T1012 Query Registry** — During Operation Wocao, the threat actors executed `/c cd /d c:\windows\temp\ & reg query HKEY_CURRENT_USER\Software\<username>\PuTTY\Sessions\` to detect recent PuTTY sessions, likely to further lateral movement.
- **T1016 System Network Configuration Discovery** — During Operation Wocao, threat actors discovered the local network configuration with `ipconfig`.
- **T1016.001 System Network Configuration Discovery: Internet Connection Discovery** — During Operation Wocao, threat actors used a Visual Basic script that checked for internet connectivity.
- **T1018 Remote System Discovery** — During Operation Wocao, threat actors used `nbtscan` and `ping` to discover remote systems, as well as `dsquery subnet` on a domain controller to retrieve all subnets in the Active Directory.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — During Operation Wocao, threat actors used Impacket's smbexec.py as well as accessing the C$ and IPC$ shares to move laterally.
- **T1027.005 Obfuscated Files or Information: Indicator Removal from Tools** — During Operation Wocao, threat actors edited variable names within the Impacket suite to avoid automated detection.
- **T1027.010 Obfuscated Files or Information: Command Obfuscation** — During Operation Wocao, threat actors executed PowerShell commands which were encoded or compressed using Base64, zlib, and XOR.
- **T1033 System Owner/User Discovery** — During Operation Wocao, threat actors enumerated sessions and users on a remote host, and identified privileged users logged into a targeted system.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — During Operation Wocao, the threat actors renamed some tools and executables to appear as legitimate programs.
- **T1041 Exfiltration Over C2 Channel** — During Operation Wocao, threat actors used the XServer backdoor to exfiltrate data.
- **T1046 Network Service Discovery** — During Operation Wocao, threat actors scanned for open ports and used nbtscan to find NETBIOS nameservers.
- **T1047 Windows Management Instrumentation** — During Operation Wocao, threat actors has used WMI to execute commands.
- **T1049 System Network Connections Discovery** — During Operation Wocao, threat actors collected a list of open connections on the infected system using `netstat` and checks whether it has an internet connection.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — During Operation Wocao, threat actors used scheduled tasks to execute malicious PowerShell code on remote systems.
- **T1055 Process Injection** — During Operation Wocao, threat actors injected code into a selected process, which in turn launches a command as a child process of the original.
- **T1056.001 Input Capture: Keylogging** — During Operation Wocao, threat actors obtained the password for the victim's password manager via a custom keylogger.
- **T1057 Process Discovery** — During Operation Wocao, the threat actors used `tasklist` to collect a list of running processes on an infected system.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — During Operation Wocao, threat actors used PowerShell on compromised systems.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — During Operation Wocao, threat actors spawned a new `cmd.exe` process to execute commands.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — During Operation Wocao, threat actors used VBScript to conduct reconnaissance on targeted systems.
- **T1059.006 Command and Scripting Interpreter: Python** — During Operation Wocao, threat actors' backdoors were written in Python and compiled with py2exe.
- **T1069.001 Permission Groups Discovery: Local Groups** — During Operation Wocao, threat actors used the command `net localgroup administrators` to list all administrators part of a local group.
- **T1070.004 Indicator Removal: File Deletion** — During Operation Wocao, the threat actors consistently removed traces of their activity by first overwriting a file using `/c cd /d c:\windows\temp\ & copy \\<IP ADDRESS>\c$\windows\system32\devmgr.dll \\<IP ADDRESS>\c$\windows\temp\LMAKSW.ps1 /y` and then deleting the overwritten file using `/c cd /d c:\windows\temp\ & del \\<IP ADDRESS>\c$\windows\temp\LMAKSW.ps1`.
- **T1071.001 Application Layer Protocol: Web Protocols** — During Operation Wocao, threat actors’ XServer tool communicated using HTTP and HTTPS.
- **T1074.001 Data Staged: Local Data Staging** — During Operation Wocao, threat actors staged archived files in a temporary directory prior to exfiltration.
- **T1078 Valid Accounts** — During Operation Wocao, threat actors used valid VPN credentials to gain initial access.
- **T1078.002 Valid Accounts: Domain Accounts** — During Operation Wocao, threat actors used domain credentials, including domain admin, for lateral movement and privilege escalation.
- **T1078.003 Valid Accounts: Local Accounts** — During Operation Wocao, threat actors used local account credentials found during the intrusion for lateral movement and privilege escalation.
- **T1082 System Information Discovery** — During Operation Wocao, threat actors discovered the OS versions of systems connected to a targeted network.
- **T1083 File and Directory Discovery** — During Operation Wocao, threat actors gathered a recursive directory listing to find files and directories of interest.
- **T1087.002 Account Discovery: Domain Account** — During Operation Wocao, threat actors used the `net` command to retrieve information about domain accounts.
- **T1090 Proxy** — During Operation Wocao, threat actors used a custom proxy tool called "Agent" which has support for multiple hops.
- **T1090.001 Proxy: Internal Proxy** — During Operation Wocao, threat actors proxied traffic through multiple infected systems.
- **T1090.003 Proxy: Multi-hop Proxy** — During Operation Wocao, threat actors executed commands through the installed web shell via Tor exit nodes.
- **T1095 Non-Application Layer Protocol** — During Operation Wocao, threat actors used a custom protocol for command and control.
- **T1105 Ingress Tool Transfer** — During Operation Wocao, threat actors downloaded additional files to the infected system.
- **T1106 Native API** — During Operation Wocao, threat actors used the `CreateProcessA` and `ShellExecute` API functions to launch commands after being injected into a selected process.
- **T1111 Multi-Factor Authentication Interception** — During Operation Wocao, threat actors used a custom collection method to intercept two-factor authentication soft tokens.
- **T1112 Modify Registry** — During Operation Wocao, the threat actors enabled Wdigest by changing the `HKLM\SYSTEM\\ControlSet001\\Control\\SecurityProviders\\WDigest` registry value from 0 (disabled) to 1 (enabled).
- **T1115 Clipboard Data** — During Operation Wocao, threat actors collected clipboard data in plaintext.
- **T1119 Automated Collection** — During Operation Wocao, threat actors used a script to collect information about the infected system.
- **T1120 Peripheral Device Discovery** — During Operation Wocao, threat actors discovered removable disks attached to a system.
- **T1124 System Time Discovery** — During Operation Wocao, threat actors used the `time` command to retrieve the current time of a compromised system.
- **T1133 External Remote Services** — During Operation Wocao, threat actors used stolen credentials to connect to the victim's network via VPN.
- **T1135 Network Share Discovery** — During Operation Wocao, threat actors discovered network disks mounted to the system using netstat.
- **T1190 Exploit Public-Facing Application** — During Operation Wocao, threat actors gained initial access by exploiting vulnerabilities in JBoss webservers.
- **T1505.003 Server Software Component: Web Shell** — During Operation Wocao, threat actors used their own web shells, as well as those previously placed on target systems by other threat actors, for reconnaissance and lateral movement.
- **T1518 Software Discovery** — During Operation Wocao, threat actors collected a list of installed software on the infected system.
- **T1518.001 Software Discovery: Security Software Discovery** — During Operation Wocao, threat actors used scripts to detect security software.
- **T1552.004 Unsecured Credentials: Private Keys** — During Operation Wocao, threat actors used Mimikatz to dump certificates and private keys from the Windows certificate store.
- **T1555.005 Credentials from Password Stores: Password Managers** — During Operation Wocao, threat actors accessed and collected credentials from password managers.
- **T1558.003 Steal or Forge Kerberos Tickets: Kerberoasting** — During Operation Wocao, threat actors used PowerSploit's `Invoke-Kerberoast` module to request encrypted service tickets and bruteforce the passwords of Windows service accounts offline.
- **T1560.001 Archive Collected Data: Archive via Utility** — During Operation Wocao, threat actors archived collected files with WinRAR, prior to exfiltration.
- **T1569.002 System Services: Service Execution** — During Operation Wocao, threat actors created services on remote systems for execution purposes.
- **T1570 Lateral Tool Transfer** — During Operation Wocao, threat actors used SMB to copy files to and from target systems.
- **T1571 Non-Standard Port** — During Operation Wocao, the threat actors used uncommon high ports for its backdoor C2, including ports 25667 and 47000.
- **T1573.002 Encrypted Channel: Asymmetric Cryptography** — During Operation Wocao, threat actors' proxy implementation "Agent" upgraded the socket in use to a TLS socket.
- **T1583.004 Acquire Infrastructure: Server** — For Operation Wocao, the threat actors purchased servers with Bitcoin to use during the operation.
- **T1585.002 Establish Accounts: Email Accounts** — For Operation Wocao, the threat actors registered email accounts to use during the campaign.
- **T1587.001 Develop Capabilities: Malware** — During Operation Wocao, threat actors developed their own custom webshells to upload to compromised servers.
- **T1588.002 Obtain Capabilities: Tool** — For Operation Wocao, the threat actors obtained a variety of open source tools, including JexBoss, KeeThief, and BloodHound.
- **T1589 Gather Victim Identity Information** — During Operation Wocao, threat actors targeted people based on their organizational roles and privileges.
- **T1680 Local Storage Discovery** — During Operation Wocao, threat actors discovered the local disks attached to the system and their hardware information including manufacturer and model.
- **T1685.005 Disable or Modify Tools: Clear Windows Event Logs** — During Operation Wocao, the threat actors deleted all Windows system and security event logs using `/Q /c wevtutil cl system` and `/Q /c wevtutil cl security`.
- **T1686.003 Disable or Modify System Firewall: Windows Host Firewall** — During Operation Wocao, threat actors used PowerShell to add and delete rules in the Windows firewall.

## Software used

- **S0002 Mimikatz** — During Operation Wocao, threat actors used Mimikatz with the `privilege::debug` and `lsadump::dcsync /all` flags to dump account credentials.
- **S0029 PsExec** — During Operation Wocao, threat actors used PsExec to interact with other systems inside the internal network.
- **S0104 netstat** — During Operation Wocao, threat actors used netstat to identify specific ports.
- **S0105 dsquery** — During Operation Wocao, threat actors used dsquery to retrieve all subnets in the Active Directory.
- **S0183 Tor** — During Operation Wocao, threat actors used Tor exit nodes to execute commands.
- **S0194 PowerSploit** — During Operation Wocao, threat actors used PowerSploit’s `Invoke-Kerberoast` module to bruteforce passwords and retrieve encrypted service tickets.
- **S0357 Impacket** — During Operation Wocao, threat actors used `smbexec.py` and `psexec.py` from Impacket for lateral movement.
- **S0521 BloodHound** — During Operation Wocao, threat actors used BloodHound discover trust between domains.
- **S0645 Wevtutil** — During Operation Wocao, threat actors used Wevtutil to delete system and security event logs with `wevtutil cl system` and `wevtutil cl security`.
