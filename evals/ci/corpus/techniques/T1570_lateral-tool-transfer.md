# T1570 — Lateral Tool Transfer

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Lateral Movement
- **Platforms:** ESXi, Linux, macOS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1570
- **Last modified:** 2026-09-03

## Description

Adversaries may transfer tools or other files between systems in a compromised environment. Once brought into the victim environment (i.e., Ingress Tool Transfer) files may then be copied from one system to another to stage adversary tools or other files over the course of an operation.

Adversaries may copy files between internal victim systems to support lateral movement using inherent file sharing protocols such as file sharing over SMB/Windows Admin Shares to connected network shares or with authenticated connections via Remote Desktop Protocol.

Files can also be transferred using native or otherwise present tools on the victim system, such as scp, rsync, curl, sftp, and ftp. In some cases, adversaries may be able to leverage Web Services such as Dropbox or OneDrive to copy files from one machine to another via shared, automatically synced folders.

## Mitigations

- **M1031 Network Intrusion Prevention** — Network intrusion detection and prevention systems that use network signatures to identify traffic for specific adversary malware or unusual data transfer over known tools and protocols like FTP can be used to mitigate activity at the network level. Signatures are often for unique indicators within protocols and may be based on the specific obfuscation technique used by a particular adversary or tool, and will likely be different across various malware families and versions.
- **M1037 Filter Network Traffic** — Consider using the host firewall to restrict file sharing communications such as SMB.

## Detection strategies

- **DET0183 Detection Strategy for Lateral Tool Transfer across OS platforms**
  - AN0516 (Windows): Correlate suspicious file transfers over SMB or Admin$ shares with process creation events (e.g., cmd.exe, powershell.exe, certutil.exe) that do not align with normal administrative behavior. Detect remote file writes followed by execution of transferred binaries. Log sources: WinEventLog:Security (EventCode=5140); WinEventLog:Sysmon (EventCode=11); WinEventLog:Sysmon (EventCode=1).
  - AN0517 (Linux): Monitor scp, rsync, curl, sftp, or ftp processes initiating transfers to internal systems combined with file creation events in unusual directories. Correlate transfer activity with subsequent execution of those binaries. Log sources: auditd:SYSCALL (execve: Invocation of scp, rsync, curl, or sftp); auditd:FILE (create: New file created in system binaries or temp directories).
  - AN0518 (macOS): Detect anomalous use of scp, rsync, curl, or third-party sync apps transferring executables into user directories. Correlate new file creation with immediate execution events. Log sources: macos:unifiedlog (Execution of scp, rsync, curl with remote destination); macos:unifiedlog (File created in ~/Library/LaunchAgents or executable directories).
  - AN0519 (ESXi): Identify lateral transfer via datastore file uploads or internal scp/ssh sessions that result in new VMX/VMDK or script files. Correlate transfer with VM execution or datastore modification. Log sources: esxi:vmkernel (Upload of file to datastore); esxi:hostd (scp/ssh used to move file across hosts).

## Procedure examples

- **C0014 Operation Wocao** (campaign) — During Operation Wocao, threat actors used SMB to copy files to and from target systems.
- **C0015 C0015** (campaign) — During C0015, the threat actors used WMI to load Cobalt Strike onto additional hosts within a compromised network.
- **C0018 C0018** (campaign) — During C0018, the threat actors transferred the SoftPerfect Network Scanner and other tools to machines in the network using AnyDesk and PDQ Deploy.
- **C0025 2016 Ukraine Electric Power Attack** (campaign) — During the 2016 Ukraine Electric Power Attack, Sandworm Team used `move` to transfer files to a network share.
- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, Sandworm Team moved their tools laterally within the corporate network and between the ICS and corporate network.
- **C0034 2022 Ukraine Electric Power Attack** (campaign) — During the 2022 Ukraine Electric Power Attack, Sandworm Team used a Group Policy Object (GPO) to copy CaddyWiper's executable `msserver.exe` from a staging server to a local hard drive before deployment.
- **C0038 HomeLand Justice** (campaign) — During HomeLand Justice, threat actors initiated a process named Mellona.exe to spread the ROADSWEEP file encryptor and a persistence script to a list of internal machines.
- **C0058 SharePoint ToolShell Exploitation** (campaign) — During SharePoint ToolShell Exploitation, threat actors used Impacket to remotely stage and execute payloads via WMI.
- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, the adversaries had placed the malicious payload on an accessible network share to facilitate propagation.
- **G0010 Turla** (group) — Turla RPC backdoors can be used to transfer files to/from victim machines on the local network.
- **G0034 Sandworm Team** (group) — Sandworm Team has used `move` to transfer files to a network share and has copied payloads--such as Prestige ransomware--to an Active Directory Domain Controller and distributed via the Default Domain Group Policy Object. Additionally, Sandworm Team has transferred an ISO file into the OT network to gain initial access.
- **G0050 APT32** (group) — APT32 has deployed tools after moving laterally using administrative accounts.
- **G0051 FIN10** (group) — FIN10 has deployed Meterpreter stagers and SplinterRAT instances in the victim network after moving laterally.
- **G0059 Magic Hound** (group) — Magic Hound has copied tools within a compromised network using RDP.
- **G0093 GALLIUM** (group) — GALLIUM has used PsExec to move laterally between hosts in the target network.
- **G0096 APT41** (group) — APT41 uses remote shares to move and remotely execute payloads during lateral movemement.
- **G0102 Wizard Spider** (group) — Wizard Spider has used stolen credentials to copy tools into the `%TEMP%` directory of domain controllers.
- **G0114 Chimera** (group) — Chimera has copied tools between compromised hosts using SMB.
- **G1003 Ember Bear** (group) — Ember Bear retrieves follow-on payloads direct from adversary-owned infrastructure for deployment on compromised hosts.
- **G1007 Aoqin Dragon** (group) — Aoqin Dragon has spread malware in target networks by copying modules to folders masquerading as removable devices.
- **G1017 Volt Typhoon** (group) — Volt Typhoon has copied web shells between servers in targeted environments.
- **G1030 Agrius** (group) — Agrius downloaded some payloads for follow-on execution from legitimate filesharing services such as `ufile.io` and `easyupload.io`.
- **G1032 INC Ransom** (group) — INC Ransom has used a rapid succession of copy commands to install a file encryption executable across multiple endpoints within compromised infrastructure.
- **G1043 BlackByte** (group) — BlackByte transfered tools such as Cobalt Strike and the AnyDesk remote access tool during operations using SMB shares.
- **G1046 Storm-1811** (group) — Storm-1811 has used the Impacket toolset to move and remotely execute payloads to other hosts in victim networks.
- **G1047 Velvet Ant** (group) — Velvet Ant transferred files laterally within victim networks through the Impacket toolkit.
- **G1048 UNC3886** (group) — UNC3886 has utilzed Python scripts to transfer files between ESXi hosts and guest VMs.
- **G1051 Medusa Group** (group) — Medusa Group has utilized legitimate software services such as PDQ Deploy to transfer malicious binaries and tools to other victimized hosts within the target environment.
- **S0029 PsExec** (software) — PsExec can be used to download or upload a file over a network share.
- **S0062 DustySky** (software) — DustySky searches for network drives and removable media and duplicates itself onto them.
- **S0095 ftp** (software) — ftp may be abused by adversaries to transfer tools or files between systems within a compromised environment.
- **S0106 cmd** (software) — cmd can be used to copy files to/from a remotely connected internal system.
- **S0140 Shamoon** (software) — Shamoon attempts to copy itself to remote machines on the network.
- **S0190 BITSAdmin** (software) — BITSAdmin can be used to create BITS Jobs to upload and/or download files from SMB file servers.
- **S0357 Impacket** (software) — Impacket has used its `wmiexec` command, leveraging Windows Management Instrumentation, to remotely stage and execute payloads in victim networks.
- **S0361 Expand** (software) — Expand can be used to download or upload a file over a network share.
- **S0365 Olympic Destroyer** (software) — Olympic Destroyer attempts to copy itself to remote machines on the network.
- **S0366 WannaCry** (software) — WannaCry attempts to copy itself to remote computers after gaining access via an SMB exploit.
- **S0367 Emotet** (software) — Emotet has copied itself to remote systems using the `service.exe` filename.
- **S0372 LockerGoga** (software) — LockerGoga has been observed moving around the victim network via SMB, indicating the actors behind this ransomware are manually copying files form computer to computer instead of self-propagating.
- **S0404 esentutl** (software) — esentutl can be used to copy files to/from a remote share.
- **S0457 Netwalker** (software) — Operators deploying Netwalker have used psexec to copy the Netwalker payload across accessible systems.
- **S0532 Lucifer** (software) — Lucifer can use certutil for propagation on Windows hosts within intranets.
- **S0603 Stuxnet** (software) — Stuxnet uses an RPC server that contains a file dropping routine and support for payload version updates for P2P communications within a victim network.
- **S0698 HermeticWizard** (software) — HermeticWizard can copy files to other machines on a compromised network.
- **S1017 OutSteel** (software) — OutSteel can download the Saint Bot malware for follow-on execution.
- **S1068 BlackCat** (software) — BlackCat can replicate itself across connected servers via `psexec`.
- **S1132 IPsec Helper** (software) — IPsec Helper can download additional payloads from command and control nodes and execute them.
- **S1139 INC Ransomware** (software) — INC Ransomware can push its encryption executable to multiple endpoints within compromised infrastructure.
- **S1180 BlackByte Ransomware** (software) — BlackByte Ransomware spreads itself laterally by writing the JavaScript launcher file to mapped shared folders.
- **S1217 VIRTUALPITA** (software) — VIRTUALPITA is capable of file transfer and arbitrary command execution.
- **S1218 VIRTUALPIE** (software) — VIRTUALPIE has file transfer capabilities.
- **S1229 Havoc** (software) — Havoc has the ability to copy files from one location to another.
- **S1242 Qilin** (software) — Qilin has used PsExec to distribute a second encryptor, named encryptor_1.exe, across the targeted environment.
- **S9030 SameCoin** (software) — SameCoin can copy its wiper executable to remote machines within the same Active Directory.
