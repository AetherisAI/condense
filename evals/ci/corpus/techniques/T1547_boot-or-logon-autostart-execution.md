# T1547 — Boot or Logon Autostart Execution

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Persistence, Privilege Escalation
- **Platforms:** Linux, macOS, Windows, Network Devices
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1547
- **Last modified:** 2025-10-24

## Description

Adversaries may configure system settings to automatically execute a program during system boot or logon to maintain persistence or gain higher-level privileges on compromised systems. Operating systems may have mechanisms for automatically running a program on system boot or account logon. These mechanisms may include automatically executing programs that are placed in specially designated directories or are referenced by repositories that store configuration information, such as the Windows Registry. An adversary may achieve the same goal by modifying or extending features of the kernel.

Since some boot or logon autostart programs run with higher privileges, an adversary may leverage these to elevate privileges.

## Sub-techniques

- **T1547.001 Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder**
- **T1547.002 Boot or Logon Autostart Execution: Authentication Package**
- **T1547.003 Boot or Logon Autostart Execution: Time Providers**
- **T1547.004 Boot or Logon Autostart Execution: Winlogon Helper DLL**
- **T1547.005 Boot or Logon Autostart Execution: Security Support Provider**
- **T1547.006 Boot or Logon Autostart Execution: Kernel Modules and Extensions**
- **T1547.007 Boot or Logon Autostart Execution: Re-opened Applications**
- **T1547.008 Boot or Logon Autostart Execution: LSASS Driver**
- **T1547.009 Boot or Logon Autostart Execution: Shortcut Modification**
- **T1547.010 Boot or Logon Autostart Execution: Port Monitors**
- **T1547.012 Boot or Logon Autostart Execution: Print Processors**
- **T1547.013 Boot or Logon Autostart Execution: XDG Autostart Entries**
- **T1547.014 Boot or Logon Autostart Execution: Active Setup**
- **T1547.015 Boot or Logon Autostart Execution: Login Items**

## Detection strategies

- **DET0274 Boot or Logon Autostart Execution Detection Strategy**
  - AN0764 (Windows): Correlation of registry key modification for Run/RunOnce with abnormal parent-child process relationships and outlier execution at user logon or system startup Log sources: WinEventLog:Security (EventCode=4688); WinEventLog:Sysmon (EventCode=13, 14).
  - AN0765 (Linux): Correlates creation/modification of systemd service files or /etc/init.d scripts with outlier process behavior during boot Log sources: auditd:SYSCALL (creat); auditd:SYSCALL (write); auditd:SYSCALL (Execution of binaries located in /etc/init.d/ or systemd service paths).
  - AN0766 (macOS): Observes creation or modification of LaunchAgent/LaunchDaemon property list files combined with anomalous plist payload execution after user logon Log sources: macos:unifiedlog (Observed loading of new LaunchAgent or LaunchDaemon plist); macos:unifiedlog (write); macos:unifiedlog (Execution of binary listed in newly modified LaunchAgent plist).

## Procedure examples

- **G1044 APT42** (group) — APT42 has modified the Registry to maintain persistence.
- **S0083 Misdat** (software) — Misdat has created registry keys for persistence, including `HKCU\Software\dnimtsoleht\StubPath`, `HKCU\Software\snimtsOleht\StubPath`, `HKCU\Software\Backtsaleht\StubPath`, `HKLM\SOFTWARE\Microsoft\Active Setup\Installed. Components\{3bf41072-b2b1-21c8-b5c1-bd56d32fbda7}`, and `HKLM\SOFTWARE\Microsoft\Active Setup\Installed Components\{3ef41072-a2f1-21c8-c5c1-70c2c3bc7905}`.
- **S0084 Mis-Type** (software) — Mis-Type has created registry keys for persistence, including `HKCU\Software\bkfouerioyou`, `HKLM\SOFTWARE\Microsoft\Active Setup\Installed Components\{6afa8072-b2b1-31a8-b5c1-{Unique Identifier}`, and `HKLM\SOFTWARE\Microsoft\Active Setup\Installed Components\{3BF41072-B2B1-31A8-B5C1-{Unique Identifier}`.
- **S0567 Dtrack** (software) — Dtrack’s RAT makes a persistent target file with auto execution on the host start.
- **S0651 BoxCaon** (software) — BoxCaon established persistence by setting the `HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\Windows\load` registry key to point to its executable.
- **S0653 xCaon** (software) — xCaon has added persistence via the Registry key `HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\Windows\load` which causes the malware to run each time any user logs in.
