# T1542 — Pre-OS Boot

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Persistence, Stealth
- **Platforms:** Linux, macOS, Network Devices, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1542
- **Last modified:** 2026-05-12

## Description

Adversaries may abuse Pre-OS Boot mechanisms as a way to establish persistence on a system. During the booting process of a computer, firmware and various startup services are loaded before the operating system. These programs control flow of execution before the operating system takes control.

Adversaries may overwrite data in boot drivers or firmware such as BIOS (Basic Input/Output System) and The Unified Extensible Firmware Interface (UEFI) to persist on systems at a layer below the operating system. This can be particularly difficult to detect as malware at this level will not be detected by host software-based defenses.

## Sub-techniques

- **T1542.001 Pre-OS Boot: System Firmware**
- **T1542.002 Pre-OS Boot: Component Firmware**
- **T1542.003 Pre-OS Boot: Bootkit**
- **T1542.004 Pre-OS Boot: ROMMONkit**
- **T1542.005 Pre-OS Boot: TFTP Boot**

## Mitigations

- **M1026 Privileged Account Management** — Ensure proper permissions are in place to help prevent adversary access to privileged accounts necessary to perform these actions
- **M1035 Limit Access to Resource Over Network** — Prevent access to file shares, remote access to systems, unnecessary services. Mechanisms to limit access may include use of network concentrators, RDP gateways, etc.
- **M1046 Boot Integrity** — Use Trusted Platform Module technology and a secure or trusted boot process to prevent system integrity from being compromised. Check the integrity of the existing BIOS or EFI to determine if it is vulnerable to modification.
- **M1047 Audit** — Perform audits or scans of systems, permissions, insecure software, insecure configurations, etc. to identify potential weaknesses.
- **M1051 Update Software** — Patch the BIOS and EFI as necessary.

## Detection strategies

- **DET0278 Detection Strategy for T1542 Pre-OS Boot**
  - AN0774 (Windows): Unusual modification of boot records (MBR, VBR) or EFI partitions not associated with legitimate patch cycles or OS upgrades. Registry or WMI events associated with firmware update tools executed from unexpected parent processes. API calls (e.g., DeviceIoControl) writing directly to raw disk sectors. Subsequent abnormal boot configuration changes followed by unsigned driver loads. Log sources: WinEventLog:Security (EventCode=4688); WinEventLog:Sysmon (EventCode=11); WinEventLog:Sysmon (EventCode=9).
  - AN0775 (Linux): Detection of writes to /boot or EFI directories outside of expected package manager updates. Monitoring kernel log and auditd events for attempts to overwrite bootloader binaries (e.g., grub, shim). Unexpected execution of efibootmgr or dd writing to /dev/sdX devices followed by boot parameter changes. Log sources: auditd:SYSCALL (open, write: Modification of /boot/grub/* or /boot/efi/*); auditd:EXECVE (exec: Execution of dd, efibootmgr, or flashrom modifying firmware/boot partitions).
  - AN0776 (macOS): Abnormal modification of EFI firmware binaries in /System/Library/CoreServices/ or NVRAM parameters not associated with OS updates. Unified logs capturing calls to bless or nvram commands executed from untrusted parent processes. Sudden unsigned kext loads after EFI variable tampering. Log sources: macos:unifiedlog (Execution of bless or nvram modifying boot parameters); macos:unifiedlog (Modification of /System/Library/CoreServices/boot.efi).
  - AN0777 (Network Devices): Unexpected firmware image uploads via TFTP/FTP/SCP. Configuration changes modifying boot image pointers. Logs showing boot variable redirection to non-standard images. Anomalous reboots immediately following firmware changes not tied to patch schedules. Log sources: networkdevice:config (Boot variable modified to point to non-standard or unsigned image); networkdevice:firmware (Unexpected firmware image upload events via TFTP/FTP/SCP).
