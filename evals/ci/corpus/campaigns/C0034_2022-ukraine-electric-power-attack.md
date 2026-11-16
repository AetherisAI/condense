# C0034 — 2022 Ukraine Electric Power Attack

- **Type:** campaign
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **First seen:** 2022-06-01
- **Last seen:** 2022-10-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0034
- **Last modified:** 2026-07-31

## Description

The 2022 Ukraine Electric Power Attack was a Sandworm Team campaign that used a combination of GOGETTER, Neo-REGEORG, CaddyWiper, and living of the land (LotL) techniques to gain access to a Ukrainian electric utility to send unauthorized commands from their SCADA system.

## Techniques used

- **T0894 System Binary Proxy Execution** — During the 2022 Ukraine Electric Power Attack, Sandworm Team executed a MicroSCADA application binary `scilc.exe` to send a predefined list of SCADA instructions specified in a file defined by the adversary, `s1.txt`. The executed command `C:\sc\prog\exec\scilc.exe -do pack\scil\s1.txt` leverages the SCADA software to send unauthorized command messages to remote substations.
- **T0895 Autorun Image** — During the 2022 Ukraine Electric Power Attack, Sandworm Team used existing hypervisor access to map an ISO image named `a.iso` to a virtual machine running a SCADA server. The SCADA server’s operating system was configured to autorun CD-ROM images, and as a result, a malicious VBS script on the ISO image was automatically executed.
- **T1036.004 Masquerading: Masquerade Task or Service** — During the 2022 Ukraine Electric Power Attack, Sandworm Team leveraged Systemd service units to masquerade GOGETTER malware as legitimate or seemingly legitimate services.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — During the 2022 Ukraine Electric Power Attack, Sandworm Team leveraged Scheduled Tasks through a Group Policy Object (GPO) to execute CaddyWiper at a predetermined time.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — During the 2022 Ukraine Electric Power Attack, Sandworm Team utilized a PowerShell utility called TANKTRAP to spread and launch a wiper using Windows Group Policy.
- **T1095 Non-Application Layer Protocol** — During the 2022 Ukraine Electric Power Attack, Sandworm Team proxied C2 communications within a TLS-based tunnel.
- **T1484.001 Domain or Tenant Policy Modification: Group Policy Modification** — During the 2022 Ukraine Electric Power Attack, Sandworm Team leveraged Group Policy Objects (GPOs) to deploy and execute malware.
- **T1485 Data Destruction** — During the 2022 Ukraine Electric Power Attack, Sandworm Team deployed CaddyWiper on the victim’s IT environment systems to wipe files related to the OT capabilities, along with mapped drives, and physical drive partitions.
- **T1505.003 Server Software Component: Web Shell** — During the 2022 Ukraine Electric Power Attack, Sandworm Team deployed the Neo-REGEORG webshell on an internet-facing server.
- **T1543.002 Create or Modify System Process: Systemd Service** — During the 2022 Ukraine Electric Power Attack, Sandworm Team configured Systemd to maintain persistence of GOGETTER, specifying the `WantedBy=multi-user.target` configuration to run GOGETTER when the system begins accepting user logins.
- **T1570 Lateral Tool Transfer** — During the 2022 Ukraine Electric Power Attack, Sandworm Team used a Group Policy Object (GPO) to copy CaddyWiper's executable `msserver.exe` from a staging server to a local hard drive before deployment.
- **T1572 Protocol Tunneling** — During the 2022 Ukraine Electric Power Attack, Sandworm Team deployed the GOGETTER tunneler software to establish a “Yamux” TLS-based C2 channel with an external server(s).
- **T1692.001 Unauthorized Message: Command Message** — During the 2022 Ukraine Electric Power Attack, Sandworm Team used the MicroSCADA SCIL-API to specify a set of SCADA instructions, including the sending of unauthorized commands to substation devices.
- **T1701.002 Command and Scripting Interpreter: Windows Command Shell** — During the 2022 Ukraine Electric Power Attack, Sandworm Team utilizes a Visual Basic script `lun.vbs` to execute `n.bat` which then executed the MicroSCADA `scilc.exe` command.
- **T1701.004 Command and Scripting Interpreter: Visual Basic** — During the 2022 Ukraine Electric Power Attack, Sandworm Team utilizes a Visual Basic script `lun.vbs` to execute `n.bat` which then executed the MicroSCADA `scilc.exe` command.

## Software used

- **S0693 CaddyWiper**

## Attributed to

- **G0034 Sandworm Team**
