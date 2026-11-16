# T1071 — Application Layer Protocol

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Command and Control
- **Platforms:** Linux, macOS, Windows, Network Devices, ESXi
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1071
- **Last modified:** 2026-09-03

## Description

Adversaries may communicate using OSI application layer protocols to avoid detection/network filtering by blending in with existing traffic. Commands to the remote system, and often the results of those commands, will be embedded within the protocol traffic between the client and server. 

Adversaries may utilize many different protocols, including those used for web browsing, transferring files, electronic mail, DNS, or publishing/subscribing. For connections that occur internally within an enclave (such as those between a proxy or pivot node and other nodes), commonly used protocols are SMB, SSH, or RDP.

## Sub-techniques

- **T1071.001 Application Layer Protocol: Web Protocols**
- **T1071.002 Application Layer Protocol: File Transfer Protocols**
- **T1071.003 Application Layer Protocol: Mail Protocols**
- **T1071.004 Application Layer Protocol: DNS**
- **T1071.005 Application Layer Protocol: Publish/Subscribe Protocols**

## Mitigations

- **M1031 Network Intrusion Prevention** — Network intrusion detection and prevention systems that use network signatures to identify traffic for specific adversary malware can be used to mitigate activity at the network level.
- **M1037 Filter Network Traffic** — Use network appliances to filter ingress or egress traffic and perform protocol-based filtering. Configure software on endpoints to filter network traffic.

## Detection strategies

- **DET0444 Detection of Command and Control Over Application Layer Protocols**
  - AN1225 (Windows): Detects suspicious usage of common application-layer protocols (e.g., HTTP, HTTPS, DNS, SMB) by abnormal processes, with high outbound byte counts or irregular ports, possibly indicating command and control or data exfiltration. Log sources: NSM:Flow (http, dns, smb, ssl logs); WinEventLog:Sysmon (EventCode=3, 22).
  - AN1226 (Linux): Detects suspicious curl, wget, or custom socket traffic that leverages DNS, HTTPS, or IRC-style protocols with unbalanced traffic or beacon-like intervals. Log sources: NSM:Flow (dns, ssl, conn); auditd:SYSCALL (execve).
  - AN1227 (macOS): Detects applications using abnormal protocols or high volume traffic not previously associated with the process image, such as Automator or AppleScript invoking curl or python sockets. Log sources: macos:osquery (socket_events); macos:unifiedlog (log stream).
  - AN1228 (Network Devices): Detects application-layer tunneling or unauthorized app protocols like DNS-over-HTTPS, embedded C2 in TLS/HTTP headers, or misused SMB traffic crossing VLANs. Log sources: NSM:Flow (conn.log, http.log, dns.log, ssl.log).

## Procedure examples

- **C0041 FrostyGoop Incident** (campaign) — During FrostyGoop Incident, the adversary initiated Layer Two Tunnelling Protocol (L2TP) connections to Moscow-based IP addresses.
- **G0059 Magic Hound** (group) — Magic Hound malware has used IRC for C2.
- **G0106 Rocke** (group) — Rocke issued wget requests from infected systems to the C2.
- **G0139 TeamTNT** (group) — TeamTNT has used an IRC bot for C2 communications.
- **G1032 INC Ransom** (group) — INC Ransom has used valid accounts over RDP to connect to targeted systems.
- **G1047 Velvet Ant** (group) — Velvet Ant has used reverse SSH tunnels to communicate to victim devices.
- **G1059 NIMBUS MANTICORE** (group) — NIMBUS MANTICORE has leveraged reverse SSH shells for command and control.
- **S0034 NETEAGLE** (software) — Adversaries can also use NETEAGLE to establish an RDP connection with a controller over TCP/7519.
- **S0038 Duqu** (software) — Duqu uses a custom command and control protocol that communicates over commonly used ports, and is frequently encapsulated by application layer protocols.
- **S0532 Lucifer** (software) — Lucifer can use the Stratum protocol on port 10001 for communication between the cryptojacking bot and the mining server.
- **S0601 Hildegard** (software) — Hildegard has used an IRC channel for C2 communications.
- **S0623 Siloscape** (software) — Siloscape connects to an IRC server for C2.
- **S0633 Sliver** (software) — Sliver can utilize the Wireguard VPN protocol for command and control.
- **S0660 Clambling** (software) — Clambling has the ability to use Telnet for communication.
- **S1084 QUIETEXIT** (software) — QUIETEXIT can use an inverse negotiated SSH connection as part of its C2.
- **S1130 Raspberry Robin** (software) — Raspberry Robin is capable of contacting the TOR network for delivering second-stage payloads.
- **S1147 Nightdoor** (software) — Nightdoor uses TCP and UDP communication for command and control traffic.
