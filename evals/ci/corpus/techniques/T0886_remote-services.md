# T0886 — Remote Services

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Initial Access, Lateral Movement
- **Platforms:** Embedded, Windows, Linux, Network Devices
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0886
- **Last modified:** 2026-10-13

## Description

Adversaries may leverage remote services to move between assets and network segments. These services are often used to allow operators to interact with systems remotely within the network, some examples are RDP, SMB, SSH, and other similar mechanisms. 

Remote services could be used to support remote access, data transmission, authentication, name resolution, and other remote functions. Further, remote services may be necessary to allow operators and administrators to configure systems within the network from their engineering or management workstations. An adversary may use this technique to access devices which may be dual-homed to multiple network segments, and can be used for Program Download or to execute attacks on control devices directly through Valid Accounts.

Specific remote services (RDP & VNC) may be a precursor to enable Graphical User Interface execution on devices such as HMIs or engineering workstation software.

Based on incident data, CISA and FBI assessed that Chinese state-sponsored actors also compromised various authorized remote access channels, including systems designed to transfer data and/or allow access between corporate and ICS networks.

## Mitigations

- **M0800 Authorization Enforcement** — Provide privileges corresponding to the restriction of a GUI session to control system operations (examples include HMI read-only vs. read-write modes). Ensure local users, such as operators and engineers, are giving prioritization over remote sessions and have the authority to regain control over a remote session if needed. Prevent remote access sessions (e.g., RDP, VNC) from taking over local sessions, especially those used for ICS control, especially HMIs.
- **M0801 Access Management** — Access Management technologies can help enforce authentication on critical remote service, examples include, but are not limited to, device management services (e.g., telnet, SSH), data access servers (e.g., HTTP, Historians), and HMI sessions (e.g., RDP, VNC).
- **M0804 Human User Authentication** — All remote services should require strong authentication before providing user access.
- **M0807 Network Allowlists** — Network allowlists can be implemented through either host-based files or system host files to specify what external connections (e.g., IP address, MAC address, port, protocol) can be made from a device.
- **M0813 Software Process and Device Authentication** — All communication sessions to remote services should be authenticated to prevent unauthorized access.
- **M0918 User Account Management** — Limit the accounts that may use remote services. Limit the permissions for accounts that are at higher risk of compromise; for example, configure SSH so users can only run specific programs.
- **M0927 Password Policies** — Enforce strong password requirements to prevent password brute force methods for lateral movement.
- **M0930 Network Segmentation** — Segment and control software movement between business and OT environments by way of one directional DMZs. Web access should be restricted from the OT environment. Engineering workstations, including transient cyber assets (TCAs) should have minimal connectivity to external networks, including Internet and email, further limit the extent to which these devices are dual-homed to multiple networks.
- **M0937 Filter Network Traffic** — Filter application-layer protocol messages for remote services to block any unauthorized activity.

## Detection strategies

- **DET0804 Detection of Remote Services**
  - AN1936 (Windows): Real-time monitoring identifies a remote service connection between two Industrial Control System (ICS) network hosts that does not match the documented, approved communication matrix, where the destination host subsequently exhibits process execution or file access inconsistent with normal automated/scheduled inter-host communication. OT operational-fidelity gate: Alert only when the account/device/session violates the approved identity + source host/jump path/zone policy and is corroborated by access to a protected OT asset, execution, configuration change, or another security-relevant follow-on event. Suppress approved shift activity, vendor support, break-glass use, commissioning, and documented remote-access windows. Log sources: WinEventLog:Security (Windows Security Event ID 4624/4625: EventCode=4624, Type 3/10 between Industrial Control Systems (ICS) hosts not in approved lateral movement pairs); WinEventLog:Sysmon (EventCode=3 on remote service ports (e.g., 22, 445, 3389, 5985/5986) between hosts not in approved communication matrix); WinEventLog:Sysmon (Microsoft-Windows-Sysmon/Operational Event ID 1 ProcessCreate: Process execution within the remote session targeting Industrial Control Systems (ICS) application directories or device subnet connections).
  - AN2159 (Linux): Real-time monitoring identifies SSH lateral movement between Industrial Control System (ICS) Linux hosts not in the documented communication matrix, with subsequent ICS tool execution or privilege escalation. OT operational-fidelity gate: Alert only when the account/device/session violates the approved identity + source host/jump path/zone policy and is corroborated by access to a protected OT asset, execution, configuration change, or another security-relevant follow-on event. Suppress approved shift activity, vendor support, break-glass use, commissioning, and documented remote-access windows. Log sources: auditd:SYSCALL (Linux Audit SYSCALL/EXECVE/SOCKADDR records (configured audit rule): Industrial Control Systems (ICS) tool execution following Secure Shell (SSH) lateral movement session); syslog:auth (Secure Shell (SSH) session between Industrial Control Systems (ICS) hosts not in approved lateral movement pairs).
  - AN2180 (Network Devices): Real-time monitoring identifies new east-west connections between Industrial Control System (ICS) hosts on remote service ports not in the approved communication matrix. OT operational-fidelity gate: Alert only when the account/device/session violates the approved identity + source host/jump path/zone policy and is corroborated by access to a protected OT asset, execution, configuration change, or another security-relevant follow-on event. Suppress approved shift activity, vendor support, break-glass use, commissioning, and documented remote-access windows. Log sources: netflow:ipfix (IPFIX/NetFlow flow record (src/dst IP, src/dst port, protocol, packets/bytes/time): new east-west connection between Industrial Control Systems (ICS) hosts on remote service ports not in approved communication matrix).
  - AN2225 (Embedded): Real-time monitoring identifies Industrial Control System (ICS) protocol traffic originating from one field device Internet Protocol (IP) address to another field device, a pattern not consistent with the documented device-to-supervisory communication topology. OT operational-fidelity gate: Alert only when the account/device/session violates the approved identity + source host/jump path/zone policy and is corroborated by access to a protected OT asset, execution, configuration change, or another security-relevant follow-on event. Suppress approved shift activity, vendor support, break-glass use, commissioning, and documented remote-access windows. Log sources: NSM:Connections (field device Internet Protocol (IP) initiates connection to another field device IP, not in approved device-to-device communication matrix).

## Procedure examples

- **C0025 2016 Ukraine Electric Power Attack** (campaign) — During the 2016 Ukraine Electric Power Attack, Sandworm Team used MS-SQL access to a pivot machine, allowing code execution throughout the ICS network.
- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, Sandworm Team used an IT helpdesk software to move the mouse on ICS control devices to maliciously release electricity breakers.
- **C0030 Triton Safety Instrumented System Attack** (campaign) — In the Triton Safety Instrumented System Attack, TEMP.Veles utilized remote desktop protocol (RDP) jump boxes, poorly configured OT firewalls, along with other traditional malware backdoors, to move into the ICS environment.
- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, the adversaries gained initial access to the operational technology via the compromised Fortinet edge devices, and used used SSH, RDP, and SMB/Windows Admin Shares to connect to remote systems and execute commands.
- **G1027 CyberAv3ngers** (group) — During the 2026 Iranian Water Campaign, one victim reported actors leveraged Dropbear Secure Shell (SSH) software to enable remote access over port 22.
- **S0496 REvil** (software) — REvil uses the SMB protocol to encrypt files located on remotely connected file shares.
- **S0603 Stuxnet** (software) — Stuxnet executes malicious SQL commands in the WinCC database server to propagate to remote systems. The malicious SQL commands include xp_cmdshell, sp_dumpdbilog, and sp_addextendedproc.
- **S1045 INCONTROLLER** (software) — INCONTROLLER can use the CODESYS protocol to remotely connect to Schneider PLCs and perform maintenance functions on the device. INCONTROLLER can use Telnet to upload payloads and execute commands on Omron PLCs. The malware can also use HTTP-based CGI scripts (e.g., cpu.fcgi, ecat.fcgi) to gain administrative access to the device.
