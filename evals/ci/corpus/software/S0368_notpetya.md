# S0368 — NotPetya

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Also known as:** ExPetr, Diskcoder.C, GoldenEye, Petrwrap, Nyetya
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0368
- **Last modified:** 2025-04-16

## Description

NotPetya is malware that was used by Sandworm Team in a worldwide attack starting on June 27, 2017. While NotPetya appears as a form of ransomware, its main purpose was to destroy data and disk structures on compromised systems; the attackers never intended to make the encrypted data recoverable. As such, NotPetya may be more appropriately thought of as a form of wiper malware. NotPetya contains worm-like features to spread itself across a computer network using the SMBv1 exploits EternalBlue and EternalRomance.

## Techniques used

- **T0828 Loss of Productivity and Revenue** — NotPetya disrupted manufacturing facilities supplying vaccines, resulting in a halt of production and the inability to meet demand for specific vaccines.
- **T0866 Exploitation of Remote Services** — NotPetya initially infected IT networks, but by means of an exploit (particularly the SMBv1-targeting MS17-010 vulnerability) spread to industrial networks.
- **T0867 Lateral Tool Transfer** — NotPetya can move laterally through industrial networks by means of the SMB service.
- **T1003.001 OS Credential Dumping: LSASS Memory** — NotPetya contains a modified version of Mimikatz to help gather credentials that are later used for lateral movement.
- **T1021.002 Remote Services: SMB/Windows Admin Shares** — NotPetya can use PsExec, which interacts with the `ADMIN$` network share to execute commands on remote systems.
- **T1036 Masquerading** — NotPetya drops PsExec with the filename dllhost.dat.
- **T1047 Windows Management Instrumentation** — NotPetya can use `wmic` to help propagate itself across a network.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — NotPetya creates a task to reboot the system one hour after infection.
- **T1078.003 Valid Accounts: Local Accounts** — NotPetya can use valid credentials with PsExec or `wmic` to spread itself to remote systems.
- **T1083 File and Directory Discovery** — NotPetya searches for files ending with dozens of different file extensions prior to encryption.
- **T1210 Exploitation of Remote Services** — NotPetya can use two exploits in SMBv1, EternalBlue and EternalRomance, to spread itself to other remote systems on the network.
- **T1218.011 System Binary Proxy Execution: Rundll32** — NotPetya uses `rundll32.exe` to install itself on remote systems when accessed via PsExec or `wmic`.
- **T1486 Data Encrypted for Impact** — NotPetya encrypts user files and disk structures like the MBR with 2048-bit RSA.
- **T1518.001 Software Discovery: Security Software Discovery** — NotPetya determines if specific antivirus programs are running on an infected host machine.
- **T1529 System Shutdown/Reboot** — NotPetya will reboot the system one hour after infection.
- **T1569.002 System Services: Service Execution** — NotPetya can use PsExec to help propagate itself across a network.
- **T1685.005 Disable or Modify Tools: Clear Windows Event Logs** — NotPetya uses `wevtutil` to clear the Windows event logs.

## Used by

- **G0034 Sandworm Team** (group)
