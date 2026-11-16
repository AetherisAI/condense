# S0607 — KillDisk

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Also known as:** Win32/KillDisk.NBI, Win32/KillDisk.NBH, Win32/KillDisk.NBD, Win32/KillDisk.NBC, Win32/KillDisk.NBB
- **Platforms:** Linux, Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0607
- **Last modified:** 2023-10-06

## Description

KillDisk is a disk-wiping tool designed to overwrite files with random data to render the OS unbootable. It was first observed as a component of BlackEnergy malware during cyber attacks against Ukraine in 2015. KillDisk has since evolved into stand-alone malware used by a variety of threat actors against additional targets in Europe and Latin America; in 2016 a ransomware component was also incorporated into some KillDisk variants.

## Techniques used

- **T0809 Data Destruction** — KillDisk is able to delete system files to make the system unbootable and targets 35 different types of files for deletion.
- **T0829 Loss of View** — KillDisk erases the master boot record (MBR) and system logs, leaving the system unusable.
- **T0872 Indicator Removal on Host** — KillDisk deletes application, security, setup, and system event logs from Windows systems.
- **T0881 Service Stop** — KillDisk looks for and terminates two non-standard processes, one of which is an ICS application.
- **T1027 Obfuscated Files or Information** — KillDisk uses VMProtect to make reverse engineering the malware more difficult.
- **T1036.004 Masquerading: Masquerade Task or Service** — KillDisk registers as a service under the Plug-And-Play Support name.
- **T1057 Process Discovery** — KillDisk has called `GetCurrentProcess`.
- **T1070.004 Indicator Removal: File Deletion** — KillDisk has the ability to quit and delete itself.
- **T1083 File and Directory Discovery** — KillDisk has used the `FindNextFile` command as part of its file deletion process.
- **T1106 Native API** — KillDisk has called the Windows API to retrieve the hard disk handle and shut down the machine.
- **T1129 Shared Modules** — KillDisk loads and executes functions from a DLL.
- **T1134 Access Token Manipulation** — KillDisk has attempted to get the access token of a process by calling `OpenProcessToken`. If KillDisk gets the access token, then it attempt to modify the token privileges with `AdjustTokenPrivileges`.
- **T1485 Data Destruction** — KillDisk deletes system files to make the OS unbootable. KillDisk also targets and deletes files with 35 different file extensions.
- **T1486 Data Encrypted for Impact** — KillDisk has a ransomware component that encrypts files with an AES key that is also RSA-1028 encrypted.
- **T1489 Service Stop** — KillDisk terminates various processes to get the user to reboot the victim machine.
- **T1529 System Shutdown/Reboot** — KillDisk attempts to reboot the machine by terminating specific processes.
- **T1561.002 Disk Wipe: Disk Structure Wipe** — KillDisk overwrites the first sector of the Master Boot Record with “0x00”.
- **T1680 Local Storage Discovery** — KillDisk retrieves the hard disk name by calling the `CreateFileA to \\.\PHYSICALDRIVE0` API.
- **T1685.005 Disable or Modify Tools: Clear Windows Event Logs** — KillDisk deletes Application, Security, Setup, and System Windows Event Logs.

## Used by

- **C0028 2015 Ukraine Electric Power Attack** (campaign)
- **G0034 Sandworm Team** (group)
- **G0082 APT38** (group)
