# T1701 — Command and Scripting Interpreter

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Execution
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1701
- **Last modified:** 2026-10-09

## Description

Adversaries may abuse command and script interpreters to execute commands, scripts, or binaries. These interfaces and languages provide ways of interacting with computer systems and are a common feature across many different platforms within industrial control system environments. Most systems come with some built-in command-line interface and scripting capabilities, for example, macOS and Linux distributions include some flavor of Unix Shell while Windows installations include the Windows Command Shell and PowerShell. Some also have cross-platform interpreters such as Python, as well as those commonly associated with client applications such as JavaScript and Visual Basic. Many controllers have command-line interfaces for management purposes. 

Adversaries may abuse these technologies in various ways as a means of executing arbitrary commands. Commands and scripts can be embedded in Initial Access payloads delivered to victims as lure documents or as secondary payloads downloaded from an existing C2. Adversaries may also execute commands through interactive terminals/shells, as well as utilize various Remote Services (e.g., Telnet, SSH, RDP, etc.) often found in industrial control system environments to achieve remote Execution.

## Sub-techniques

- **T1701.001 Command and Scripting Interpreter: PowerShell**
- **T1701.002 Command and Scripting Interpreter: Windows Command Shell**
- **T1701.003 Command and Scripting Interpreter: Unix Shell**
- **T1701.004 Command and Scripting Interpreter: Visual Basic**
- **T1701.005 Command and Scripting Interpreter: Python**
- **T1701.006 Command and Scripting Interpreter: JavaScript**

## Mitigations

- **M0938 Execution Prevention** — Execution prevention may block malicious software from accessing protected resources through the command-line interface.
- **M0942 Disable or Remove Feature or Program** — Consider removing or restricting features that are unnecessary to an asset's intended function within the control environment.
- **M0948 Application Isolation and Sandboxing** — Consider the use of application isolation and sandboxing to restrict specific operating system interactions such as access through user accounts, services, system calls, registry, and network access. This may be even more useful in cases where the source of the executed script is unknown.

## Detection strategies

- **DET0928 Behavioral Detection of Command and Scripting Abuse in ICS**
  - AN2082 (Windows): Real-time monitoring identifies a command-line interpreter (cmd.exe, PowerShell.exe) spawned as a child of an Industrial Control System (ICS) vendor application process, where this parent-child relationship is not part of the documented normal operation of that vendor software or directly spawned processes with a command line parameters containing ICS protocol/Application Programming Interface (API) interaction keywords, from a context not associated with documented automation scripts. Operational Technology (OT) operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: WinEventLog:Sysmon (EventCode=1).
  - AN2083 (Linux): Real-time monitoring identifies a command and scripting interpreter process spawned by an Industrial Control System (ICS) service process, or interactive shell sessions from unexpected Secure Shell (SSH) source Internet Protocol (IP) addresses or an unexpected User Identifier (UID) not associated with recognized ICS automation scripts, deviating from the expected execution baseline. Operational Technology (OT) operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: auditd:SYSCALL (syscall=execve; command or executable associated with the technique runs outside the approved ICS administrative/application baseline).
  - AN2084 (Network Devices): Real-time monitoring identifies an Industrial Control System (ICS) network-device command-line interface (CLI) commands (e.g., interface shutdown, access control list modification, network address translation changes, etc.) from a source or account outside the approved network-management baseline or network traffic patterns consistent with scripted command execution -- regular-interval connections with consistent payload sizes -- to field device Internet Protocol (IP) addresses from a host not normally exhibiting such regularity. Operational Technology (OT) operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: networkdevice:cli (shell command).
  - AN2085 (Embedded): Real-time monitoring identifies a session (Telnet, SSH, proprietary, etc.) opened to an embedded field device from a source not in the approved administrative CIDR, immediately followed by configuration-mode entry or high-risk commands (firmware operations, config write/erase, reload) or identifies sequences of Industrial Control System (ICS) protocol commands arriving at field devices that follow a scripted, deterministic pattern -- identical inter-command timing, systematic address iteration -- rather than the variable, operator-driven timing of legitimate engineering sessions. Operational Technology (OT) operational-fidelity gate: Alert only when execution violates an approved signer/hash/path/parent/process or tool allowlist, or originates from an unauthorized user/tool, and is tied to an OT asset or follow-on OT-relevant action. Suppress vendor-signed software, approved engineering utilities, diagnostics, patching, backup, and documented maintenance. Log sources: device:cli (Shell command).

## Procedure examples

- **C0030 Triton Safety Instrumented System Attack** (campaign) — In the Triton Safety Instrumented System Attack, TEMP.Veles’ tool took one option from the command line, which was a single IP address of the target Triconex device.
- **S1165 FrostyGoop** (software) — FrostyGoop is compiled for Windows systems and leverages a Windows-based command line interface. Modbus interaction functionality is based off a publicly available Github repository for command line input.
