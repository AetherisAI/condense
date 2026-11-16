# T1692 — Unauthorized Message

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Evasion, Impair Process Control
- **Platforms:** Embedded, Windows, Linux
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1692
- **Last modified:** 2026-10-13

## Description

Adversaries may send unauthorized messages to ICS systems and devices to evade defenses or manipulate processes. Unauthorized messages can be categorized as either reporting messages that contain telemetry data about the current state of systems, devices, and processes or as command messages which instruct systems and devices on how to operate. By injecting unauthorized messages, adversaries can make it appear as if everything is working correctly when it isn’t, trigger alarms to misdirect personnel or impact processes, and manipulate controls to disrupt processes.

Adversaries may send unauthorized messages in an ICS environment using software found within the environment (living-off-the-land, vendor-specific interfaces, etc.), custom tooling leveraging OT protocols and libraries, or by positioning themselves between systems and devices and injecting messages into the communications such as the case with an Adversary-in-the-Middle attack.

## Sub-techniques

- **T1692.001 Unauthorized Message: Command Message**
- **T1692.002 Unauthorized Message: Reporting Message**

## Mitigations

- **M0802 Communication Authenticity** — Protocols used for control functions should provide authenticity through MAC functions or digital signatures. If not, utilize bump-in-the-wire devices or VPNs to enforce communication authenticity between devices that are not capable of supporting this (e.g., legacy controllers, RTUs).
- **M0807 Network Allowlists** — Use host-based allowlists to prevent devices from accepting connections from unauthorized systems. For example, allowlists can be used to ensure devices can only connect with master stations or known management/engineering workstations.
- **M0813 Software Process and Device Authentication** — Devices should authenticate all messages between master and outstation assets.
- **M0930 Network Segmentation** — Segment operational assets and their management devices based on their functional role within the process. Enabling more strict isolation to more critical control and operational information within the control environment.
- **M0937 Filter Network Traffic** — Perform inline allowlisting of automation protocol commands to prevent devices from sending unauthorized command or reporting messages. Allow/denylist techniques need to be designed with sufficient accuracy to prevent the unintended blocking of valid messages.

## Detection strategies

- **DET0902 Detection of Unauthorized Message**
  - AN2045 (Embedded): Real-time monitoring identifies an Industrial Control System (ICS) protocol message arriving at a device from a source whose identity is not in the approved communication baseline for that destination, where the message is structurally valid but originates outside the documented set of legitimate communicators. This technique-level analytic synthesizes Command Message (T1692.001) and Reporting Message (T1692.002). OT operational-fidelity gate: Alert only when the action is not attributable to an authorized operator/engineering source for the specific target and function, and it is either outside an approved change/maintenance window or lacks matching change-control context; where telemetry permits, require corroborating device, configuration, or process-state effect. Suppress activity that fully matches approved maintenance, commissioning, failover, recovery, or tested control procedures. Log sources: netflow:ipfix (IPFIX/NetFlow flow record (src/dst IP, src/dst port, protocol, packets/bytes/time): first-seen connection from a source to an Industrial Control System (ICS) device outside the documented approved communication matrix); NSM:Content (structurally valid Industrial Control System (ICS) protocol message from source not in approved communication baseline for the destination device_ip).
  - AN2160 (Linux): Real-time monitoring identifies an Industrial Control System (ICS) protocol library loaded by a Linux process not in the authorized ICS applications list, making connections to the device subnet. OT operational-fidelity gate: Alert only when the action is not attributable to an authorized operator/engineering source for the specific target and function, and it is either outside an approved change/maintenance window or lacks matching change-control context; where telemetry permits, require corroborating device, configuration, or process-state effect. Suppress activity that fully matches approved maintenance, commissioning, failover, recovery, or tested control procedures. Log sources: auditd:SYSCALL (Linux Audit SYSCALL/EXECVE/SOCKADDR records (configured audit rule): connect syscall from an ICS service/application process to a destination outside the approved network or vendor-service baseline).
  - AN2283 (Windows): Real-time monitoring identifies a Windows process making Industrial Control System (ICS) protocol connections to device subnets from a process not in the authorized ICS applications list, structurally valid traffic from an unauthorized source. OT operational-fidelity gate: Alert only when the action is not attributable to an authorized operator/engineering source for the specific target and function, and it is either outside an approved change/maintenance window or lacks matching change-control context; where telemetry permits, require corroborating device, configuration, or process-state effect. Suppress activity that fully matches approved maintenance, commissioning, failover, recovery, or tested control procedures. Log sources: WinEventLog:Sysmon (EventCode=3 to device subnet from process not in authorized Industrial Control Systems (ICS) applications).
