# T1018 — Remote System Discovery

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Discovery
- **Platforms:** ESXi, Linux, macOS, Network Devices, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1018
- **Last modified:** 2026-05-12

## Description

Adversaries may attempt to get a listing of other systems by IP address, hostname, or other logical identifier on a network that may be used for Lateral Movement from the current system. Functionality could exist within remote access tools to enable this, but utilities available on the operating system could also be used such as Ping, `net view` using Net, or, on ESXi servers, `esxcli network diag ping`.

Adversaries may also analyze data from local host files (ex: `C:\Windows\System32\Drivers\etc\hosts` or `/etc/hosts`) or other passive means (such as local Arp cache entries) in order to discover the presence of remote systems in an environment.

Adversaries may also target discovery of network infrastructure as well as leverage Network Device CLI commands on network devices to gather detailed information about systems within a network (e.g. `show cdp neighbors`, `show arp`).

## Detection strategies

- **DET0574 Detection Strategy for Remote System Enumeration Behavior**
  - AN1583 (Windows): Execution of network enumeration utilities (e.g., net.exe, ping.exe, tracert.exe) in short succession, often chained with lateral movement tools or system enumeration commands. Log sources: WinEventLog:Sysmon (EventCode=1); WinEventLog:Sysmon (EventCode=3, 22).
  - AN1584 (Linux): Use of bash scripts or interactive shells to issue sequential ping, arp, or traceroute commands to map remote hosts. Log sources: auditd:EXECVE (execve); linux:syslog (network).
  - AN1585 (macOS): Execution of built-in or AppleScript-based system enumeration via `arp`, `netstat`, `ping`, and discovery of `/etc/hosts` contents. Log sources: macos:unifiedlog (process); macos:osquery (file_events).
  - AN1586 (ESXi): ESXi shell or SSH access issuing `esxcli network diag ping` or viewing routing tables to identify connected hosts. Log sources: esxi:hostd (None).
  - AN1587 (Network Devices): Execution of discovery commands like `show cdp neighbors`, `show arp`, and other interface-level introspection on Cisco or Juniper devices. Log sources: networkdevice:syslog (syslog facility LOCAL7 or trap messages).

## Procedure examples

- **C0007 FunnyDream** (campaign) — During FunnyDream, the threat actors used several tools and batch files to map victims' internal networks.
- **C0012 Operation CuckooBees** (campaign) — During Operation CuckooBees, the threat actors used the `net view` and `ping` commands as part of their advanced reconnaissance.
- **C0014 Operation Wocao** (campaign) — During Operation Wocao, threat actors used `nbtscan` and `ping` to discover remote systems, as well as `dsquery subnet` on a domain controller to retrieve all subnets in the Active Directory.
- **C0015 C0015** (campaign) — During C0015, the threat actors used the commands `net view /all /domain` and `ping` to discover remote systems. They also used PowerView's PowerShell Invoke-ShareFinder script for file share enumeration.
- **C0024 SolarWinds Compromise** (campaign) — During the SolarWinds Compromise, APT29 used AdFind to enumerate remote systems.
- **C0025 2016 Ukraine Electric Power Attack** (campaign) — During the 2016 Ukraine Electric Power Attack, Sandworm Team checked for connectivity to resources within the network and used LDAP to query Active Directory, discovering information about computers listed in AD.
- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, Sandworm Team remotely discovered systems over LAN connections. OT systems were visible from the IT network as well, giving adversaries the ability to discover operational assets.
- **C0049 Leviathan Australian Intrusions** (campaign) — Leviathan performed extensive remote host enumeration to build their own map of victim networks during Leviathan Australian Intrusions.
- **C0061 Operation Digital Eye** (campaign) — During Operation Digital Eye, threat actors used Ping for reconnaissance.
- **C0064 AI-Assisted Breach of Mexico's Government Infrastructure** (campaign) — During the AI-Assisted Breach of Mexico's Government Infrastructure, the adversary used Claude Code to request BACKUPOSINT v9.0 APEX PREDATOR to perform remote system discovery mapping harvested credentials to systems within the victim environment. During the AI-Assisted Breach of Mexico's Government Infrastructure, the adversary tasked Claude Code with enumerating additional lateral movement targets which included the discovery of a vNode industrial gateway and Supervisory Control and Data Acquisition (SCADA)/Industrial Internet of Things (IIoT) management platform.
- **G0004 Ke3chang** (group) — Ke3chang has used network scanning and enumeration tools, including Ping.
- **G0009 Deep Panda** (group) — Deep Panda has used ping to identify other machines of interest.
- **G0010 Turla** (group) — Turla surveys a system upon check-in to discover remote systems on a local network using the `net view` and `net view /DOMAIN` commands. Turla has also used `net group "Domain Computers" /domain`, `net group "Domain Controllers" /domain`, and `net group "Exchange Servers" /domain` to enumerate domain computers, including the organization's DC and Exchange Server.
- **G0019 Naikon** (group) — Naikon has used a netbios scanner for remote machine identification.
- **G0022 APT3** (group) — APT3 has a tool that can detect the existence of remote systems.
- **G0027 Threat Group-3390** (group) — Threat Group-3390 has used the `net view` command.
- **G0030 Lotus Blossom** (group) — Lotus Blossom has used Ping to identify remote systems.
- **G0034 Sandworm Team** (group) — Sandworm Team has used a tool to query Active Directory using LDAP, discovering information about computers listed in AD.
- **G0035 Dragonfly** (group) — Dragonfly has likely obtained a list of hosts in the victim environment.
- **G0037 FIN6** (group) — FIN6 used publicly available tools (including Microsoft's built-in SQL querying tool, osql.exe) to map the internal network and conduct reconnaissance against Active Directory, Structured Query Language (SQL) servers, and NetBIOS.
- **G0045 menuPass** (group) — menuPass uses scripts to enumerate IP ranges on the victim network. menuPass has also issued the command `net view /domain` to a PlugX implant to gather information about remote systems on the network.
- **G0050 APT32** (group) — APT32 has enumerated DC servers using the command `net group "Domain Controllers" /domain`. The group has also used the `ping` command.
- **G0053 FIN5** (group) — FIN5 has used the open source tool Essential NetTools to map the network and build a list of targets.
- **G0059 Magic Hound** (group) — Magic Hound has used Ping for discovery on targeted networks.
- **G0060 BRONZE BUTLER** (group) — BRONZE BUTLER typically use `ping` and Net to enumerate systems.
- **G0061 FIN8** (group) — FIN8 has used dsquery and other Active Directory utilities to enumerate hosts; they have also used `nltest.exe /dclist` to retrieve a list of domain controllers.
- **G0077 Leafminer** (group) — Leafminer used Microsoft’s Sysinternals tools to gather detailed information about remote systems.
- **G0087 APT39** (group) — APT39 has used NBTscan and custom tools to discover remote systems.
- **G0091 Silence** (group) — Silence has used Nmap to scan the corporate network, build a network topology, and identify vulnerable hosts.
- **G0093 GALLIUM** (group) — GALLIUM used a modified version of NBTscan to identify available NetBIOS name servers over the network as well as `ping` to identify remote systems.
- **G0096 APT41** (group) — APT41 has used MiPing to discover active systems in the victim network.
- **G0102 Wizard Spider** (group) — Wizard Spider has used networkdll for network discovery and psfin specifically for financial and point of sale indicators. Wizard Spider has also used AdFind, `nltest/dclist`, and PowerShell script Get-DataInfo.ps1 to enumerate domain computers, including the domain controller.
- **G0106 Rocke** (group) — Rocke has looked for IP addresses in the known_hosts file on the infected system and attempted to SSH into them.
- **G0114 Chimera** (group) — Chimera has utilized various scans and queries to find domain controllers and remote services in the target environment.
- **G0117 Fox Kitten** (group) — Fox Kitten has used Angry IP Scanner to detect remote systems.
- **G0119 Indrik Spider** (group) — Indrik Spider has used PowerView to enumerate all Windows Server, Windows Server 2003, and Windows 7 instances in the Active Directory database.
- **G0125 HAFNIUM** (group) — HAFNIUM has enumerated domain controllers using `net group "Domain computers"` and `nltest /dclist`.
- **G0129 Mustang Panda** (group) — Mustang Panda has queried Active Directory for computers using AdFind. Mustang Panda has also utilized SharpNBTScan to scan the victim environment.
- **G1001 HEXANE** (group) — HEXANE has used `net view` to enumerate domain machines.
- **G1003 Ember Bear** (group) — Ember Bear has used tools such as Nmap and MASSCAN for remote service discovery.
- **G1006 Earth Lusca** (group) — Earth Lusca used the command `powershell “Get-EventLog -LogName security -Newest 500 | where {$_.EventID -eq 4624} | format-list - property * | findstr “Address””` to find the network information of successfully logged-in accounts to discovery addresses of other machines. Earth Lusca has also used multiple scanning tools to discover other machines within the same compromised network.
- **G1015 Scattered Spider** (group) — Scattered Spider can enumerate remote systems, such as VMware vCenter infrastructure.
- **G1017 Volt Typhoon** (group) — Volt Typhoon has used multiple methods, including Ping, to enumerate systems on compromised networks.
- **G1022 ToddyCat** (group) — ToddyCat has used `ping %REMOTE_HOST%` for post exploit discovery.
- **G1024 Akira** (group) — Akira uses software such as Advanced IP Scanner and MASSCAN to identify remote hosts within victim networks.
- **G1030 Agrius** (group) — Agrius used the tool NBTscan to scan for remote, accessible hosts in victim environments.
- **G1040 Play** (group) — Play has used tools such as AdFind, Nltest, and BloodHound to enumerate shares and hostnames on compromised networks.
- **G1043 BlackByte** (group) — BlackByte used tools such as Arp to identify remotely-connected devices.
- **G1045 Salt Typhoon** (group) — Salt Typhoon has used SNMPwalk to enumerate devices.
- **G1051 Medusa Group** (group) — Medusa Group has used PDQ Inventory to get an inventory of the endpoints on the network.
- **G1054 MirrorFace** (group) — MirrorFace has used Ping for system discovery.
- **G1057 ShinyHunters** (group) — ShinyHunters has enumerated the internal subnet using ` cat /etc/hosts | grep -E "[redacted_victim_string]"`.
- **G1058 The Gentlemen** (group) — The Gentlemen has utilized internal network scanning tools to enumerate additional hosts in the victim environment to include Advanced IP Scanner.
- **S0018 Sykipot** (software) — Sykipot may use `net view /domain` to display hostnames of available systems on a network.
- **S0039 Net** (software) — Commands such as `net view` can be used in Net to gather information about available remote systems.
- **S0063 SHOTPUT** (software) — SHOTPUT has a command to list all servers in the domain, as well as one to locate domain controllers on a domain.
- **S0091 Epic** (software) — Epic uses the `net view` command on the victim’s machine.
- **S0093 Backdoor.Oldrea** (software) — Backdoor.Oldrea can enumerate and map ICS-specific systems in victim environments.
- **S0097 Ping** (software) — Ping can be used to identify remote systems within a network.
- **S0099 Arp** (software) — Arp can be used to display a host's ARP cache, which may include address resolutions for remote systems.
- **S0125 Remsec** (software) — Remsec can ping or traceroute a remote host.
- **S0140 Shamoon** (software) — Shamoon scans the C-class subnet of the IPs on the victim's interfaces.
- **S0154 Cobalt Strike** (software) — Cobalt Strike uses the native Windows Network Enumeration APIs to interrogate and discover targets in a Windows Active Directory network.
- **S0165 OSInfo** (software) — OSInfo performs a connection test to discover remote systems in the network
- **S0233 MURKYTOP** (software) — MURKYTOP has the capability to identify remote hosts on connected networks.
- **S0236 Kwampirs** (software) — Kwampirs collects a list of available servers with the command `net view`.
- **S0241 RATANKBA** (software) — RATANKBA runs the `net view /domain` and `net view` commands.
- **S0244 Comnie** (software) — Comnie runs the `net view` command
- **S0248 yty** (software) — yty uses the `net view` command for discovery.
- **S0266 TrickBot** (software) — TrickBot can enumerate computers and network devices.
- **S0335 Carbon** (software) — Carbon uses the `net view` command.
- **S0359 Nltest** (software) — Nltest may be used to enumerate remote domain controllers using options such as `/dclist` and `/dsgetdc`.
- **S0365 Olympic Destroyer** (software) — Olympic Destroyer uses Windows Management Instrumentation to enumerate all systems in the network.
- **S0366 WannaCry** (software) — WannaCry scans its local network segment for remote systems to try to exploit and copy itself to.
- **S0385 njRAT** (software) — njRAT can identify remote hosts on connected networks.
- **S0428 PoetRAT** (software) — PoetRAT used Nmap for remote system discovery.
- **S0452 USBferry** (software) — USBferry can use `net view` to gather information about remote systems.
- **S0488 CrackMapExec** (software) — CrackMapExec can discover active IP addresses, along with the machine name, within a targeted network.
- **S0521 BloodHound** (software) — BloodHound can enumerate and collect the properties of domain computers, including domain controllers.
- **S0534 Bazar** (software) — Bazar can enumerate remote systems using ` Net View`.
- **S0552 AdFind** (software) — AdFind has the ability to query Active Directory for computers.
- **S0570 BitPaymer** (software) — BitPaymer can use `net view` to discover remote systems.
- **S0575 Conti** (software) — Conti has the ability to discover hosts on a target network.
- **S0586 TAINTEDSCRIBE** (software) — The TAINTEDSCRIBE command and execution module can perform target system enumeration.
- **S0590 NBTscan** (software) — NBTscan can list NetBIOS computer names.
- **S0599 Kinsing** (software) — Kinsing has used a script to parse files like `/etc/hosts` and SSH `known_hosts` to discover remote systems.
- **S0604 Industroyer** (software) — Industroyer can enumerate remote computers in the compromised network.
- **S0646 SpicyOmelette** (software) — SpicyOmelette can identify payment systems, payment gateways, and ATM systems in compromised environments.
- **S0650 QakBot** (software) — QakBot can identify remote systems through the `net view` command.
- **S0659 Diavol** (software) — Diavol can use the ARP table to find remote hosts to scan.
- **S0684 ROADTools** (software) — ROADTools can enumerate Azure AD systems and devices.
- **S0692 SILENTTRINITY** (software) — SILENTTRINITY can enumerate and collect the properties of domain computers.
- **S0694 DRATzarus** (software) — DRATzarus can search for other machines connected to compromised host and attempt to map the network.
- **S0696 Flagpro** (software) — Flagpro has been used to execute `net view` on a targeted system.
- **S0698 HermeticWizard** (software) — HermeticWizard can find machines on the local network by gathering known local IP addresses through `DNSGetCacheDataTable`, `GetIpNetTable`,`WNetOpenEnumW(RESOURCE_GLOBALNET, RESOURCETYPE_ANY)`,`NetServerEnum`,`GetTcpTable`, and `GetAdaptersAddresses.`
- **S1044 FunnyDream** (software) — FunnyDream can collect information about hosts on the victim network.
- **S1068 BlackCat** (software) — BlackCat can broadcasts NetBIOS Name Service (NBNC) messages to search for servers connected to compromised networks.
- **S1070 Black Basta** (software) — Black Basta can use LDAP queries to connect to AD and iterate over connected workstations.
- **S1081 BADHATCH** (software) — BADHATCH can use a PowerShell object such as, `System.Net.NetworkInformation.Ping` to ping a computer.
- **S1146 MgBot** (software) — MgBot includes modules for performing ARP scans of local connected systems.
- **S1159 DUSTTRAP** (software) — DUSTTRAP can use `ping` to identify remote hosts within the victim network.
- **S1198 Gomir** (software) — Gomir probes arbitrary network endpoints for TCP connectivity.
- **S1212 RansomHub** (software) — RansomHub can enumerate all accessible machines from the infected system.
- **S1229 Havoc** (software) — Havoc features a module capable of host enumeration.
- **S1242 Qilin** (software) — Qilin can enumerate domain-connected hosts during its discovery phase.
- **S9020 LODEINFO** (software) — LODEINFO can run `net view` and `net view /domain` for network discovery.
- **S9042 CanisterWorm** (software) — CanisterWorm has scanned the local /24 subnet for new targets.
- **S9045 BACKUPOSINT v9.0 APEX PREDATOR** (software) — BACKUPOSINT v9.0 APEX PREDATOR has performed remote system discovery mapping harvested credentials to systems within the target environment.
