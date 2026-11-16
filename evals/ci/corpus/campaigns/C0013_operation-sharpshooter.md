# C0013 — Operation Sharpshooter

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **First seen:** 2017-09-01
- **Last seen:** 2019-03-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0013
- **Last modified:** 2026-07-31

## Description

Operation Sharpshooter was a global cyber espionage campaign that targeted nuclear, defense, government, energy, and financial companies, with many located in Germany, Turkey, the United Kingdom, and the United States. Security researchers noted the campaign shared many similarities with previous Lazarus Group operations, including fake job recruitment lures and shared malware code.

## Techniques used

- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — During Operation Sharpshooter, threat actors installed Rising Sun in the Startup folder and disguised it as `mssync.exe`.
- **T1055 Process Injection** — During Operation Sharpshooter, threat actors leveraged embedded shellcode to inject a downloader into the memory of Word.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — During Operation Sharpshooter, the threat actors used a VBA macro to execute a simple downloader that installed Rising Sun.
- **T1090 Proxy** — For Operation Sharpshooter, the threat actors used the ExpressVPN service to hide their location.
- **T1105 Ingress Tool Transfer** — During Operation Sharpshooter, additional payloads were downloaded after a target was infected with a first-stage downloader.
- **T1106 Native API** — During Operation Sharpshooter, the first stage downloader resolved various Windows libraries and APIs, including `LoadLibraryA()`, `GetProcAddress()`, and `CreateProcessA()`.
- **T1204.002 User Execution: Malicious File** — During Operation Sharpshooter, the threat actors relied on victims executing malicious Microsoft Word or PDF files.
- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder** — During Operation Sharpshooter, a first-stage downloader installed Rising Sun to `%Startup%\mssync.exe` on a compromised host.
- **T1559.002 Inter-Process Communication: Dynamic Data Exchange** — During Operation Sharpshooter, threat actors sent malicious Word OLE documents to victims.
- **T1583.006 Acquire Infrastructure: Web Services** — For Operation Sharpshooter, the threat actors used Dropbox to host lure documents and their first-stage downloader.
- **T1584.004 Compromise Infrastructure: Server** — For Operation Sharpshooter, the threat actors compromised a server they used as part of the campaign's infrastructure.
- **T1587.001 Develop Capabilities: Malware** — For Operation Sharpshooter, the threat actors used the Rising Sun modular backdoor.
- **T1608.001 Stage Capabilities: Upload Malware** — For Operation Sharpshooter, the threat actors staged malicious files on Dropbox and other websites.

## Software used

- **S0448 Rising Sun** — During the investigation of Operation Sharpshooter, security researchers identified Rising Sun in 87 organizations across the globe and subsequently discovered three variants.
