# T0849 — Masquerading

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Evasion
- **Platforms:** Embedded, Windows, Linux, Network Devices
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0849
- **Last modified:** 2026-10-13

## Description

Adversaries may use masquerading to disguise a malicious application or executable as another file, to avoid operator and engineer suspicion. Possible disguises of these masquerading files can include commonly found programs, expected vendor executables and configuration files, and other commonplace application and naming conventions. By impersonating expected and vendor-relevant files and applications, operators and engineers may not notice the presence of the underlying malicious content and possibly end up running those masquerading as legitimate functions. 

Applications and other files commonly found on Windows systems or in engineering workstations have been impersonated before. This can be as simple as renaming a file to effectively disguise it in the ICS environment.

## Mitigations

- **M0922 Restrict File and Directory Permissions** — Use file system access controls to protect system and application folders.
- **M0938 Execution Prevention** — Use tools that restrict program execution via application control by attributes other than file name for common system and application utilities.
- **M0945 Code Signing** — Require signed binaries.

## Detection strategies

- **DET0725 Detection of Masquerading**
  - AN1858 (Windows): Real-time monitoring identifies a process or scheduled task whose displayed name matches a known Industrial Control System (ICS) vendor application but whose on-disk binary hash or file path does not match the vendor-signed baseline. The mismatch -- name says one thing, binary integrity says another -- is the defining signal. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: WinEventLog:Security (Windows Security Event ID 4698/4702: EventCode=4698 referencing Industrial Control Systems (ICS) vendor binary name from unauthorized process); WinEventLog:Sysmon (EventCode=11 matching Industrial Control Systems (ICS) vendor binary name in a path outside vendor install paths); WinEventLog:Sysmon (EventCode=1 where image filename matches Industrial Control Systems (ICS) vendor process names but hash not in vendor hash baseline or current directory outside vendor install paths); WinEventLog:System (EventCode=7045 where ServiceName/ImagePath references Industrial Control Systems (ICS) vendor application with hash/path mismatch).
  - AN2123 (Linux): Real-time monitoring identifies a process whose executable name matches a known Industrial Control System (ICS) service daemon but whose execution path falls outside the documented vendor installation directories, or whose binary hash does not match the package manager's recorded checksum for that package. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: auditd:SYSCALL (Linux Audit SYSCALL/EXECVE/SOCKADDR records (configured audit rule): execve where exe basename matches Industrial Control Systems (ICS) daemon names but path outside vendor install paths); linux:pkgintegrity (rpm -V/dpkg --verify checksum mismatch for installed Industrial Control Systems (ICS) package binary).
  - AN2231 (Embedded): Real-time monitoring identifies an ICS device presenting protocol identity attributes (for example vendor, product, model, or capability identifiers) that conflict with the identity and capabilities recorded for that network address/device in the authorized asset inventory. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: NSM:Content (GetIdentity/Identity Object response vendor/product string does not match enrolled asset inventory for device_ip).
  - AN2287 (Network Devices): Real-time monitoring identifies traffic on an Industrial Control System (ICS) protocol port (e.g., 502, 20000, 44818, etc.) with payload content that does not conform to the expected protocol structure for that port, suggesting non-ICS traffic tunneled over ICS port numbers to evade port-based filtering or blend with expected traffic patterns. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: otids:ProtocolDecoder (Protocol decoder/IDS transaction/signature: exploit-relevant request against ICS remote service from unexpected source, correlated with subsequent endpoint/device anomaly).

## Procedure examples

- **C0025 2016 Ukraine Electric Power Attack** (campaign) — During the 2016 Ukraine Electric Power Attack, Sandworm Team transferred executable files as .txt and then renamed them to .exe, likely to avoid detection through extension tracking.
- **S0496 REvil** (software) — REvil searches for whether the Ahnlab autoup.exe service is running on the target system and injects its payload into this existing process.
- **S0603 Stuxnet** (software) — Stuxnet renames s7otbxdx.dll, a dll responsible for handling communications with a PLC. It replaces this dll file with its own version that allows it to intercept any calls that are made to access the PLC.
- **S0605 EKANS** (software) — EKANS masquerades itself as a valid executable with the filename update.exe. Many valid programs use the process name update.exe to perform background software updates.
- **S1009 Triton** (software) — Triton's injector, inject.bin, masquerades as a standard compiled PowerPC program for the Tricon. Triton was configured to masquerade as trilog.exe, which is the Triconex software for analyzing SIS logs.
