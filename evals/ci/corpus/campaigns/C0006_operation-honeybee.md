# C0006 — Operation Honeybee

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **First seen:** 2017-08-01
- **Last seen:** 2018-02-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0006
- **Last modified:** 2026-07-31

## Description

Operation Honeybee was a campaign that targeted humanitarian aid and inter-Korean affairs organizations from at least late 2017 through early 2018. Operation Honeybee initially targeted South Korea, but expanded to include Vietnam, Singapore, Japan, Indonesia, Argentina, and Canada. Security researchers assessed the threat actors were likely Korean speakers based on metadata used in both lure documents and executables, and named the campaign "Honeybee" after the author name discovered in malicious Word documents.

## Techniques used

- **T1005 Data from Local System** — During Operation Honeybee, the threat actors collected data from compromised hosts.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — During Operation Honeybee, the threat actors used Base64 to encode files with a custom key.
- **T1036 Masquerading** — During Operation Honeybee, the threat actors modified the MaoCheng dropper so its icon appeared as a Word document.
- **T1036.005 Masquerading: Match Legitimate Resource Name or Location** — During Operation Honeybee, the threat actors used a legitimate Windows executable and secure directory for their payloads to bypass UAC.
- **T1041 Exfiltration Over C2 Channel** — During Operation Honeybee, the threat actors uploaded stolen files to their C2 servers.
- **T1057 Process Discovery** — During Operation Honeybee, the threat actors obtained a list of running processes on a victim machine using `cmd /c tasklist > %temp%\temp.ini`.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — During Operation Honeybee, various implants used batch scripting and `cmd.exe` for execution.
- **T1059.005 Command and Scripting Interpreter: Visual Basic** — For Operation Honeybee, the threat actors used a Visual Basic script embedded within a Word document to download an implant.
- **T1070.004 Indicator Removal: File Deletion** — During Operation Honeybee, the threat actors used batch files that reduced their fingerprint on a compromised system by deleting malware-related files.
- **T1071.002 Application Layer Protocol: File Transfer Protocols** — During Operation Honeybee, the threat actors had the ability to use FTP for C2.
- **T1074.001 Data Staged: Local Data Staging** — During Operation Honeybee, stolen data was copied into a text file using the format `From <COMPUTER-NAME> (<Month>-<Day> <Hour>-<Minute>-<Second>).txt` prior to compression, encoding, and exfiltration.
- **T1082 System Information Discovery** — During Operation Honeybee, the threat actors collected the computer name, OS, and other system information using `cmd /c systeminfo > %temp%\ temp.ini`.
- **T1083 File and Directory Discovery** — During Operation Honeybee, the threat actors used a malicious DLL to search for files with specific keywords.
- **T1105 Ingress Tool Transfer** — During Operation Honeybee, the threat actors downloaded additional malware and malicious scripts onto a compromised host.
- **T1106 Native API** — During Operation Honeybee, the threat actors deployed malware that used API calls, including `CreateProcessAsUser`.
- **T1112 Modify Registry** — During Operation Honeybee, the threat actors used batch files that modified registry keys.
- **T1140 Deobfuscate/Decode Files or Information** — During Operation Honeybee, malicious files were decoded prior to execution.
- **T1204.002 User Execution: Malicious File** — During Operation Honeybee, threat actors relied on a victim to enable macros within a malicious Word document.
- **T1543.003 Create or Modify System Process: Windows Service** — During Operation Honeybee, threat actors installed DLLs and backdoors as Windows services.
- **T1548.002 Abuse Elevation Control Mechanism: Bypass User Account Control** — During Operation Honeybee, the threat actors used the malicious NTWDBLIB.DLL and `cliconfig.exe` to bypass UAC protections.
- **T1553.002 Subvert Trust Controls: Code Signing** — During Operation Honeybee, the threat actors deployed the MaoCheng dropper with a stolen Adobe Systems digital signature.
- **T1560.001 Archive Collected Data: Archive via Utility** — During Operation Honeybee, the threat actors uses zip to pack collected files before exfiltration.
- **T1569.002 System Services: Service Execution** — During Operation Honeybee, threat actors ran `sc start` to start the COMSysApp as part of the service hijacking and `sc stop` to stop and reconfigure the COMSysApp.
- **T1574.011 Hijack Execution Flow: Services Registry Permissions Weakness** — During Operation Honeybee, the threat actors used a batch file that modified the COMSysApp service to load a malicious ipnet.dll payload and to load a DLL into the `svchost.exe` process.
- **T1583.001 Acquire Infrastructure: Domains** — During Operation Honeybee, threat actors registered domains for C2.
- **T1583.004 Acquire Infrastructure: Server** — For Operation Honeybee, at least one identified persona was used to register for a free account for a control server.
- **T1585.002 Establish Accounts: Email Accounts** — During Operation Honeybee, attackers created email addresses to register for a free account for a control server used for the implants.
- **T1588.004 Obtain Capabilities: Digital Certificates** — For Operation Honeybee, the threat actors stole a digital signature from Adobe Systems to use with their MaoCheng dropper.

## Software used

- **S0057 Tasklist**
- **S0075 Reg**
- **S0096 Systeminfo**
- **S0106 cmd**
- **S0464 SYSCON** — Operation Honeybee included the use of an upgraded version of SYSCON.
