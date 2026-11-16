# T1693 — Modify Firmware

- **Type:** technique
- **Domain:** ICS ATT&CK
- **Tactics:** Impair Process Control, Inhibit Response Function, Persistence
- **Platforms:** Embedded
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1693
- **Last modified:** 2026-10-13

## Description

Firmware is low-level software embedded in hardware that enables systems and devices to function properly and is commonly found in ICS environments. Adversaries may modify firmware on a system or device by installing malicious or vulnerable versions that enable them to achieve objectives such as Persistence, Impair Process Control, and Inhibit Response Function. 

Adversaries may modify system and device firmware by using the built-in firmware update functionality which may support local or remote installation. The malicious or vulnerable firmware may be delivered via Replication Through Removable Media, Supply Chain Compromise, or Remote Services. Once installed, the malicious or vulnerable firmware could be used to provide Rootkit and Hooking functionality, Exploitation for Privilege Escalation, or Denial of Service.

## Sub-techniques

- **T1693.001 Modify Firmware: System Firmware**
- **T1693.002 Modify Firmware: Module Firmware**

## Mitigations

- **M0801 Access Management** — All devices or systems changes, including all administrative functions, should require authentication. Consider using access management technologies to enforce authorization on all management interface access attempts, especially when the device does not inherently provide strong authentication and authorization functions.
- **M0802 Communication Authenticity** — Protocols used for device management should authenticate all network messages to prevent unauthorized system changes.
- **M0804 Human User Authentication** — Devices that allow remote management of firmware should require authentication before allowing any changes. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **M0807 Network Allowlists** — Use host-based allowlists to prevent devices from accepting connections from unauthorized systems. For example, allowlists can be used to ensure devices can only connect with master stations or known management/engineering workstations.
- **M0808 Encrypt Network Traffic** — The encryption of firmware should be considered to prevent adversaries from identifying possible vulnerabilities within the firmware.
- **M0813 Software Process and Device Authentication** — Authenticate connections from software and devices to prevent unauthorized systems from accessing protected management functions.
- **M0930 Network Segmentation** — Segment operational network and systems to restrict access to critical system functions to predetermined management systems.
- **M0937 Filter Network Traffic** — Filter for protocols and payloads associated with firmware activation or updating activity.
- **M0941 Encrypt Sensitive Information** — The encryption of firmware should be considered to prevent adversaries from identifying possible vulnerabilities within the firmware.
- **M0945 Code Signing** — Devices should verify that firmware has been properly signed by the vendor before allowing installation.
- **M0946 Boot Integrity** — Check the integrity of the existing BIOS or EFI to determine if it is vulnerable to modification. Use Trusted Platform Module technology. Move system's root of trust to hardware to prevent tampering with the SPI flash memory. Technologies such as Intel Boot Guard can assist with this.
- **M0947 Audit** — Perform integrity checks of firmware before uploading it on a device. Utilize cryptographic hashes to verify the firmware has not been tampered with by comparing it to a trusted hash of the firmware. This could be from trusted data sources (e.g., vendor site) or through a third-party verification service.

## Detection strategies

- **DET0904 Detection of Firmware Modification**
  - AN2047 (Embedded): Real-time monitoring identifies the full firmware modification chain: a device entering firmware-update mode, receiving a large data transfer on a firmware-capable protocol port from a source not in the approved engineering workstation list, rebooting, and reporting a post-reboot firmware hash that does not match the authorized inventory. This technique-level analytic synthesizes System Firmware (T1693.001) and Module Firmware (T1693.002). OT operational-fidelity gate: Alert only when the action is not attributable to an authorized operator/engineering source for the specific target and function, and it is either outside an approved change/maintenance window or lacks matching change-control context; where telemetry permits, require corroborating device, configuration, or process-state effect. Suppress activity that fully matches approved maintenance, commissioning, failover, recovery, or tested control procedures. Log sources: assetinventory:FirmwareHash (post-reboot firmware hash (main processor or specific module) not in authorized firmware inventory); operationaldb:AlarmEvent (device reboot within firmware update window of the flagged transfer session); NSM:Content (large session on firmware-capable port from source not in engineering workstation list outside change control window).
