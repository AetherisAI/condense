# C0022 — Operation Dream Job

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **Also known as:** Operation North Star, Operation Interception
- **First seen:** 2019-09-01
- **Last seen:** 2020-08-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0022
- **Last modified:** 2026-07-31

## Description

Operation Dream Job was a cyber espionage operation likely conducted by Lazarus Group that targeted the defense, aerospace, government, and other sectors in the United States, Israel, Australia, Russia, and India. In at least one case, the cyber actors tried to monetize their network access to conduct a business email compromise (BEC) operation. In 2020, security researchers noted overlapping TTPs, to include fake job lures and code similarities, between Operation Dream Job, Operation North Star, and Operation Interception; by 2022 security researchers described Operation Dream Job as an umbrella term covering both Operation Interception and Operation North Star.

## Techniques used

- **T1005 Data from Local System** — During Operation Dream Job, Lazarus Group used malicious Trojans and DLL files to exfiltrate data from an infected host.
- **T1027.002 Obfuscated Files or Information: Software Packing** — During Operation Dream Job, Lazarus Group packed malicious .db files with Themida to evade detection.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — During Operation Dream Job, Lazarus Group encrypted malware such as DRATzarus with XOR and DLL files with base64.
- **T1036.008 Masquerading: Masquerade File Type** — During Operation Dream Job, Lazarus Group disguised malicious template files as JPEG files to avoid detection.
- **T1041 Exfiltration Over C2 Channel** — During Operation Dream Job, Lazarus Group exfiltrated data from a compromised host to actor-controlled C2 servers.
- **T1047 Windows Management Instrumentation** — During Operation Dream Job, Lazarus Group used WMIC to executed a remote XSL script.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — During Operation Dream Job, Lazarus Group created scheduled tasks to set a periodic execution of a remote XSL script.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — During Operation Dream Job, Lazarus Group used PowerShell commands to explore the environment of compromised victims.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — During Operation Dream Job, Lazarus Group launched malicious DLL files, created new folders, and renamed folders with the use of the Windows command shell.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — During Operation Dream Job, Lazarus Group executed a VBA written malicious macro after victims download malicious DOTM files; Lazarus Group also used Visual Basic macro code to extract a double Base64 encoded DLL implant.
- **T1070.004 Indicator Removal: File Deletion** — During Operation Dream Job, Lazarus Group removed all previously delivered files from a compromised computer.
- **T1071.001 Application Layer Protocol: Web Protocols** — During Operation Dream Job, Lazarus Group uses HTTP and HTTPS to contact actor-controlled C2 servers.
- **T1083 File and Directory Discovery** — During Operation Dream Job, Lazarus Group conducted word searches within documents on a compromised host in search of security and financial matters.
- **T1087.002 Account Discovery: Domain Account** — During Operation Dream Job, Lazarus Group queried compromised victim's active directory servers to obtain the list of employees including administrator accounts.
- **T1105 Ingress Tool Transfer** — During Operation Dream Job, Lazarus Group downloaded multistage malware and tools onto a compromised host.
- **T1106 Native API** — During Operation Dream Job, Lazarus Group used Windows API `ObtainUserAgentString` to obtain the victim's User-Agent and used the value to connect to their C2 server.
- **T1110 Brute Force** — During Operation Dream Job, Lazarus Group performed brute force attacks against administrator accounts.
- **T1204.001 User Execution: Malicious Link** — During Operation Dream Job, Lazarus Group lured users into executing a malicious link to disclose private account information or provide initial access.
- **T1204.002 User Execution: Malicious File** — During Operation Dream Job, Lazarus Group lured victims into executing malicious documents that contained "dream job" descriptions from defense, aerospace, and other sectors.
- **T1218.010 System Binary Proxy Execution: Regsvr32** — During Operation Dream Job, Lazarus Group used `regsvr32` to execute malware.
- **T1218.011 System Binary Proxy Execution: Rundll32** — During Operation Dream Job, Lazarus Group executed malware with `C:\\windows\system32\rundll32.exe "C:\ProgramData\ThumbNail\thumbnail.db"`, `CtrlPanel S-6-81-3811-75432205-060098-6872 0 0 905`.
- **T1220 XSL Script Processing** — During Operation Dream Job, Lazarus Group used a remote XSL script to download a Base64-encoded DLL custom downloader.
- **T1221 Template Injection** — During Operation Dream Job, Lazarus Group used DOCX files to retrieve a malicious document template/DOTM file.
- **T1497.001 Virtualization/Sandbox Evasion: System Checks** — During Operation Dream Job, Lazarus Group used tools that conducted a variety of system checks to detect sandboxes or VMware services.
- **T1497.003 Virtualization/Sandbox Evasion: Time Based Checks** — During Operation Dream Job, Lazarus Group used tools that collected `GetTickCount` and `GetSystemTimeAsFileTime` data to detect sandbox or VMware services.
- **T1505.004 Server Software Component: IIS Components** — During Operation Dream Job, Lazarus Group targeted Windows servers running Internet Information Systems (IIS) to install C2 components.
- **T1534 Internal Spearphishing** — During Operation Dream Job, Lazarus Group conducted internal spearphishing from within a compromised organization.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — During Operation Dream Job, Lazarus Group placed LNK files into the victims' startup folder for persistence.
- **T1553.002 Subvert Trust Controls: Code Signing** — During Operation Dream Job, Lazarus Group digitally signed their own malware to evade detection.
- **T1560.001 Archive Collected Data: Archive via Utility** — During Operation Dream Job, Lazarus Group archived victim's data into a RAR file.
- **T1566.001 Phishing: Spearphishing Attachment** — During Operation Dream Job, Lazarus Group sent emails with malicious attachments to gain unauthorized access to targets' computers.
- **T1566.002 Phishing: Spearphishing Link** — During Operation Dream Job, Lazarus Group sent malicious OneDrive links with fictitious job offer advertisements via email.
- **T1566.003 Phishing: Spearphishing via Service** — During Operation Dream Job, Lazarus Group sent victims spearphishing messages via LinkedIn concerning fictitious jobs.
- **T1567.002 Exfiltration Over Web Service: Exfiltration to Cloud Storage** — During Operation Dream Job, Lazarus Group used a custom build of open-source command-line dbxcli to exfiltrate stolen data to Dropbox.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — During Operation Dream Job, Lazarus Group used an AES key to communicate with their C2 server.
- **T1583.001 Acquire Infrastructure: Domains** — During Operation Dream Job, Lazarus Group registered a domain name identical to that of a compromised company as part of their BEC effort.
- **T1583.004 Acquire Infrastructure: Server** — During Operation Dream Job, Lazarus Group acquired servers to host their malicious tools.
- **T1583.006 Acquire Infrastructure: Web Services** — During Operation Dream Job, Lazarus Group used file hosting services like DropBox and OneDrive.
- **T1584.001 Compromise Infrastructure: Domains** — For Operation Dream Job, Lazarus Group compromised domains in Italy and other countries for their C2 infrastructure.
- **T1584.004 Compromise Infrastructure: Server** — For Operation Dream Job, Lazarus Group compromised servers to host their malicious tools.
- **T1585.001 Establish Accounts: Social Media Accounts** — For Operation Dream Job, Lazarus Group created fake LinkedIn accounts for their targeting efforts.
- **T1585.002 Establish Accounts: Email Accounts** — During Operation Dream Job, Lazarus Group created fake email accounts to correspond with fake LinkedIn personas; Lazarus Group also established email accounts to match those of the victim as part of their BEC attempt.
- **T1587.001 Develop Capabilities: Malware** — For Operation Dream Job, Lazarus Group developed custom tools such as Sumarta, DBLL Dropper, Torisma, and DRATzarus for their operations.
- **T1587.002 Develop Capabilities: Code Signing Certificates** — During Operation Dream Job, Lazarus Group digitally signed their malware and the dbxcli utility.
- **T1588.002 Obtain Capabilities: Tool** — For Operation Dream Job, Lazarus Group obtained tools such as Wake-On-Lan, Responder, ChromePass, and dbxcli.
- **T1588.003 Obtain Capabilities: Code Signing Certificates** — During Operation Dream Job, Lazarus Group used code signing certificates issued by Sectigo RSA for some of its malware and tools.
- **T1589 Gather Victim Identity Information** — For Operation Dream Job, Lazarus Group conducted extensive reconnaissance research on potential targets.
- **T1591 Gather Victim Org Information** — For Operation Dream Job, Lazarus Group gathered victim organization information to identify specific targets.
- **T1591.004 Gather Victim Org Information: Identify Roles** — During Operation Dream Job, Lazarus Group targeted specific individuals within an organization with tailored job vacancy announcements.
- **T1593.001 Search Open Websites/Domains: Social Media** — For Operation Dream Job, Lazarus Group used LinkedIn to identify and target employees within a chosen organization.
- **T1608.001 Stage Capabilities: Upload Malware** — For Operation Dream Job, Lazarus Group used compromised servers to host malware.
- **T1608.002 Stage Capabilities: Upload Tool** — For Operation Dream Job, Lazarus Group used multiple servers to host malicious tools.
- **T1614.001 System Location Discovery: System Language Discovery** — During Operation Dream Job, Lazarus Group deployed malware designed not to run on computers set to Korean, Japanese, or Chinese in Windows language preferences.
- **T1622 Debugger Evasion** — During Operation Dream Job, Lazarus Group used tools that used the `IsDebuggerPresent` call to detect debuggers.
- **T1684.001 Social Engineering: Impersonation** — During Operation Dream Job, Lazarus Group impersonated HR hiring personnel through LinkedIn messages and conducted interviews with victims in order to deceive them into downloading malware.

## Software used

- **S0174 Responder**
- **S0678 Torisma** — During Operation Dream Job, Lazarus Group used Torisma to actively monitor for new drives and remote desktop connections on an infected system.
- **S0694 DRATzarus** — During Operation Dream Job, Lazarus Group used DRATzarus to deploy open source software and partly commodity software such as Responder, Wake-On-Lan, and ChromePass to target infected hosts.

## Attributed to

- **G0032 Lazarus Group**
