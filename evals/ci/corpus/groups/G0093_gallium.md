# G0093 — GALLIUM

- **Type:** group
- **Domain:** Enterprise ATT&CK
- **Also known as:** Granite Typhoon
- **ATT&CK URL:** https://attack.mitre.org/groups/G0093
- **Last modified:** 2026-07-31

## Description

GALLIUM is a cyberespionage group that has been active since at least 2012, primarily targeting telecommunications companies, financial institutions, and government entities in Afghanistan, Australia, Belgium, Cambodia, Malaysia, Mozambique, the Philippines, Russia, and Vietnam. This group is particularly known for launching Operation Soft Cell, a long-term campaign targeting telecommunications providers. Security researchers have identified GALLIUM as a likely Chinese state-sponsored group, based in part on tools used and TTPs commonly associated with Chinese threat actors.

## Techniques used

- **T1003.001 OS Credential Dumping: LSASS Memory** — GALLIUM used a modified version of Mimikatz along with a PowerShell-based Mimikatz to dump credentials on the victim machines.
- **T1003.002 OS Credential Dumping: Security Account Manager** — GALLIUM used `reg` commands to dump specific hives from the Windows Registry, such as the SAM hive, and obtain password hashes.
- **T1005 Data from Local System** — GALLIUM collected data from the victim's local system, including password hashes from the SAM hive in the Registry.
- **T1016 System Network Configuration Discovery** — GALLIUM used `ipconfig /all` to obtain information about the victim network configuration. The group also ran a modified version of NBTscan to identify available NetBIOS name servers.
- **T1018 Remote System Discovery** — GALLIUM used a modified version of NBTscan to identify available NetBIOS name servers over the network as well as `ping` to identify remote systems.
- **T1027 Obfuscated Files or Information** — GALLIUM used a modified version of HTRAN in which they obfuscated strings such as debug messages in an apparent attempt to evade detection.
- **T1027.002 Obfuscated Files or Information: Software Packing** — GALLIUM packed some payloads using different types of packers, both known and custom.
- **T1027.005 Obfuscated Files or Information: Indicator Removal from Tools** — GALLIUM ensured each payload had a unique hash, including by using different types of packers.
- **T1033 System Owner/User Discovery** — GALLIUM used `whoami` and `query user` to obtain information about the victim user.
- **T1036.003 Masquerading: Rename Legitimate Utilities** — GALLIUM used a renamed cmd.exe file to evade detection.
- **T1041 Exfiltration Over C2 Channel** — GALLIUM used Web shells and HTRAN for C2 and to exfiltrate data.
- **T1047 Windows Management Instrumentation** — GALLIUM used WMI for execution to assist in lateral movement as well as for installing tools across multiple assets.
- **T1049 System Network Connections Discovery** — GALLIUM used `netstat -oan` to obtain information about the victim network connections.
- **T1053.005 Scheduled Task/Job: Scheduled Task** — GALLIUM established persistence for PoisonIvy by created a scheduled task.
- **T1059.001 Command and Scripting Interpreter: PowerShell** — GALLIUM used PowerShell for execution to assist in lateral movement as well as for dumping credentials stored on compromised machines.
- **T1059.003 Command and Scripting Interpreter: Windows Command Shell** — GALLIUM used the Windows command shell to execute commands.
- **T1074.001 Data Staged: Local Data Staging** — GALLIUM compressed and staged files in multi-part archives in the Recycle Bin prior to exfiltration.
- **T1078 Valid Accounts** — GALLIUM leveraged valid accounts to maintain access to a victim network.
- **T1090.002 Proxy: External Proxy** — GALLIUM used a modified version of HTRAN to redirect connections between networks.
- **T1105 Ingress Tool Transfer** — GALLIUM dropped additional tools to victims during their operation, including portqry.exe, a renamed cmd.exe file, winrar, and HTRAN.
- **T1133 External Remote Services** — GALLIUM has used VPN services, including SoftEther VPN, to access and maintain persistence in victim environments.
- **T1136.002 Create Account: Domain Account** — GALLIUM created high-privileged domain user accounts to maintain access to victim networks.
- **T1190 Exploit Public-Facing Application** — GALLIUM exploited a publicly-facing servers including Wildfly/JBoss servers to gain access to the network.
- **T1505.003 Server Software Component: Web Shell** — GALLIUM used Web shells to persist in victim environments and assist in execution and exfiltration.
- **T1550.002 Use Alternate Authentication Material: Pass the Hash** — GALLIUM used dumped hashes to authenticate to other machines via pass the hash.
- **T1553.002 Subvert Trust Controls: Code Signing** — GALLIUM has used stolen certificates to sign its tools including those from Whizzimo LLC.
- **T1560.001 Archive Collected Data: Archive via Utility** — GALLIUM used WinRAR to compress and encrypt stolen data prior to exfiltration.
- **T1570 Lateral Tool Transfer** — GALLIUM has used PsExec to move laterally between hosts in the target network.
- **T1574.001 Hijack Execution Flow: DLL** — GALLIUM used DLL side-loading to covertly load PoisonIvy into memory on the victim machine.
- **T1583.004 Acquire Infrastructure: Server** — GALLIUM has used Taiwan-based servers that appear to be exclusive to GALLIUM.
- **T1588.002 Obtain Capabilities: Tool** — GALLIUM has used a variety of widely-available tools, which in some cases they modified to add functionality and/or subvert antimalware solutions.

## Software used

- **S0002 Mimikatz**
- **S0005 Windows Credential Editor**
- **S0012 PoisonIvy**
- **S0013 PlugX**
- **S0020 China Chopper**
- **S0029 PsExec**
- **S0039 Net**
- **S0040 HTRAN**
- **S0075 Reg**
- **S0097 Ping**
- **S0100 ipconfig**
- **S0106 cmd**
- **S0110 at**
- **S0564 BlackMould**
- **S0590 NBTscan**
- **S1031 PingPull**
