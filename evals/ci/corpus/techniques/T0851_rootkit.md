# T0851 — Rootkit

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Evasion, Inhibit Response Function
- **Platforms:** Embedded, Windows, Linux, Network Devices
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0851
- **Last modified:** 2026-10-13

## Description

Adversaries may deploy rootkits to hide the presence of programs, files, network connections, services, drivers, and other system components. Rootkits are programs that hide the existence of malware by intercepting and modifying operating-system API calls that supply system information. Rootkits or rootkit-enabling functionality may reside at the user or kernel level in the operating system, or lower. 

Firmware rootkits that affect the operating system yield nearly full control of the system. While firmware rootkits are normally developed for the main processing board, they can also be developed for the I/O that is attached to an asset. Compromise of this firmware allows the modification of all of the process variables and functions the module engages in. This may result in commands being disregarded and false information being fed to the main device. By tampering with device processes, an adversary may inhibit its expected response functions and possibly enable Impact.

## Mitigations

- **M0945 Code Signing** — Digital signatures may be used to ensure application DLLs are authentic prior to execution.
- **M0947 Audit** — Audit the integrity of PLC system and application code functionality, such as the manipulation of standard function blocks (e.g., Organizational Blocks) that manage the execution of application logic programs.

## Detection strategies

- **DET0780 Detection of Rootkit**
  - AN1912 (Embedded): Periodic or event-triggered integrity verification identifies a discrepancy between a field device's self-reported diagnostic state and an independently verified hardware/firmware fingerprint, indicating the device's reporting layer has been compromised. MITRE explicitly notes firmware/module rootkits 'can also be developed for the Input/Output (I/O) that is attached to an asset.'. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Monitoring reality: this is an integrity/posture analytic, not a universal streaming field-device event; collection cadence depends on the vendor integrity interface, asset-management system, or acquisition workflow. Log sources: assetinventory:FirmwareHash (device-reported firmware hash/version does not match independently verified value obtained through vendor integrity tool or physical inspection).
  - AN2146 (Linux): Real-time monitoring identifies inconsistencies between auditd-recorded process activity and what /proc reports, or kernel module loads from non-standard paths on Industrial Control System (ICS) Linux assets. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: auditd:SYSCALL (Linux Audit SYSCALL/EXECVE/SOCKADDR records (configured audit rule): syscall=init_module/finit_module; kernel module loaded from a path or hash not in the authorized ICS host module baseline).
  - AN2167 (Windows): Real-time monitoring identifies Industrial Control System (ICS) host telemetry gaps -- process lists differing between Windows Management Instrumentation (WMI) and direct enumeration, or unexpected kernel driver loads from unexpected paths -- suggesting kernel-level manipulation of what the Operating System (OS) reports. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: edr:TelemetryCompare (process enumeration discrepancy between Windows Management Instrumentation (WMI) and direct process listing); WinEventLog:Sysmon (EventCode=6 kernel driver load from path not in trusted driver paths, not signed by trusted signer list).
  - AN2185 (Network Devices): Real-time monitoring identifies Industrial Control System (ICS) network device telemetry gaps -- Simple Network Management Protocol (SNMP) polling returning inconsistent results, syslog sequence gaps -- suggesting kernel-level manipulation of device-reported state. OT operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: networkdevice:snmp (Simple Network Management Protocol (SNMP) polling inconsistency or syslog sequence gap suggesting telemetry manipulation).

## Procedure examples

- **S0603 Stuxnet** (software) — One of Stuxnet's rootkits is contained entirely in the fake s7otbxdx.dll. In order to continue existing undetected on the PLC it needs to account for at least the following situations: read requests for its own malicious code blocks, read requests for infected blocks (OB1, OB35, DP_RECV), and write requests that could overwrite Stuxnets own code. Stuxnet contains code to monitor and intercept these types of requests. The rootkit modifies these requests so that Stuxnets PLC code is not discovered or damaged.
