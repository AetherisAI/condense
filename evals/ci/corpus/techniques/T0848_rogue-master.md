# T0848 — Rogue Master

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Initial Access
- **Platforms:** Embedded, Windows, Linux, Network Devices
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0848
- **Last modified:** 2026-10-13

## Description

Adversaries may setup a rogue master to leverage control server functions to communicate with outstations. A rogue master can be used to send legitimate control messages to other control system devices, affecting processes in unintended ways. It may also be used to disrupt network communications by capturing and receiving the network traffic meant for the actual master. Impersonating a master may also allow an adversary to avoid detection. 

In the case of the 2017 Dallas Siren incident, adversaries used a rogue master to send command messages to the 156 distributed sirens across the city, either through a single rogue transmitter with a strong signal, or using many distributed repeaters.

## Mitigations

- **M0802 Communication Authenticity** — Protocols used for control functions should provide authenticity through MAC functions or digital signatures. If not, utilize bump-in-the-wire devices or VPNs to enforce communication authenticity between devices that are not capable of supporting this (e.g., legacy controllers, RTUs).
- **M0807 Network Allowlists** — Use host-based allowlists to prevent devices from accepting connections from unauthorized systems. For example, allowlists can be used to ensure devices can only connect with master stations or known management/engineering workstations.
- **M0813 Software Process and Device Authentication** — Devices should authenticate all messages between master and outstation assets.
- **M0930 Network Segmentation** — Segment operational assets and their management devices based on their functional role within the process. Enabling more strict isolation to more critical control and operational information within the control environment.
- **M0937 Filter Network Traffic** — Perform inline allowlisting of automation protocol commands to prevent devices from sending unauthorized command or reporting messages. Allow/denylist techniques need to be designed with sufficient accuracy to prevent the unintended blocking of valid reporting messages.

## Detection strategies

- **DET0792 Detection of Rogue Master**
  - AN1924 (Embedded): Real-time monitoring identifies Industrial Control System (ICS) master-role command traffic originating from a source not in the approved control server inventory, directed at multiple field devices in a pattern consistent with control-server behavior. Documented in Maroochy Water Services (falsified PDS/station addresses to impersonate the master) and the 2017 Dallas Siren incident (rogue radio transmitter to 156 sirens). OT operational-fidelity gate: Alert only when the master/station identity or source is not authorized for the target device and command function, or when a normally authorized master violates its configured role/sequence and produces a corroborating device/process-state change. Suppress legitimate redundancy/failover, hot-standby promotion, commissioning, and approved engineering master activity. Log sources: assetinventory:MasterAddress (command traffic uses master/station address not in registered master addresses); operationaldb:AlarmEvent (device receives commands from two distinct master identities within a short window); NSM:Content (write/control command traffic from source not in approved Supervisory Control and Data Acquisition (SCADA) servers directed at multiple distinct device IPs within rogue master time window).
  - AN2151 (Linux): Real-time monitoring identifies a Linux process opening Industrial Control System (ICS) protocol master connections to multiple field device Internet Protocol (IP) addresses, from a host that is not the authorized Supervisory Control and Data Acquisition (SCADA) server. OT operational-fidelity gate: Alert only when the master/station identity or source is not authorized for the target device and command function, or when a normally authorized master violates its configured role/sequence and produces a corroborating device/process-state change. Suppress legitimate redundancy/failover, hot-standby promotion, commissioning, and approved engineering master activity. Log sources: auditd:SYSCALL (Linux Audit SYSCALL/EXECVE/SOCKADDR records (configured audit rule): connect syscalls show a host outside the approved SCADA/master set opening ICS-protocol connections to multiple field devices).
  - AN2178 (Network Devices): Real-time monitoring identifies a new device appearing on the Industrial Control System (ICS) network with network behavior consistent with an ICS master station, with a Media Access Control (MAC) address not in the approved device inventory. OT operational-fidelity gate: Alert only when the master/station identity or source is not authorized for the target device and command function, or when a normally authorized master violates its configured role/sequence and produces a corroborating device/process-state change. Suppress legitimate redundancy/failover, hot-standby promotion, commissioning, and approved engineering master activity. Log sources: netflow:ipfix (IPFIX/NetFlow flow record (src/dst IP, src/dst port, protocol, packets/bytes/time): new device Media Access Control (MAC) address on Industrial Control Systems (ICS) network generating ICS master-pattern traffic such as polling multiple device Internet Protocol (IP) addresses on ICS protocol ports).
  - AN2278 (Windows): Real-time monitoring identifies Industrial Control System (ICS) protocol master-role traffic originating from a Windows host that is not the authorized Supervisory Control and Data Acquisition (SCADA) or Distributed Control System (DCS) server. OT operational-fidelity gate: Alert only when the master/station identity or source is not authorized for the target device and command function, or when a normally authorized master violates its configured role/sequence and produces a corroborating device/process-state change. Suppress legitimate redundancy/failover, hot-standby promotion, commissioning, and approved engineering master activity. Log sources: WinEventLog:Sysmon (EventCode=3 unexpected Windows host opening Industrial Control Systems (ICS) protocol connections to multiple field device Internet Protocol (IP) addresses in polling pattern characteristic of master station).

## Procedure examples

- **C0020 Maroochy Water Breach** (campaign) — In the Maroochy Water Breach, the adversary falsified network addresses in order to send false data and instructions to pumping stations.
