# T1495 — Firmware Corruption

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Impact
- **Platforms:** Linux, macOS, Network Devices, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1495
- **Last modified:** 2026-05-12

## Description

Adversaries may overwrite or corrupt the flash memory contents of system BIOS or other firmware in devices attached to a system in order to render them inoperable or unable to boot, thus denying the availability to use the devices and/or the system. Firmware is software that is loaded and executed from non-volatile memory on hardware devices in order to initialize and manage device functionality. These devices may include the motherboard, hard drive, or video cards.

In general, adversaries may manipulate, overwrite, or corrupt firmware in order to deny the use of the system or devices. For example, corruption of firmware responsible for loading the operating system for network devices may render the network devices inoperable. Depending on the device, this attack may also result in Data Destruction.

## Mitigations

- **M1026 Privileged Account Management** — Prevent adversary access to privileged accounts or access necessary to replace system firmware.
- **M1046 Boot Integrity** — Check the integrity of the existing BIOS and device firmware to determine if it is vulnerable to modification.
- **M1051 Update Software** — Patch the BIOS and other firmware as necessary to prevent successful use of known vulnerabilities.

## Detection strategies

- **DET0167 Firmware Modification via Flash Tool or Corrupted Firmware Upload**
  - AN0474 (Windows): Firmware flash utility invoked with elevated privileges followed by raw access to firmware device path or changes to boot configuration. Log sources: WinEventLog:Security (EventCode=4688); WinEventLog:Sysmon (EventCode=6); WinEventLog:Microsoft-Windows-Kernel-Boot (Firmware integrity validation failed or boot configuration tampered).
  - AN0475 (Linux): Direct write access to /dev/mem or /sys/firmware combined with usage of firmware flashing utilities (e.g., flashrom). Log sources: auditd:SYSCALL (write access to /dev/mem or /sys/firmware/efi/efivars); auditd:SYSCALL (execution of known flash tools (e.g., flashrom, fwupd)).
  - AN0476 (macOS): EFI updates executed via system processes or binaries outside of expected patch windows or using unsigned firmware packages. Log sources: macos:unifiedlog (com.apple.firmwareupdater activity or update-firmware binary invoked); macos:unifiedlog (boot failure events or SMC validation errors).
  - AN0477 (Network Devices): Firmware image uploaded via TFTP/SCP or web interface followed by reboot or unexpected loss of connectivity. Log sources: NSM:Flow (large upload to firmware interface port or path); networkdevice:firmware (Firmware update initiated or bootloader tampering detected).

## Procedure examples

- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, adversaries performed a factory-reset on compromised devices that hampered forensic investigations.
- **S0266 TrickBot** (software) — TrickBot module "Trickboot" can write or erase the UEFI/BIOS firmware of a compromised device.
- **S0606 Bad Rabbit** (software) — Bad Rabbit has used an executable that installs a modified bootloader to prevent normal boot-up.
