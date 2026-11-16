# T1070 — Indicator Removal

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Stealth
- **Platforms:** Containers, ESXi, Linux, macOS, Network Devices, Office Suite, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1070
- **Last modified:** 2026-05-12

## Description

Adversaries may selectively delete or modify artifacts generated to reduce indications of their presence and blend in with legitimate activity. Rather than broadly removing evidence, adversaries may target specific artifacts that appear anomalous or are likely to draw scrutiny, while leaving sufficient data intact to maintain the appearance of normal system behavior.

Artifacts such as command histories, log entries, or file metadata may be altered in ways that align with expected user or system activity. Location, format, and type of artifact (such as command or login history) are often platform-specific, allowing adversaries to tailor modifications that minimize suspicion.

These actions may not prevent detection entirely but can delay recognition of malicious activity or reduce the fidelity of alerts by making events appear benign or consistent with routine operations. Additionally, selectively removed or modified artifacts may still be recoverable through deeper forensic analysis, though their absence or alteration can complicate timeline reconstruction and attribution.

## Sub-techniques

- **T1070.003 Indicator Removal: Clear Command History**
- **T1070.004 Indicator Removal: File Deletion**
- **T1070.005 Indicator Removal: Network Share Connection Removal**
- **T1070.006 Indicator Removal: Timestomp**
- **T1070.007 Indicator Removal: Clear Network Connection History and Configurations**
- **T1070.008 Indicator Removal: Clear Mailbox Data**
- **T1070.009 Indicator Removal: Clear Persistence**
- **T1070.010 Indicator Removal: Relocate Malware**

## Mitigations

- **M1022 Restrict File and Directory Permissions** — Protect generated event files that are stored locally with proper permissions and authentication and limit opportunities for adversaries to increase privileges by preventing Privilege Escalation opportunities.
- **M1029 Remote Data Storage** — Automatically forward events to a log server or data repository to prevent conditions in which the adversary can locate and manipulate data on the local system. When possible, minimize time delay on event reporting to avoid prolonged storage on the local system.
- **M1041 Encrypt Sensitive Information** — Obfuscate/encrypt event files locally and in transit to avoid giving feedback to an adversary.

## Detection strategies

- **DET0184 Behavioral Detection of Indicator Removal Across Platforms**
  - AN0520 (Windows): Monitors sequences involving deletion/modification of logs, registry keys, scheduled tasks, or prefetch files following suspicious process activity or elevated access escalation. Log sources: WinEventLog:Sysmon (EventCode=23); WinEventLog:Security (EventCode=1102); WinEventLog:Sysmon (EventCode=13, 14).
  - AN0521 (Linux): Detects deletion or overwriting of bash history, syslog, audit logs, and .ssh metadata following privilege elevation or suspicious process spawning. Log sources: auditd:SYSCALL (unlink, rename, open); linux:cli (cleared or truncated .bash_history).
  - AN0522 (macOS): Detects clearing of unified logs, deletion of plist files tied to persistence, and manipulation of Terminal history after initial execution. Log sources: macos:unifiedlog (log stream cleared or truncated); fs:fsusage (unlink, fs_delete); macos:osquery (File modifications in ~/Library/Preferences/).
  - AN0523 (Containers): Monitors tampering with audit logs, volumes, or mounted storage often used for side-channel logging (e.g., /var/log inside containers) post-compromise. Log sources: docker:daemon (container file operations); ebpf:syscalls (Unexpected container volume unmount + file deletion).
  - AN0524 (ESXi): Tracks suspicious use of ESXi shell commands or PowerCLI to delete logs, rotate system files, or tamper with hostd/vpxa history. Log sources: esxi:hostd (rm, clearlogs, logrotate).
  - AN0525 (Office Suite): Detects deletion or hiding of security-related mail rules, audit mailboxes, or calendar/log sync artifacts indicative of tampering post-intrusion. Log sources: m365:exchange (Remove-InboxRule, Clear-Mailbox); m365:unified (PurgeAuditLogs, Remove-MailboxAuditLog).

## Procedure examples

- **C0024 SolarWinds Compromise** (campaign) — During the SolarWinds Compromise, APT29 temporarily replaced legitimate utilities with their own, executed their payload, and then restored the original file.
- **C0029 Cutting Edge** (campaign) — During Cutting Edge, threat actors cleared logs to remove traces of their activity and restored compromised systems to a clean state to bypass manufacturer mitigations for CVE-2023-46805 and CVE-2024-21887.
- **G0032 Lazarus Group** (group) — Lazarus Group has restored malicious KernelCallbackTable code to its original state after the process execution flow has been hijacked.
- **G0129 Mustang Panda** (group) — Mustang Panda has deleted registry keys that store data and maintained persistence.
- **G1023 APT5** (group) — APT5 has used the THINBLOOD utility to clear SSL VPN log files located at `/home/runtime/logs`.
- **G1044 APT42** (group) — APT42 has cleared Chrome browser history.
- **S0089 BlackEnergy** (software) — BlackEnergy has removed the watermark associated with enabling the `TESTSIGNING` boot configuration option by removing the relevant strings in the `user32.dll.mui` of the system.
- **S0229 Orz** (software) — Orz can overwrite Registry settings to reduce its visibility on the victim.
- **S0239 Bankshot** (software) — Bankshot deletes all artifacts associated with the malware from the infected machine.
- **S0332 Remcos** (software) — Remcos can clean saved cookies and logins from the web browser.
- **S0448 Rising Sun** (software) — Rising Sun can clear a memory blog in the process by overwriting it with junk bytes.
- **S0449 Maze** (software) — Maze has used the “Wow64RevertWow64FsRedirection” function following attempts to delete the shadow volumes, in order to leave the system in the same state as it was prior to redirection.
- **S0455 Metamorfo** (software) — Metamorfo has a command to delete a Registry key it uses, `\Software\Microsoft\Internet Explorer\notes`.
- **S0461 SDBbot** (software) — SDBbot has the ability to clean up and remove data structures from a compromised host.
- **S0527 CSPY Downloader** (software) — CSPY Downloader has the ability to remove values it writes to the Registry.
- **S0559 SUNBURST** (software) — SUNBURST removed HTTP proxy registry values to clean up traces of execution.
- **S0568 EVILNUM** (software) — EVILNUM has a function called "DeleteLeftovers" to remove certain artifacts of the attack.
- **S0589 Sibot** (software) — Sibot will delete an associated registry key if a certain server response is received.
- **S0596 ShadowPad** (software) — ShadowPad has deleted arbitrary Registry values.
- **S0603 Stuxnet** (software) — Stuxnet can delete OLE Automation and SQL stored procedures used to store malicious payloads.
- **S0673 DarkWatchman** (software) — DarkWatchman can uninstall malicious components from the Registry, stop processes, and clear the browser history.
- **S0691 Neoichor** (software) — Neoichor can clear the browser history on a compromised host by changing the `ClearBrowsingHistoryOnExit` value to 1 in the `HKEY_CURRENT_USER\Software\Microsoft\Internet Explorer\Privacy` Registry key.
- **S0692 SILENTTRINITY** (software) — SILENTTRINITY can remove artifacts from the compromised host, including created Registry keys.
- **S0695 Donut** (software) — Donut can erase file references to payloads in-memory after being reflectively loaded and executed.
- **S0696 Flagpro** (software) — Flagpro can close specific Windows Security and Internet Explorer dialog boxes to mask external connections.
- **S0697 HermeticWiper** (software) — HermeticWiper can disable pop-up information about folders and desktop items and delete Registry keys to hide malicious services.
- **S1044 FunnyDream** (software) — FunnyDream has the ability to clean traces of malware deployment.
- **S1085 Sardonic** (software) — Sardonic has the ability to delete created WMI objects to evade detections.
- **S1132 IPsec Helper** (software) — IPsec Helper can delete various registry keys related to its execution and use.
- **S1135 MultiLayer Wiper** (software) — MultiLayer Wiper uses a batch script to clear file system cache memory via the `ProcessIdleTasks` export in `advapi32.dll` as an anti-analysis and anti-forensics technique.
- **S1159 DUSTTRAP** (software) — DUSTTRAP restores the `.text` section of compromised DLLs after malicious code is loaded into memory and before the file is closed.
- **S1161 BPFDoor** (software) — BPFDoor clears the file location `/proc/<PID>/environ` removing all environment variables for the process.
- **S9029 IronWind** (software) — IronWind has used a .NET DLL named "exit-DN4-core.dll" to terminate malicious processes running on victim's systems.
