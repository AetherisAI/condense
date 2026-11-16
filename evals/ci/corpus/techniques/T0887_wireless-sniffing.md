# T0887 — Wireless Sniffing

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Collection, Discovery
- **Platforms:** Embedded, Windows, Linux
- **ATT&CK URL:** https://attack.mitre.org/techniques/T0887
- **Last modified:** 2026-10-13

## Description

Adversaries may seek to capture radio frequency (RF) communication used for remote control and reporting in distributed environments. RF communication frequencies vary between 3 kHz to 300 GHz, although are commonly between 300 MHz to 6 GHz. The wavelength and frequency of the signal affect how the signal propagates through open air, obstacles (e.g. walls and trees) and the type of radio required to capture them. These characteristics are often standardized in the protocol and hardware and may have an effect on how the signal is captured. Some examples of wireless protocols that may be found in cyber-physical environments are: WirelessHART, Zigbee, WIA-FA, and 700 MHz Public Safety Spectrum. 

Adversaries may capture RF communications by using specialized hardware, such as software defined radio (SDR), handheld radio, or a computer with radio demodulator tuned to the communication frequency. Information transmitted over a wireless medium may be captured in-transit whether the sniffing device is the intended destination or not. This technique may be particularly useful to an adversary when the communications are not encrypted. 

In the 2017 Dallas Siren incident, it is suspected that adversaries likely captured wireless command message broadcasts on a 700 MHz frequency during a regular test of the system. These messages were later replayed to trigger the alarm systems.

## Mitigations

- **M0806 Minimize Wireless Signal Propagation** — Reduce the range of RF communications to their intended operating range when possible. Propagation reduction methods may include (i) reducing transmission power on wireless signals, (ii) adjusting antenna gain to prevent extensions beyond organizational boundaries, and (iii) employing RF shielding techniques to block excessive signal propagation.
- **M0808 Encrypt Network Traffic** — Utilize strong cryptographic techniques and protocols to prevent eavesdropping on network communications.

## Detection strategies

- **DET0743 Detection of Wireless Sniffing**
  - AN1876 (Embedded): Real-time monitoring identifies indirect evidence of passive RF capture on Industrial Control System (ICS) wireless frequencies -- an unassociated device's RF signature detected without a completed association sequence, or a known device's Media Access Control (MAC) address detected from a location/signal strength inconsistent with its registered installation point. OT operational-fidelity gate: Do not alert on novelty, scan/read volume, or enumeration alone. Alert when the source role is not authorized for discovery/polling and the target scope, address/tag range, protocol, or rate deviates from the established operational baseline. Suppress normal SCADA/HMI/historian polling, commissioning, asset inventory, backup, diagnostics, and approved engineering activity. Log sources: wireless:spectrum (Radio Frequency (RF) signal detected on Industrial Control Systems (ICS) wireless frequencies from Media Access Control (MAC) address not in approved wireless device inventory without completed association sequence).
  - AN2134 (Linux): Real-time monitoring identifies a process on an Industrial Control System (ICS) Linux asset setting a wireless interface to monitor mode via iwconfig or netlink calls, from a User Identifier (UID) not associated with documented wireless diagnostics. OT operational-fidelity gate: Do not alert on novelty, scan/read volume, or enumeration alone. Alert when the source role is not authorized for discovery/polling and the target scope, address/tag range, protocol, or rate deviates from the established operational baseline. Suppress normal SCADA/HMI/historian polling, commissioning, asset inventory, backup, diagnostics, and approved engineering activity. Log sources: auditd:SYSCALL (Linux Audit SYSCALL/EXECVE/SOCKADDR records (configured audit rule): execve of wireless configuration utility setting monitor mode on Industrial Control Systems (ICS) Linux asset by User Identifier (UID) not in authorized wireless admin UIDs).
  - AN2272 (Windows): Real-time monitoring identifies a Windows process enabling promiscuous or monitor mode on a wireless adapter on an Industrial Control System (ICS) workstation that is not a designated wireless management station, indicating preparation for wireless interception. OT operational-fidelity gate: Do not alert on novelty, scan/read volume, or enumeration alone. Alert when the source role is not authorized for discovery/polling and the target scope, address/tag range, protocol, or rate deviates from the established operational baseline. Suppress normal SCADA/HMI/historian polling, commissioning, asset inventory, backup, diagnostics, and approved engineering activity. Log sources: WinEventLog:Sysmon (EventCode=6 for wireless capture driver on host not in designated wireless management station list).
