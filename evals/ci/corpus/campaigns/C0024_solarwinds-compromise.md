# C0024 — SolarWinds Compromise

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **First seen:** 2019-08-01
- **Last seen:** 2021-01-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0024
- **Last modified:** 2026-07-31

## Description

The SolarWinds Compromise was a sophisticated supply chain cyber operation conducted by APT29 that was discovered in mid-December 2020. APT29 used customized malware to inject malicious code into the SolarWinds Orion software build process that was later distributed through a normal software update; they also used password spraying, token theft, API abuse, spear phishing, and other supply chain attacks to compromise user accounts and leverage their associated access. Victims of this campaign included government, consulting, technology, telecom, and other organizations in North America, Europe, Asia, and the Middle East. This activity has been labled the StellarParticle campaign in industry reporting. Industry reporting also initially referred to the actors involved in this campaign as UNC2452, NOBELIUM, Dark Halo, and SolarStorm. 

In April 2021, the US and UK governments attributed the SolarWinds Compromise to Russia's Foreign Intelligence Service (SVR); public statements included citations to APT29, Cozy Bear, and The Dukes. The US government assessed that of the approximately 18,000 affected public and private sector customers of Solar Winds’ Orion product, a much smaller number were compromised by follow-on APT29 activity on their systems.

## Techniques used

- **T1003.006 OS Credential Dumping: DCSync** — During the SolarWinds Compromise, APT29 used privileged accounts to replicate directory service data with domain controllers.
- **T1005 Data from Local System** — During the SolarWinds Compromise, APT29 extracted files from compromised networks.
- **T1016.001 System Network Configuration Discovery: Internet Connection Discovery** — During the SolarWinds Compromise, APT29 used GoldFinder to perform HTTP GET requests to check internet connectivity and identify HTTP proxy servers and other redirectors that an HTTP request travels through.
- **T1018 Remote System Discovery** — During the SolarWinds Compromise, APT29 used AdFind to enumerate remote systems.
- **T1021.001 Remote Services: Remote Desktop Protocol** — During the SolarWinds Compromise, APT29 used RDP sessions from public-facing systems to internal servers.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — During the SolarWinds Compromise, APT29 used administrative accounts to connect over SMB to targeted users.
- **T1021.006 Remote Services: Windows Remote Management** — During the SolarWinds Compromise, APT29 used WinRM via PowerShell to execute commands and payloads on remote hosts.
- **T1036.004 Masquerading: Masquerade Task or Service** — During the SolarWinds Compromise, APT29 named tasks `\Microsoft\Windows\SoftwareProtectionPlatform\EventCacheManager` in order to appear legitimate.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — During the SolarWinds Compromise, APT29 renamed software and DLLs with legitimate names to appear benign.
- **T1047 Windows Management Instrumentation** — During the SolarWinds Compromise, APT29 used WMI for the remote execution of files for lateral movement.
- **T1048.002 Exfiltration Over Alternative Protocol: Exfiltration Over Asymmetric Encrypted Non-C2 Protocol** — During the SolarWinds Compromise, APT29 exfiltrated collected data over a simple HTTPS request to a password-protected archive staged on a victim's OWA servers.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — During the SolarWinds Compromise, APT29 used `scheduler` and `schtasks` to create new tasks on remote host as part of their lateral movement. They manipulated scheduled tasks by updating an existing legitimate task to execute their tools and then returned the scheduled task to its original configuration. APT29 also created a scheduled task to maintain SUNSPOT persistence when the host booted.
- **T1057 Process Discovery** — During the SolarWinds Compromise, APT29 used multiple command-line utilities to enumerate running processes.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — During the SolarWinds Compromise, APT29 used PowerShell to create new tasks on remote machines, identify configuration settings, exfiltrate data, and execute other commands.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — During the SolarWinds Compromise, APT29 used `cmd.exe` to execute commands on remote machines.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — For the SolarWinds Compromise, APT29 wrote malware such as Sibot in Visual Basic.
- **T1069 Permission Groups Discovery** — During the SolarWinds Compromise, APT29 used the `Get-ManagementRoleAssignment` PowerShell cmdlet to enumerate Exchange management role assignments through an Exchange Management Shell.
- **T1069.002 Permission Groups Discovery: Domain Groups** — During the SolarWinds Compromise, APT29 used AdFind to enumerate domain groups.
- **T1070 Indicator Removal** — During the SolarWinds Compromise, APT29 temporarily replaced legitimate utilities with their own, executed their payload, and then restored the original file.
- **T1070.004 Indicator Removal: File Deletion** — During the SolarWinds Compromise, APT29 routinely removed their tools, including custom backdoors, once remote access was achieved.
- **T1070.006 Indicator Removal: Timestomp** — During the SolarWinds Compromise, APT29 modified timestamps of backdoors to match legitimate Windows files.
- **T1070.008 Indicator Removal: Clear Mailbox Data** — During the SolarWinds Compromise, APT29 removed evidence of email export requests using `Remove-MailboxExportRequest`.
- **T1071.001 Application Layer Protocol: Web Protocols** — During the SolarWinds Compromise, APT29 used HTTP for C2 and data exfiltration.
- **T1074.002 Data Staged: Remote Data Staging** — During the SolarWinds Compromise, APT29 staged data and files in password-protected archives on a victim's OWA server.
- **T1078 Valid Accounts** — During the SolarWinds Compromise, APT29 used different compromised credentials for remote access and to move laterally.
- **T1078.002 Valid Accounts: Domain Accounts** — During the SolarWinds Compromise, APT29 used domain administrators' accounts to help facilitate lateral movement on compromised networks.
- **T1078.003 Valid Accounts: Local Accounts** — During the SolarWinds Compromise, APT29 used compromised local accounts to access victims' networks.
- **T1078.004 Valid Accounts: Cloud Accounts** — During the SolarWinds Compromise, APT29 used a compromised O365 administrator account to create a new Service Principal.
- **T1083 File and Directory Discovery** — During the SolarWinds Compromise, APT29 obtained information about the configured Exchange virtual directory using `Get-WebServicesVirtualDirectory`.
- **T1087 Account Discovery** — During the SolarWinds Compromise, APT29 obtained a list of users and their roles from an Exchange server using `Get-ManagementRoleAssignment`.
- **T1087.002 Account Discovery: Domain Account** — During the SolarWinds Compromise, APT29 used PowerShell to discover domain accounts by exectuing `Get-ADUser` and `Get-ADGroupMember`.
- **T1090.001 Proxy: Internal Proxy** — During the SolarWinds Compromise, APT29 used SSH port forwarding capabilities on public-facing systems, and configured at least one instance of Cobalt Strike to use a network pipe over SMB.
- **T1098.001 Account Manipulation: Additional Cloud Credentials** — During the SolarWinds Compromise, APT29 added credentials to OAuth Applications and Service Principals.
- **T1098.002 Account Manipulation: Additional Email Delegate Permissions** — During the SolarWinds Compromise, APT29 added their own devices as allowed IDs for active sync using `Set-CASMailbox`, allowing it to obtain copies of victim mailboxes. It also added additional permissions (such as Mail.Read and Mail.ReadWrite) to compromised Application or Service Principals.
- **T1098.003 Account Manipulation: Additional Cloud Roles** — During the SolarWinds Compromise, APT29 granted `company administrator` privileges to a newly created service principle.
- **T1098.005 Account Manipulation: Device Registration** — During the SolarWinds Compromise, APT29 registered devices in order to enable mailbox syncing via the `Set-CASMailbox` command.
- **T1105 Ingress Tool Transfer** — During the SolarWinds Compromise, APT29 downloaded additional malware, such as TEARDROP and Cobalt Strike, onto a compromised host following initial access.
- **T1114.002 Email Collection: Remote Email Collection** — During the SolarWinds Compromise, APT29 collected emails from specific individuals, such as executives and IT staff, using `New-MailboxExportRequest` followed by `Get-MailboxExportRequest`.
- **T1133 External Remote Services** — For the SolarWinds Compromise, APT29 used compromised identities to access networks via SSH, VPNs, and other remote access tools.
- **T1140 Deobfuscate/Decode Files or Information** — During the SolarWinds Compromise, APT29 used 7-Zip to decode their Raindrop malware.
- **T1190 Exploit Public-Facing Application** — During the SolarWinds Compromise, APT29 exploited CVE-2020-0688 against the Microsoft Exchange Control Panel to regain access to a network.
- **T1195.002 Supply Chain Compromise: Compromise Software Supply Chain** — During the SolarWinds Compromise, APT29 gained initial network access to some victims via a trojanized update of SolarWinds Orion software.
- **T1199 Trusted Relationship** — During the SolarWinds Compromise, APT29 gained access through compromised accounts at cloud solution partners, and used compromised certificates issued by Mimecast to authenticate to Mimecast customer systems.
- **T1213 Data from Information Repositories** — During the SolarWinds Compromise, APT29 accessed victims' internal knowledge repositories (wikis) to view sensitive corporate information on products, services, and internal business operations.
- **T1213.003 Data from Information Repositories: Code Repositories** — During the SolarWinds Compromise, APT29 downloaded source code from code repositories.
- **T1218.011 System Binary Proxy Execution: Rundll32** — During the SolarWinds Compromise, APT29 used `Rundll32.exe` to execute payloads.
- **T1482 Domain Trust Discovery** — During the SolarWinds Compromise, APT29 used the `Get-AcceptedDomain` PowerShell cmdlet to enumerate accepted domains through an Exchange Management Shell. They also used AdFind to enumerate domains and to discover trust between federated domains.
- **T1484.002 Domain or Tenant Policy Modification: Trust Modification** — During the SolarWinds Compromise, APT29 changed domain federation trust settings using Azure AD administrative permissions to configure the domain to accept authorization tokens signed by their own SAML signing certificate.
- **T1539 Steal Web Session Cookie** — During the SolarWinds Compromise, APT29 stole Chrome browser cookies by copying the Chrome profile directories of targeted users.
- **T1546.003 Event Triggered Execution: Windows Management Instrumentation Event Subscription** — During the SolarWinds Compromise, APT29 used a WMI event filter to invoke a command-line event consumer at system boot time to launch a backdoor with `rundll32.exe`.
- **T1550 Use Alternate Authentication Material** — During the SolarWinds Compromise, APT29 used forged SAML tokens that allowed the actors to impersonate users and bypass MFA, enabling APT29 to access enterprise cloud applications and services.
- **T1550.001 Use Alternate Authentication Material: Application Access Token** — During the SolarWinds Compromise, APT29 used compromised service principals to make changes to the Office 365 environment.
- **T1550.004 Use Alternate Authentication Material: Web Session Cookie** — During the SolarWinds Compromise, APT29 used stolen cookies to access cloud resources and a forged `duo-sid` cookie to bypass MFA set on an email account.
- **T1552.004 Unsecured Credentials: Private Keys** — During the SolarWinds Compromise, APT29 obtained PKI keys, certificate files, and the private encryption key from an Active Directory Federation Services (AD FS) container to decrypt corresponding SAML signing certificates.
- **T1553.002 Subvert Trust Controls: Code Signing** — During the SolarWinds Compromise, APT29 was able to get SUNBURST signed by SolarWinds code signing certificates by injecting the malware into the SolarWinds Orion software lifecycle.
- **T1555 Credentials from Password Stores** — During the SolarWinds Compromise, APT29 used account credentials they obtained to attempt access to Group Managed Service Account (gMSA) passwords.
- **T1555.003 Credentials from Password Stores: Credentials from Web Browsers** — During the SolarWinds Compromise, APT29 stole users' saved passwords from Chrome.
- **T1558.003 Steal or Forge Kerberos Tickets: Kerberoasting** — During the SolarWinds Compromise, APT29 obtained Ticket Granting Service (TGS) tickets for Active Directory Service Principle Names to crack offline.
- **T1560.001 Archive Collected Data: Archive via Utility** — During the SolarWinds Compromise, APT29 used 7-Zip to compress stolen emails into password-protected archives prior to exfltration; APT29 also compressed text files into zipped archives.
- **T1568 Dynamic Resolution** — During the SolarWinds Compromise, APT29 used dynamic DNS resolution to construct and resolve to randomly-generated subdomains for C2.
- **T1583.001 Acquire Infrastructure: Domains** — For the SolarWinds Compromise, APT29 acquired C2 domains, sometimes through resellers.
- **T1584.001 Compromise Infrastructure: Domains** — For the SolarWinds Compromise, APT29 compromised domains to use for C2.
- **T1587.001 Develop Capabilities: Malware** — For the SolarWinds Compromise, APT29 used numerous pieces of malware that were likely developed for or by the group, including SUNBURST, SUNSPOT, Raindrop, and TEARDROP.
- **T1589.001 Gather Victim Identity Information: Credentials** — For the SolarWinds Compromise, APT29 conducted credential theft operations to obtain credentials to be used for access to victim environments.
- **T1606.001 Forge Web Credentials: Web Cookies** — During the SolarWinds Compromise, APT29 bypassed MFA set on OWA accounts by generating a cookie value from a previously stolen secret key.
- **T1606.002 Forge Web Credentials: SAML Tokens** — During the SolarWinds Compromise, APT29 created tokens using compromised SAML signing certificates.
- **T1665 Hide Infrastructure** — During the SolarWinds Compromise, APT29 set the hostnames of their C2 infrastructure to match legitimate hostnames in the victim environment. They also used IP addresses originating from the same country as the victim for their VPN infrastructure.
- **T1680 Local Storage Discovery** — During the SolarWinds Compromise, APT29 used `fsutil` to check available free space before executing actions that might create large files on disk.
- **T1685 Disable or Modify Tools** — During the SolarWinds Compromise, APT29 used the service control manager on a remote system to disable services associated with security monitoring products.
- **T1685.001 Disable or Modify Tools: Disable or Modify Windows Event Log** — During the SolarWinds Compromise, APT29, used `AUDITPOL` to prevent the collection of audit logs.
- **T1686 Disable or Modify System Firewall** — During the SolarWinds Compromise, APT29 used `netsh` to configure firewall rules that limited certain UDP outbound packets.

## Software used

- **S0002 Mimikatz**
- **S0154 Cobalt Strike**
- **S0552 AdFind**
- **S0559 SUNBURST**
- **S0560 TEARDROP**
- **S0562 SUNSPOT**
- **S0565 Raindrop**
- **S0588 GoldMax**
- **S0589 Sibot**
- **S0597 GoldFinder**
- **S0682 TrailBlazer**

## Attributed to

- **G0016 APT29**
