# T1119 — Automated Collection

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Collection
- **Platforms:** IaaS, Linux, macOS, Office Suite, SaaS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1119
- **Last modified:** 2026-09-11

## Description

Once established within a system or network, an adversary may use automated techniques for collecting internal data. Methods for performing this technique could include use of a Command and Scripting Interpreter to search for and copy information fitting set criteria such as file type, location, or name at specific time intervals. 

In cloud-based environments, adversaries may also use cloud APIs, data pipelines, command line interfaces, or extract, transform, and load (ETL) services to automatically collect data. 

This functionality could also be built into remote access tools. 

This technique may incorporate use of other techniques such as File and Directory Discovery and Lateral Tool Transfer to identify and move files, as well as Cloud Service Dashboard and Cloud Storage Object Discovery to identify resources in cloud environments.

## Mitigations

- **M1029 Remote Data Storage** — Encryption and off-system storage of sensitive information may be one way to mitigate collection of files, but may not stop an adversary from acquiring the information if an intrusion persists over a long period of time and the adversary is able to discover and access the data through other means.
- **M1041 Encrypt Sensitive Information** — Encryption and off-system storage of sensitive information may be one way to mitigate collection of files, but may not stop an adversary from acquiring the information if an intrusion persists over a long period of time and the adversary is able to discover and access the data through other means. Strong passwords should be used on certain encrypted documents that use them to prevent offline cracking through Brute Force techniques.

## Detection strategies

- **DET0186 Automated File and API Collection Detection Across Platforms**
  - AN0531 (Windows): Automated execution of native utilities and scripts to discover, enumerate, and exfiltrate files and clipboard content. Focus is on detecting repeated file access, scripting engine use, and use of command-line utilities commonly leveraged by collection scripts. Log sources: WinEventLog:Sysmon (EventCode=1); WinEventLog:Sysmon (EventCode=11).
  - AN0532 (Linux): Repeated or automated access to user document directories or clipboard using shell scripts or utilities like xclip/pbpaste. Detectable via auditd syscall logs or osquery file events. Log sources: auditd:SYSCALL (execve); auditd:SYSCALL (open).
  - AN0533 (macOS): Use of pbpaste, AppleScript, or third-party automation frameworks (e.g., Automator) to collect clipboard or file content in bursts. Observable via unified logs. Log sources: macos:unifiedlog (logMessage contains pbpaste or osascript); macos:unifiedlog (subsystem=launchservices).
  - AN0534 (SaaS): Suspicious sign-ins to Graph API or sensitive resources using non-browser scripting agents (e.g., Python, PowerShell), often for programmatic access to mailbox or OneDrive content. Log sources: azure:signinlogs (Operation=UserLogin).

## Procedure examples

- **C0001 Frankenstein** (campaign) — During Frankenstein, the threat actors used Empire to automatically gather the username, domain name, machine name, and other system information.
- **C0014 Operation Wocao** (campaign) — During Operation Wocao, threat actors used a script to collect information about the infected system.
- **C0040 APT41 DUST** (campaign) — APT41 DUST used tools such as SQLULDR2 and PINEGROVE to gather local system and database information.
- **C0046 ArcaneDoor** (campaign) — ArcaneDoor included collection of packet capture and system configuration information.
- **C0058 SharePoint ToolShell Exploitation** (campaign) — During SharePoint ToolShell Exploitation, threat actors used a command shell to automatically iterate through web.config files to expose and collect machineKey settings.
- **C0062 Anthropic AI-orchestrated Campaign** (campaign) — During the Anthropic AI-orchestrated Campaign, the adversary used Claude Code to automatically collect and process large volumes of data from without human direction.
- **C0064 AI-Assisted Breach of Mexico's Government Infrastructure** (campaign) — During the AI-Assisted Breach of Mexico's Government Infrastructure, the adversary tasked Claude Code to automate data extraction jobs across multiple databases as a background process.
- **G0004 Ke3chang** (group) — Ke3chang has performed frequent and scheduled data collection from victim networks.
- **G0006 APT1** (group) — APT1 used a batch script to perform a series of discovery techniques and saves it to a text file.
- **G0007 APT28** (group) — APT28 used a publicly available tool to gather and compress multiple documents on the DCCC and DNC networks.
- **G0027 Threat Group-3390** (group) — Threat Group-3390 ran a command to compile an archive of file types of interest from the victim user's directories.
- **G0037 FIN6** (group) — FIN6 has used a script to iterate through a list of compromised PoS systems, copy and remove data to a log file, and to bind to events from the submit payment button.
- **G0040 Patchwork** (group) — Patchwork developed a file stealer to search C:\ and collect files with certain extensions. Patchwork also executed a script to enumerate all drives, store them as a list, and upload generated files to the C2 server.
- **G0045 menuPass** (group) — menuPass has used the Csvde tool to collect Active Directory files and data.
- **G0047 Gamaredon Group** (group) — Gamaredon Group has deployed scripts on compromised systems that automatically scan for interesting documents.
- **G0049 OilRig** (group) — OilRig has used automated collection.
- **G0053 FIN5** (group) — FIN5 scans processes on all victim systems in the environment and uses automated scripts to pull back the results.
- **G0081 Tropic Trooper** (group) — Tropic Trooper has collected information automatically using the adversary's USBferry attack.
- **G0114 Chimera** (group) — Chimera has used custom DLLs for continuous retrieval of data from memory.
- **G0121 Sidewinder** (group) — Sidewinder has used tools to automatically collect system and network configuration information.
- **G0125 HAFNIUM** (group) — HAFNIUM has used MSGraph to exfiltrate data from email, OneDrive, and SharePoint.
- **G0129 Mustang Panda** (group) — Mustang Panda used custom batch scripts to collect files automatically from a targeted system.
- **G0142 Confucius** (group) — Confucius has used a file stealer to steal documents and images with the following extensions: txt, pdf, png, jpg, doc, xls, xlm, odp, ods, odt, rtf, ppt, xlsx, xlsm, docx, pptx, and jpeg.
- **G1003 Ember Bear** (group) — Ember Bear engages in mass collection from compromised systems during intrusions.
- **G1030 Agrius** (group) — Agrius used a custom tool, `sql.net4.exe`, to query SQL databases and then identify and extract personally identifiable information.
- **G1035 Winter Vivern** (group) — Winter Vivern delivered a PowerShell script capable of recursively scanning victim machines looking for various file types before exfiltrating identified files via HTTP.
- **G1039 RedCurl** (group) — RedCurl has used batch scripts to collect data.
- **G1055 VOID MANTICORE** (group) — VOID MANTICORE conducted large-scale data exfiltration in the Stryker operation, consistent with automated or scripted collection against enterprise systems.
- **S0090 Rover** (software) — Rover automatically collects files from the local system and removable drives based on a predefined list of file extensions on a regular timeframe.
- **S0098 T9000** (software) — T9000 searches removable storage devices for files with a pre-defined list of file extensions (e.g. * .doc, *.ppt, *.xls, *.docx, *.pptx, *.xlsx). Any matching files are encrypted and written to a local user directory.
- **S0128 BADNEWS** (software) — BADNEWS monitors USB devices and copies files with certain extensions to a predefined directory.
- **S0136 USBStealer** (software) — For all non-removable drives on a victim, USBStealer executes automated collection of certain files for later exfiltration.
- **S0148 RTM** (software) — RTM monitors browsing activity and automatically captures screenshots if a victim browses to a URL matching one of a list of strings.
- **S0170 Helminth** (software) — A Helminth VBScript receives a batch script to execute a set of commands in a command prompt.
- **S0198 NETWIRE** (software) — NETWIRE can automatically archive collected data.
- **S0238 Proxysvc** (software) — Proxysvc automatically collects data about the victim and sends it to the control server.
- **S0239 Bankshot** (software) — Bankshot recursively generates a list of files within a directory and sends them back to the control server.
- **S0244 Comnie** (software) — Comnie executes a batch script to store discovery information in %TEMP%\info.dat and then uploads the temporarily file to the remote C2 server.
- **S0251 Zebrocy** (software) — Zebrocy scans the system and automatically collects files with the following extensions: .doc, .docx, ,.xls, .xlsx, .pdf, .pptx, .rar, .zip, .jpg, .jpeg, .bmp, .tiff, .kum, .tlg, .sbx, .cr, .hse, .hsf, and .lhz.
- **S0257 VERMIN** (software) — VERMIN saves each collected file with the automatically generated format {0:dd-MM-yyyy}.txt .
- **S0260 InvisiMole** (software) — InvisiMole can sort and collect specific documents as well as generate a list of all files on a newly inserted drive and store them in an encrypted file.
- **S0339 Micropsia** (software) — Micropsia executes an RAR tool to recursively archive files based on a predefined list of file extensions (*.xls, *.xlsx, *.csv, *.odt, *.doc, *.docx, *.ppt, *.pptx, *.pdf, *.mdb, *.accdb, *.accde, *.txt).
- **S0363 Empire** (software) — Empire can automatically gather the username, domain name, machine name, and other information from a compromised system.
- **S0378 PoshC2** (software) — PoshC2 contains a module for recursively parsing through files and directories to gather valid credit card numbers.
- **S0395 LightNeuron** (software) — LightNeuron can be configured to automatically collect files under a specified directory.
- **S0428 PoetRAT** (software) — PoetRAT used file system monitoring to track modification and enable automatic exfiltration.
- **S0438 Attor** (software) — Attor has automatically collected data about the compromised system.
- **S0443 MESSAGETAP** (software) — MESSAGETAP checks two files, keyword_parm.txt and parm.txt, for instructions on how to target and save data parsed and extracted from SMS message data from the network traffic. If an SMS message contained either a phone number, IMSI number, or keyword that matched the predefined list, it is saved to a CSV file for later theft by the threat actor.
- **S0445 ShimRatReporter** (software) — ShimRatReporter gathered information automatically, without instruction from a C2, related to the user and host machine that is compiled into a report and sent to the operators.
- **S0455 Metamorfo** (software) — Metamorfo has automatically collected mouse clicks, continuous screenshots on the machine, and set timers to collect the contents of the clipboard and website browsing.
- **S0458 Ramsay** (software) — Ramsay can conduct an initial scan for Microsoft Word documents on the local system, removable media, and connected network drives, before tagging and collecting them. It can continue tagging documents to collect with follow up scans.
- **S0466 WindTail** (software) — WindTail can identify and add files that possess specific file extensions to an array for archiving.
- **S0467 TajMahal** (software) — TajMahal has the ability to index and compress files into a send queue for exfiltration.
- **S0476 Valak** (software) — Valak can download a module to search for and build a report of harvested credential data.
- **S0491 StrongPity** (software) — StrongPity has a file searcher component that can automatically collect and archive files based on a predefined list of file extensions.
- **S0538 Crutch** (software) — Crutch can automatically monitor removable drives in a loop and copy interesting files.
- **S0597 GoldFinder** (software) — GoldFinder logged and stored information related to the route or hops a packet took from a compromised machine to a hardcoded C2 server, including the target C2 URL, HTTP response/status code, HTTP response headers and values, and data received from the C2 node.
- **S0622 AppleSeed** (software) — AppleSeed has automatically collected data from USB drives, keystrokes, and screen images before exfiltration.
- **S0684 ROADTools** (software) — ROADTools automatically gathers data from Azure AD environments using the Azure Graph API.
- **S0699 Mythic** (software) — Mythic supports scripting of file downloads from agents.
- **S1017 OutSteel** (software) — OutSteel can automatically scan for and collect files with specific extensions.
- **S1043 ccf32** (software) — ccf32 can be used to automatically collect files from a compromised host.
- **S1044 FunnyDream** (software) — FunnyDream can monitor files for changes and automatically collect them.
- **S1078 RotaJakiro** (software) — Depending on the Linux distribution, RotaJakiro executes a set of commands to collect device information and sends the collected information to the C2 server.
- **S1091 Pacu** (software) — Pacu can automatically collect data, such as CloudFormation templates, EC2 user data, AWS Inspector reports, and IAM credential reports.
- **S1101 LoFiSe** (software) — LoFiSe can collect all the files from the working directory every three hours and place them into a password-protected archive for further exfiltration.
- **S1109 PACEMAKER** (software) — PACEMAKER can enter a loop to read `/proc/` entries every 2 seconds in order to read a target application's memory.
- **S1111 DarkGate** (software) — DarkGate searches for stored credentials associated with cryptocurrency wallets and notifies the command and control server when identified.
- **S1131 NPPSPY** (software) — NPPSPY collection is automatically recorded to a specified file on the victim machine.
- **S1148 Raccoon Stealer** (software) — Raccoon Stealer collects files and directories from victim systems based on configuration data downloaded from command and control servers.
- **S1183 StrelaStealer** (software) — StrelaStealer attempts to identify and collect mail login data from Thunderbird and Outlook following execution.
- **S1213 Lumma Stealer** (software) — Lumma Stealer has automated collection of various information including cryptocurrency wallet details.
- **S9008 Shai-Hulud** (software) — Shai-Hulud has the ability to automatically collect host data, secrets, system information, and endpoints.
- **S9035 LAMEHUG** (software) — LAMEHUG can recursively copy files from targeted directories on victim hosts.
- **S9041 TeamPCP Cloud Stealer** (software) — TeamPCP Cloud Stealer can identify and collect credentials across over 50 file paths in Cloud, CI/CD, developer tooling, and container enviornments.
- **S9043 Mini Shai-Hulud** (software) — Mini Shai-Hulud has the ability to automatically compile gathered credentials from configuration files and password vaults within an archive and exfiltrate stolen data leveraging both a primary and fallback C2.
- **S9050 Vidar** (software) — Vidar has collected data using automated scripts within malicious executables.
- **S9058 SIGHTGRAB** (software) — SIGHTGRAB has autonomously captured screen shots at regular intervals.
