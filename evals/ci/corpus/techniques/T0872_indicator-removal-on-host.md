# T0872 — Indicator Removal on Host

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Evasion
- **Platforms:** Embedded, Windows, Linux, Network Devices
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0872
- **Last modified:** 2026-10-13

## Description

Adversaries may attempt to remove indicators of their presence on a system in an effort to cover their tracks. In cases where an adversary may feel detection is imminent, they may try to overwrite, delete, or cover up changes they have made to the device.

## Mitigations

- **M0922 Restrict File and Directory Permissions** — Protect files stored locally with proper permissions to limit opportunities for adversaries to remove indicators of their activity on the system.

## Detection strategies

- **DET0750 Detection of Indicator Removal on Host**
  - AN1882 (Windows): Real-time monitoring identifies an audit log clearing event or deletion/truncation of an Industrial Control System (ICS) vendor application log file, immediately preceded by other suspicious activity on the same host within a short lookback window. Documented in the CaddyWiper deployment alongside Industroyer2, explicitly intended to destroy evidence and slow forensic recovery. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: WinEventLog:Security (Windows Security Event ID 4688: EventCode=1102 correlated with any other Medium+ confidence alert on the same host within log clear lookback window); WinEventLog:Sysmon (EventCode=23 or wevtutil/Clear-EventLog invocation deleting Industrial Control Systems (ICS) vendor application log file by process not in authorized log management tools); WinEventLog:System (EventCode=104 outside scheduled log rotation window).
  - AN2113 (Linux): Real-time monitoring identifies truncation or deletion of Industrial Control System (ICS) application or auth log files, or modification of bash history, by a User Identifier (UID) that does not normally manage log rotation. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: auditd:SYSCALL+PATH (Linux Audit SYSCALL+PATH records: modification of bash_history file by uid not normally performing interactive shell sessions); auditd:SYSCALL+PATH (Linux Audit SYSCALL+PATH records: truncate/shred/rm on Industrial Control Systems (ICS) application log files or auth.log by User Identifier (UID) not in authorized log admin UIDs).
  - AN2192 (Network Devices): Real-time monitoring identifies Industrial Control System (ICS) network device syslog showing a gap in expected event sequence numbers, or syslog forwarding interruption from a device coinciding with a period of suspicious activity on that device. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: networkdevice:syslog (syslog sequence number gap or forwarding interruption coinciding with suspicious activity window for the same device).
  - AN2245 (Embedded): Real-time monitoring identifies Industrial Control System (ICS) field device event logs being cleared via ICS protocol commands from a source not in the approved engineering workstation list, occurring immediately following other suspicious ICS activity on the same device. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: NSM:Content (event buffer clear or log clear service from source not in engineering workstation list, correlated with preceding suspicious activity on the same device).

## Procedure examples

- **C0030 Triton Safety Instrumented System Attack** (campaign) — In the Triton Safety Instrumented System Attack, TEMP.Veles would programmatically return the controller to a normal running state if the Triton malware failed. If the controller could not recover in a defined time window, TEMP.Veles programmatically overwrote their malicious program with invalid data.
- **S0607 KillDisk** (software) — KillDisk deletes application, security, setup, and system event logs from Windows systems.
- **S1009 Triton** (software) — Triton would reset the controller to the previous state over TriStation and if this failed it would write a dummy program to memory in what was likely an attempt at anti-forensics.
