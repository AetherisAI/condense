# S0053 — SeaDuke

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Also known as:** SeaDaddy, SeaDesk
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0053
- **Last modified:** 2025-04-25

## Description

SeaDuke is malware that was used by APT29 from 2014 to 2015. It was used primarily as a secondary backdoor for victims that were already compromised with CozyCar.

## Techniques used

- **T1027.002 Obfuscated Files or Information: Software Packing** — SeaDuke has been packed with the UPX packer.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — SeaDuke uses a module to execute Mimikatz with PowerShell to perform Pass the Ticket.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — SeaDuke is capable of executing commands.
- **T1070.004 Indicator Removal: File Deletion** — SeaDuke can securely delete files, including deleting itself from the victim.
- **T1071.001 Application Layer Protocol: Web Protocols** — SeaDuke uses HTTP and HTTPS for C2.
- **T1078 Valid Accounts** — Some SeaDuke samples have a module to extract email from Microsoft Exchange servers using compromised credentials.
- **T1105 Ingress Tool Transfer** — SeaDuke is capable of uploading and downloading files.
- **T1114.002 Email Collection: Remote Email Collection** — Some SeaDuke samples have a module to extract email from Microsoft Exchange servers using compromised credentials.
- **T1132.001 Data Encoding: Standard Encoding** — SeaDuke C2 traffic is base64-encoded.
- **T1546.003 Event Triggered Execution: Windows Management Instrumentation Event Subscription** — SeaDuke uses an event filter in WMI code to execute a previously dropped executable shortly after system startup.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — SeaDuke is capable of persisting via the Registry Run key or a .lnk file stored in the Startup directory.
- **T1547.009 Boot or Logon Autostart Execution: Shortcut Modification** — SeaDuke is capable of persisting via a .lnk file stored in the Startup directory.
- **T1550.003 Use Alternate Authentication Material: Pass the Ticket** — Some SeaDuke samples have a module to use pass the ticket with Kerberos for authentication.
- **T1560.002 Archive Collected Data: Archive via Library** — SeaDuke compressed data with zlib prior to sending it over C2.
- **T1573.001 Encrypted Channel: Symmetric Cryptography** — SeaDuke C2 traffic has been encrypted with RC4 and AES.

## Used by

- **G0016 APT29** (group)
