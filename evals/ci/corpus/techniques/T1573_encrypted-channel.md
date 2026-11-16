# T1573 — Encrypted Channel

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Command and Control
- **Platforms:** ESXi, Linux, macOS, Network Devices, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1573
- **Last modified:** 2026-09-03

## Description

Adversaries may employ an encryption algorithm to conceal command and control traffic rather than relying on any inherent protections provided by a communication protocol. Despite the use of a secure algorithm, these implementations may be vulnerable to reverse engineering if secret keys are encoded and/or generated within malware samples/configuration files.

## Sub-techniques

- **T1573.001 Encrypted Channel: Symmetric Cryptography**
- **T1573.002 Encrypted Channel: Asymmetric Cryptography**

## Mitigations

- **M1020 SSL/TLS Inspection** — SSL/TLS inspection can be used to see the contents of encrypted sessions to look for network-based indicators of malware communication protocols.
- **M1031 Network Intrusion Prevention** — Network intrusion detection and prevention systems that use network signatures to identify traffic for specific adversary malware can be used to mitigate activity at the network level.

## Detection strategies

- **DET0273 Detection Strategy for Encrypted Channel across OS Platforms**
  - AN0759 (Windows): Processes that normally do not initiate network connections establishing outbound encrypted TLS/SSL sessions, especially with asymmetric traffic volumes (client sending more than receiving) or non-standard certificate chains. Defender observations correlate process creation with unexpected network encryption libraries being loaded. Log sources: WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Sysmon (EventCode=7).
  - AN0760 (Linux): Processes like curl, wget, python, socat, or custom binaries initiating TLS/SSL sessions to non-standard destinations. Defender sees abnormal syscalls for connect(), loading of libssl libraries, and persistent outbound encrypted traffic from daemons not normally communicating externally. Log sources: auditd:SYSCALL (socket/connect with TLS context by unexpected process); linux:syslog (system daemons initiating TLS sessions outside expected services); linux:osquery (Processes linked with libssl or crypto libraries making outbound connections).
  - AN0761 (macOS): Applications or launchd jobs initiating encrypted TLS traffic to rare external hosts. Defender observes unified logs showing ssl/TLS API calls by processes not baseline-approved, and payload entropy suggesting encrypted C2 sessions. Log sources: macos:unifiedlog (Encrypted session initiation by unexpected binary); macos:unifiedlog (Process invoking SSL routines from Security framework).
  - AN0762 (ESXi): VMware management daemons or guest processes initiating encrypted connections outside expected vCenter, update servers, or internal comms. Defender identifies hostd or vpxa initiating outbound TLS flows with uncommon destinations. Log sources: esxi:vpxd (TLS session established by ESXi service to unapproved endpoint); esxi:vmkernel (Inspection of sockets showing encrypted sessions from non-baseline processes).
  - AN0763 (Network Devices): Unusual TLS tunnels through ports not normally encrypted (e.g., TLS on port 8080, 53). Defender sees NetFlow/IPFIX or packet inspection indicating high-entropy traffic volumes and asymmetric client/server exchange ratios. Log sources: NSM:Flow (Session records with TLS-like byte patterns); NSM:Connections (Abnormal certificate chains or non-standard ports carrying TLS).

## Procedure examples

- **C0030 Triton Safety Instrumented System Attack** (campaign) — In the Triton Safety Instrumented System Attack, TEMP.Veles used cryptcat binaries to encrypt their traffic.
- **C0035 KV Botnet Activity** (campaign) — KV Botnet Activity command and control activity includes transmission of an RSA public key in communication from the server, but this is followed by subsequent negotiation stages that represent a form of handshake similar to TLS negotiation.
- **G0016 APT29** (group) — APT29 has used multiple layers of encryption within malware to protect C2 communication.
- **G0059 Magic Hound** (group) — Magic Hound has used an encrypted http proxy in C2 communications.
- **G0081 Tropic Trooper** (group) — Tropic Trooper has encrypted traffic with the C2 to prevent network detection.
- **G1002 BITTER** (group) — BITTER has encrypted their C2 communications.
- **S0032 gh0st RAT** (software) — gh0st RAT has encrypted TCP communications to evade detection.
- **S0198 NETWIRE** (software) — NETWIRE can encrypt C2 communications.
- **S0367 Emotet** (software) — Emotet has encrypted data before sending to the C2 server.
- **S0498 Cryptoistic** (software) — Cryptoistic can engage in encrypted communications with C2.
- **S0631 Chaes** (software) — Chaes has used encryption for its C2 channel.
- **S0662 RCSession** (software) — RCSession can use an encrypted beacon to check in with C2.
- **S0681 Lizar** (software) — Lizar can support encrypted communications between the client and server.
- **S1012 PowerLess** (software) — PowerLess can use an encrypted channel for C2 communications.
- **S1016 MacMa** (software) — MacMa has used TLS encryption to initialize a custom protocol for C2 communications.
- **S1046 PowGoop** (software) — PowGoop can receive encrypted commands from C2.
- **S1198 Gomir** (software) — Gomir uses a custom encryption algorithm for content sent to command and control infrastructure.
