# C0038 — HomeLand Justice

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **First seen:** 2021-05-01
- **Last seen:** 2022-09-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0038
- **Last modified:** 2026-07-31

## Description

HomeLand Justice was a disruptive cyber campaign conducted by Iranian state-affiliated actors against Albanian government networks in July and September 2022. The activity combined ransomware, wiper malware, and data leak operations. Initial access for HomeLand Justice was established as early as May 2021, and threat actors moved laterally, exfiltrated sensitive information, and maintained persistence for approximately 14 months prior to the destructive phase of the operation. Responsibility was claimed by the "HomeLand Justice" front, which framed the campaign as retaliation against the Mujahedeen-e Khalq (MEK), an Iranian opposition group with a presence in Albania. Multiple Iran-nexus groups are assessed to have participated in the campaign, including HEXANE who probed victim infrastructure. A second wave of attacks was launched in September 2022 using similar tactics following public attribution of the previous activity to Iran and the severing of diplomatic ties between Iran and Albania.

## Techniques used

- **T1003.001 OS Credential Dumping: LSASS Memory** — During HomeLand Justice, threat actors dumped LSASS memory on compromised hosts.
- **T1021.001 Remote Services: Remote Desktop Protocol** — During HomeLand Justice, threat actors primarily used RDP for lateral movement in the victim environment.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — During HomeLand Justice, threat actors used SMB for lateral movement.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — During HomeLand Justice, threat actors renamed ROADSWEEP to GoXML.exe and ZeroCleare to cl.exe.
- **T1041 Exfiltration Over C2 Channel** — During HomeLand Justice, threat actors used HTTP to transfer data from compromised Exchange servers.
- **T1046 Network Service Discovery** — During HomeLand Justice, threat actors executed the Advanced Port Scanner tool on compromised systems.
- **T1047 Windows Management Instrumentation** — During HomeLand Justice, threat actors used WMI to modify Windows Defender settings.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — During HomeLand Justice, threat actors used PowerShell cmdlets New-MailboxSearch and Get-Recipient for discovery.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — During HomeLand Justice, threat actors used Windows batch files for persistence and execution.
- **T1078 Valid Accounts** — During HomeLand Justice, threat actors used a compromised Exchange account to search mailboxes and create new Exchange accounts.
- **T1078.001 Valid Accounts: Default Accounts** — During HomeLand Justice, threat actors used the built-in administrator account to move laterally using RDP and Impacket.
- **T1087.003 Account Discovery: Email Account** — During HomeLand Justice, threat actors used compromised Exchange accounts to search mailboxes for administrator accounts.
- **T1098.002 Account Manipulation: Additional Email Delegate Permissions** — During HomeLand Justice, threat actors added the `ApplicationImpersonation` management role to accounts under their control to impersonate users and take ownership of targeted mailboxes.
- **T1105 Ingress Tool Transfer** — During HomeLand Justice, threat actors used web shells to download files to compromised infrastructure.
- **T1114.002 Email Collection: Remote Email Collection** — During HomeLand Justice, threat actors made multiple HTTP POST requests to the Exchange servers of the victim organization to transfer data.
- **T1134.001 Access Token Manipulation: Token Impersonation/Theft** — During HomeLand Justice, threat actors used custom tooling to acquire tokens using `ImpersonateLoggedOnUser/SetThreadToken`.
- **T1190 Exploit Public-Facing Application** — For HomeLand Justice, threat actors exploited CVE-2019-0604 in Microsoft SharePoint for initial access.
- **T1486 Data Encrypted for Impact** — During HomeLand Justice, threat actors used ROADSWEEP ransomware to encrypt files on targeted systems.
- **T1505.003 Server Software Component: Web Shell** — For HomeLand Justice, threat actors used .aspx webshells named pickers.aspx, error4.aspx, and ClientBin.aspx, to maintain persistence.
- **T1561.002 Disk Wipe: Disk Structure Wipe** — During HomeLand Justice, threat actors used a version of ZeroCleare to wipe disk drives on targeted hosts.
- **T1570 Lateral Tool Transfer** — During HomeLand Justice, threat actors initiated a process named Mellona.exe to spread the ROADSWEEP file encryptor and a persistence script to a list of internal machines.
- **T1588.002 Obtain Capabilities: Tool** — During HomeLand Justice, threat actors used tools including Advanced Port Scanner, Mimikatz, and Impacket.
- **T1588.003 Obtain Capabilities: Code Signing Certificates** — During HomeLand Justice, threat actors used tools with legitimate code signing certificates.
- **T1685 Disable or Modify Tools** — During HomeLand Justice, threat actors modified and disabled components of endpoint detection and response (EDR) solutions including Microsoft Defender Antivirus.
- **T1685.001 Disable or Modify Tools: Disable or Modify Windows Event Log** — During HomeLand Justice, threat actors deleted Windows events and application logs.

## Software used

- **S0002 Mimikatz**
- **S0095 ftp**
- **S0357 Impacket**
- **S0364 RawDisk**
- **S1149 CHIMNEYSWEEP**
- **S1150 ROADSWEEP**
- **S1151 ZeroCleare**

## Attributed to

- **G1055 VOID MANTICORE**
