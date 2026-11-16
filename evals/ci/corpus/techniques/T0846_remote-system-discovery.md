# T0846 — Remote System Discovery

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Discovery
- **Platforms:** Embedded, Windows, Linux, Network Devices
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0846
- **Last modified:** 2026-10-13

## Description

Adversaries may attempt to get a listing of other systems by IP address, hostname, or other logical identifier on a network that may be used for subsequent Lateral Movement or Discovery techniques. Functionality could exist within adversary tools to enable this, but utilities available on the operating system or vendor software could also be used.

## Sub-techniques

- **T0846.001 Remote System Discovery: Port Scan**
- **T0846.002 Remote System Discovery: Broadcast Discovery**
- **T0846.003 Remote System Discovery: Multicast Discovery**

## Mitigations

- **M0814 Static Network Configuration** — ICS environments typically have more statically defined devices, therefore minimize the use of both IT discovery protocols (e.g., DHCP, LLDP) and discovery functions in automation protocols. Examples of automation protocols with discovery capabilities include OPC UA Device Discovery, BACnet, and Ethernet/IP.

## Detection strategies

- **DET0739 Detection of Remote System Discovery**
  - AN1872 (Windows): Real-time monitoring identifies execution of network discovery tools (nmap, PLCScan, redpoint NSE scripts) or Industrial Control System (ICS)-specific scanners from an Industrial Control System (ICS) Windows host, from a process not associated with a recognized network management or engineering tool. OT operational-fidelity gate: Do not alert on novelty, scan/read volume, or enumeration alone. Alert when the source role is not authorized for discovery/polling and the target scope, address/tag range, protocol, or rate deviates from the established operational baseline. Suppress normal SCADA/HMI/historian polling, commissioning, asset inventory, backup, diagnostics, and approved engineering activity. Log sources: WinEventLog:Sysmon (EventCode=1 of network discovery tool (nmap, PLCScan) from process not in authorized network tools list).
  - AN2132 (Linux): Real-time monitoring identifies execution of network discovery tools on an Industrial Control System (ICS) Linux asset by a User Identifier (UID) that does not normally perform network scanning. OT operational-fidelity gate: Do not alert on novelty, scan/read volume, or enumeration alone. Alert when the source role is not authorized for discovery/polling and the target scope, address/tag range, protocol, or rate deviates from the established operational baseline. Suppress normal SCADA/HMI/historian polling, commissioning, asset inventory, backup, diagnostics, and approved engineering activity. Log sources: auditd:SYSCALL (Linux Audit SYSCALL/EXECVE/SOCKADDR records (configured audit rule): execve of network discovery tool (nmap, arp-scan, PLCScan) by User Identifier (UID) not in authorized net admin UIDs).
  - AN2171 (Embedded): Real-time network monitoring identifies a source generating Industrial Control System (ICS) discovery broadcasts or sequential connection attempts across the full IP range of a device subnet, from a source not in the approved engineering/Supervisory Control and Data Acquisition (SCADA) inventory. Documented in the PIPEDREAM/INCONTROLLER toolset's CODECALL module for EtherNet/IP device discovery. OT operational-fidelity gate: Do not alert on novelty, scan/read volume, or enumeration alone. Alert when the source role is not authorized for discovery/polling and the target scope, address/tag range, protocol, or rate deviates from the established operational baseline. Suppress normal SCADA/HMI/historian polling, commissioning, asset inventory, backup, diagnostics, and approved engineering activity. Log sources: netflow:ipfix (IPFIX/NetFlow flow record (src/dst IP, src/dst port, protocol, packets/bytes/time): source generates flows to every IP in device subnet in sequential order within discovery time window); NSM:Content (EtherNet/IP ListIdentity broadcast or sequential Industrial Control System (ICS) protocol connection attempts across Internet Protocol (IP) range from source not in approved Supervisory Control and Data Acqusition (SCADA) servers).
  - AN2172 (Network Devices): Real-time monitoring identifies Internet Control Message Protocol (ICMP) echo sweeps, Address Resolution Protocol (ARP) broadcast floods, or Industrial Control System (ICS)-specific discovery protocol packets from a host generating traffic to all IPs in a subnet in sequential order, a sweep pattern distinct from normal operational traffic to known device Internet Protocol (IP) addresses only. OT operational-fidelity gate: Do not alert on novelty, scan/read volume, or enumeration alone. Alert when the source role is not authorized for discovery/polling and the target scope, address/tag range, protocol, or rate deviates from the established operational baseline. Suppress normal SCADA/HMI/historian polling, commissioning, asset inventory, backup, diagnostics, and approved engineering activity. Log sources: netflow:ipfix (IPFIX/NetFlow flow record (src/dst IP, src/dst port, protocol, packets/bytes/time): Internet Control Message Protocol (ICMP) echo requests or Address Resolution Protocol (ARP) broadcasts to all Internet Protocol (IP) addresses in subnet sequentially from single source within discovery time window).

## Procedure examples

- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, Sandworm Team remotely discovered operational assets once on the OT network.
- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, the adversaries used `nslookup` and `ping` to conduct remote system discovery activities.
- **S0093 Backdoor.Oldrea** (software) — The Backdoor.Oldrea ICS malware plugin relies on Windows networking (WNet) to discover all the servers, including OPC servers, that are reachable by the compromised machine over the network.
- **S0604 Industroyer** (software) — Industroyer contains an OPC DA module that enumerates all OPC servers using the `ICatInformation::EnumClassesOfCategories` method with `CATID_OPCDAServer20` category identifier and `IOPCServer::GetStatus` to identify the ones running.
- **S1045 INCONTROLLER** (software) — INCONTROLLER can use the FINS (Factory Interface Network Service) protocol to scan for and obtain MAC address associated with Omron devices.
