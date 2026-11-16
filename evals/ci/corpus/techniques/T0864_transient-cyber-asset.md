# T0864 — Transient Cyber Asset

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Initial Access
- **Platforms:** Windows, Linux
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0864
- **Last modified:** 2026-10-13

## Description

Adversaries may target devices that are transient across ICS networks and external networks. Normally, transient assets are brought into an environment by authorized personnel and do not remain in that environment on a permanent basis. Transient assets are commonly needed to support management functions and may be more common in systems where a remotely managed asset is not feasible, external connections for remote access do not exist, or 3rd party contractor/vendor access is required. 

Adversaries may take advantage of transient assets in different ways. For instance, adversaries may target a transient asset when it is connected to an external network and then leverage its trusted access in another environment to launch an attack. They may also take advantage of installed applications and libraries that are used by legitimate end-users to interact with control system devices. 

Transient assets, in some cases, may not be deployed with a secure configuration leading to weaknesses that could allow an adversary to propagate malicious executable code, e.g., the transient asset may be infected by malware and when connected to an ICS environment the malware propagates onto other systems.

## Mitigations

- **M0930 Network Segmentation** — Segment and control software movement between business and OT environments by way of one directional DMZs. Web access should be restricted from the OT environment. Engineering workstations, including transient cyber assets (TCAs) should have minimal connectivity to external networks, including Internet and email, further limit the extent to which these devices are dual-homed to multiple networks.
- **M0941 Encrypt Sensitive Information** — Consider implementing full disk encryption, especially if engineering workstations are transient assets that are more likely to be lost, stolen, or tampered with.
- **M0947 Audit** — Integrity checking of transient assets can include performing the validation of the booted operating system and programs using TPM-based technologies, such as Secure Boot and Trusted Boot. It can also include verifying filesystem changes, such as programs and configuration files stored on the system, executing processes, libraries, accounts, and open ports.
- **M0949 Antivirus/Antimalware** — Install anti-virus software on all workstation and transient assets that may have external access, such as to web, email, or remote file shares.
- **M0951 Update Software** — Update software on control network assets when possible. If feasible, use modern operating systems and software to reduce exposure to known vulnerabilities.

## Detection strategies

- **DET0744 Detection of Transient Cyber Asset**
  - AN1877 (Windows): Real-time monitoring identifies a device establishing its first network connection to Industrial Control System (ICS) application servers from an Internet Protocol (IP) address or Media Access Control (MAC) address not previously seen in the environment, immediately following a new device association event on the network. OT operational-fidelity gate: Alert only when the account/device/session violates the approved identity + source host/jump path/zone policy and is corroborated by access to a protected OT asset, execution, configuration change, or another security-relevant follow-on event. Suppress approved shift activity, vendor support, break-glass use, commissioning, and documented remote-access windows. Log sources: netflow:ipfix (IPFIX/NetFlow flow record (src/dst IP, src/dst port, protocol, packets/bytes/time): connection from newly-observed device to Industrial Control Systems (ICS) application server within new device window of first network appearance); WinEventLog:Security (Windows Security Event ID 4624/4625: EventCode=4624 from a device Media Access Control (MAC) address/hardware-ID first observed on the network, not in approved device inventory).
  - AN2254 (Linux): Real-time monitoring identifies an Secure Shell (SSH) connection to an Industrial Control System (ICS) Linux asset from a source Internet Protocol (IP) address that appeared on the ICS network within a short window and is not in the approved device inventory. OT operational-fidelity gate: Alert only when the account/device/session violates the approved identity + source host/jump path/zone policy and is corroborated by access to a protected OT asset, execution, configuration change, or another security-relevant follow-on event. Suppress approved shift activity, vendor support, break-glass use, commissioning, and documented remote-access windows. Log sources: syslog:auth (Secure Shell (SSH) connection from source Internet Protocol (IP) address that appeared on Industrial Control Systems (ICS) network within new device window, not in approved device inventory).

## Procedure examples

- **C0020 Maroochy Water Breach** (campaign) — In the Maroochy Water Breach, the adversary utilized a computer, possibly stolen, with proprietary engineering software to communicate with a wastewater system.
