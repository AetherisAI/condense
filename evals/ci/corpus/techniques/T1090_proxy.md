# T1090 — Proxy

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Command and Control
- **Platforms:** ESXi, Linux, macOS, Network Devices, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1090
- **Last modified:** 2026-09-08

## Description

Adversaries may use a connection proxy to direct network traffic between systems or act as an intermediary for network communications to a command and control server to avoid direct connections to their infrastructure. Many tools exist that enable traffic redirection through proxies or port redirection, including HTRAN, ZXProxy, and ZXPortMap. Adversaries use these types of proxies to manage command and control communications, reduce the number of simultaneous outbound network connections, provide resiliency in the face of connection loss, or to ride over existing trusted communications paths between victims to avoid suspicion. Adversaries may chain together multiple proxies to further disguise the source of malicious traffic.

Adversaries can also take advantage of routing schemes in Content Delivery Networks (CDNs) to proxy command and control traffic.

## Sub-techniques

- **T1090.001 Proxy: Internal Proxy**
- **T1090.002 Proxy: External Proxy**
- **T1090.003 Proxy: Multi-hop Proxy**
- **T1090.004 Proxy: Domain Fronting**

## Mitigations

- **M1020 SSL/TLS Inspection** — If it is possible to inspect HTTPS traffic, the captures can be analyzed for connections that appear to be domain fronting.
- **M1031 Network Intrusion Prevention** — Network intrusion detection and prevention systems that use network signatures to identify traffic for specific adversary malware can be used to mitigate activity at the network level. Signatures are often for unique indicators within protocols and may be based on the specific C2 protocol used by a particular adversary or tool, and will likely be different across various malware families and versions. Adversaries will likely change tool C2 signatures over time or construct protocols in such a way as to avoid detection by common defensive tools.
- **M1037 Filter Network Traffic** — Traffic to known anonymity networks and C2 infrastructure can be blocked through the use of network allow and block lists. It should be noted that this kind of blocking may be circumvented by other techniques like Domain Fronting.

## Detection strategies

- **DET0445 Detection of Proxy Infrastructure Setup and Traffic Bridging**
  - AN1229 (Windows): Suspicious process spawning (e.g., `rundll32`, `svchost`, `powershell`, or `netsh`) followed by network connection creation to internal hosts or uncommon external endpoints on high or non-standard ports. Log sources: WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Sysmon (EventCode=1); NSM:Connections (Outbound Connection).
  - AN1230 (Linux): User-space tools (e.g., `socat`, `ncat`, `iptables`, `ssh`) used in non-standard ways to establish reverse shells, port-forwarding, or inter-host connections. Often chained with uncommon outbound destinations or SSH tunnels. Log sources: auditd:SYSCALL (execve); NSM:Flow (Connection Tracking).
  - AN1231 (macOS): AppleScript, LaunchAgents, or remote login services (`ssh`, `networksetup`) establishing proxy tunnels or dynamic port forwards to external IPs or alternate local hosts. Log sources: macos:unifiedlog (None); NSM:Firewall (pf firewall logs); NSM:Flow (connection attempts).
  - AN1232 (ESXi): Direct use of `nc`, `socat`, or reverse tunnel scripts initiated by abnormal user contexts or unauthorized VIBs initiating connections from hypervisor to external systems. Log sources: esxi:shell (None); esxi:vmkernel (None); NSM:Flow (conn.log).
  - AN1233 (Network Devices): Dynamic or static port forwarding rules added to route traffic through an internal host, or configuration changes to proxy firewall rules not aligned with baselined policy. Log sources: NSM:Firewall (Policy Change / Rule Update); NSM:Flow (Flow Creation (NetFlow/sFlow)); networkdevice:cli (Interface commands).

## Procedure examples

- **C0013 Operation Sharpshooter** (campaign) — For Operation Sharpshooter, the threat actors used the ExpressVPN service to hide their location.
- **C0014 Operation Wocao** (campaign) — During Operation Wocao, threat actors used a custom proxy tool called "Agent" which has support for multiple hops.
- **C0017 C0017** (campaign) — During C0017, APT41 used the Cloudflare CDN to proxy C2 traffic.
- **C0027 C0027** (campaign) — During C0027, Scattered Spider installed the open-source rsocx reverse proxy tool on a targeted ESXi appliance.
- **C0047 RedDelta Modified PlugX Infection Chain Operations** (campaign) — Mustang Panda proxied communication through the Cloudflare CDN service during RedDelta Modified PlugX Infection Chain Operations.
- **C0048 Operation MidnightEclipse** (campaign) — During Operation MidnightEclipse, threat actors used the GO Simple Tunnel reverse proxy tool.
- **C0056 RedPenguin** (campaign) — During RedPenguin, UNC3886 used malware capable of establishing a SOCKS proxy connection to a specified IP and port.
- **C0058 SharePoint ToolShell Exploitation** (campaign) — During SharePoint ToolShell Exploitation, threat actors used Fast Reverse Proxy to communicate with C2.
- **C0059 Salesforce Data Exfiltration** (campaign) — During Salesforce Data Exfiltration, threat actors used Mullvad VPN IPs to proxy voice phishing calls.
- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, the adversaries utilized the rsocx tool identified as `r.exe` and `rsocx.exe` to tunnel within the internal infrastructure using a Reverse SOCKS Proxy.
- **G0010 Turla** (group) — Turla RPC backdoors have included local UPnP RPC proxies.
- **G0034 Sandworm Team** (group) — Sandworm Team's BCS-server tool can create an internal proxy server to redirect traffic from the adversary-controlled C2 to internal servers which may not be connected to the internet, but are interconnected locally.
- **G0047 Gamaredon Group** (group) — Gamaredon Group has used the Cloudflare Tunnel client to proxy C2 traffic.
- **G0052 CopyKittens** (group) — CopyKittens has used the AirVPN service for operational activity.
- **G0059 Magic Hound** (group) — Magic Hound has used Fast Reverse Proxy (FRP) for RDP traffic.
- **G0069 MuddyWater** (group) — MuddyWater has used NordVPN to proxy phishing emails, making them appear to originate from France.
- **G0096 APT41** (group) — APT41 used a tool called CLASSFON to covertly proxy network communications.
- **G0108 Blue Mockingbird** (group) — Blue Mockingbird has used FRP, ssf, and Venom to establish SOCKS proxy connections.
- **G0117 Fox Kitten** (group) — Fox Kitten has used the open source reverse proxy tools including FRPC and Go Proxy to establish connections from C2 to local servers.
- **G0124 Windigo** (group) — Windigo has delivered a generic Windows proxy Win32/Glubteta.M. Windigo has also used multiple reverse proxy chains as part of their C2 infrastructure.
- **G1004 LAPSUS$** (group) — LAPSUS$ has leverage NordVPN for its egress points when targeting intended victims.
- **G1005 POLONIUM** (group) — POLONIUM has used the AirVPN service for operational activity.
- **G1006 Earth Lusca** (group) — Earth Lusca adopted Cloudflare as a proxy for compromised servers.
- **G1015 Scattered Spider** (group) — Scattered Spider has used proxy networks to hamper detection and has installed legitimate proxy tools on VMware vCenter and adversary-controlled VMs.
- **G1017 Volt Typhoon** (group) — Volt Typhoon has used compromised devices and customized versions of open source tools such as FRP (Fast Reverse Proxy), Earthworm, and Impacket to proxy network traffic.
- **G1019 MoustachedBouncer** (group) — MoustachedBouncer has used a reverse proxy tool similar to the GitHub repository revsocks.
- **G1021 Cinnamon Tempest** (group) — Cinnamon Tempest has used a customized version of the Iox port-forwarding and proxy tool.
- **G1045 Salt Typhoon** (group) — Salt Typhoon has utilized virtual private servers and compromised routers as proxies for malicious communications.
- **G1052 Contagious Interview** (group) — Contagious Interview has leveraged Astrill VPN for C2.
- **G1054 MirrorFace** (group) — MirrorFace has used the GO Simple Tunnel (GOST) proxy tool.
- **S0040 HTRAN** (software) — HTRAN can proxy TCP socket connections to obfuscate command and control infrastructure.
- **S0108 netsh** (software) — netsh can be used to set up a proxy tunnel to allow remote host access to an infected host.
- **S0117 XTunnel** (software) — XTunnel relays traffic between a C2 server and a victim.
- **S0198 NETWIRE** (software) — NETWIRE can implement use of proxies to pivot traffic.
- **S0207 Vasport** (software) — Vasport is capable of tunneling though a proxy.
- **S0245 BADCALL** (software) — BADCALL functions as a proxy server between the victim and C2 server.
- **S0246 HARDRAIN** (software) — HARDRAIN uses the command `cmd.exe /c netsh firewall add portopening TCP 443 "adp"` and makes the victim machine function as a proxy server.
- **S0262 QuasarRAT** (software) — QuasarRAT can communicate over a reverse proxy using SOCKS5.
- **S0263 TYPEFRAME** (software) — A TYPEFRAME variant can force the compromised system to function as a proxy server.
- **S0268 Bisonal** (software) — Bisonal has supported use of a proxy server.
- **S0273 Socksbot** (software) — Socksbot can start SOCKS proxy threads.
- **S0283 jRAT** (software) — jRAT can serve as a SOCKS proxy server.
- **S0332 Remcos** (software) — Remcos uses the infected hosts as SOCKS5 proxies to allow for tunneling and proxying.
- **S0347 AuditCred** (software) — AuditCred can utilize proxy for communications.
- **S0348 Cardinal RAT** (software) — Cardinal RAT can act as a reverse proxy.
- **S0376 HOPLIGHT** (software) — HOPLIGHT has multiple proxy options that mask traffic between the malware and the remote operators.
- **S0378 PoshC2** (software) — PoshC2 contains modules that allow for use of proxies in command and control.
- **S0384 Dridex** (software) — Dridex contains a backconnect module for tunneling network traffic through a victim's computer. Infected computers become part of a P2P botnet that can relay C2 traffic to other infected peers.
- **S0386 Ursnif** (software) — Ursnif has used a peer-to-peer (P2P) network for C2.
- **S0412 ZxShell** (software) — ZxShell can set up an HTTP or SOCKS proxy.
- **S0435 PLEAD** (software) — PLEAD has the ability to proxy network communications.
- **S0436 TSCookie** (software) — TSCookie has the ability to proxy communications with command and control (C2) servers.
- **S0456 Aria-body** (software) — Aria-body has the ability to use a reverse SOCKS proxy module.
- **S0461 SDBbot** (software) — SDBbot has the ability to use port forwarding to establish a proxy between a target host and C2.
- **S0487 Kessel** (software) — Kessel can use a proxy during exfiltration if set in the configuration.
- **S0508 ngrok** (software) — ngrok can be used to proxy connections to machines located behind NAT or firewalls.
- **S0615 SombRAT** (software) — SombRAT has the ability to use an embedded SOCKS proxy in C2 communications.
- **S0629 RainyDay** (software) — RainyDay can use proxy tools including boost_proxy_client for reverse proxy functionality.
- **S0669 KOCTOPUS** (software) — KOCTOPUS has deployed a modified version of Invoke-Ngrok to expose open local ports to the Internet.
- **S0670 WarzoneRAT** (software) — WarzoneRAT has the capability to act as a reverse proxy.
- **S0690 Green Lambert** (software) — Green Lambert can use proxies for C2 traffic.
- **S1044 FunnyDream** (software) — FunnyDream can identify and use configured proxies in a compromised network for C2 communication.
- **S1051 KEYPLUG** (software) — KEYPLUG has used Cloudflare CDN associated infrastructure to redirect C2 communications to malicious domains.
- **S1081 BADHATCH** (software) — BADHATCH can use SOCKS4 and SOCKS5 proxies to connect to actor-controlled C2 servers. BADHATCH can also emulate a reverse proxy on a compromised machine to connect with actor-controlled C2 servers.
- **S1099 Samurai** (software) — Samurai has the ability to proxy connections to specified remote IPs and ports through a a proxy module.
- **S1114 ZIPLINE** (software) — ZIPLINE can create a proxy server on compromised hosts.
- **S1121 LITTLELAMB.WOOLTEA** (software) — LITTLELAMB.WOOLTEA has the ability to function as a SOCKS proxy.
- **S1141 LunarWeb** (software) — LunarWeb has the ability to use a HTTP proxy server for C&C communications.
- **S1144 FRP** (software) — FRP can proxy communications through a server in public IP space to local servers located behind a NAT or firewall.
- **S1187 reGeorg** (software) — reGeorg can establish an HTTP or SOCKS proxy to tunnel data in and out of a network.
- **S1189 Neo-reGeorg** (software) — Neo-reGeorg has the ability to establish a SOCKS5 proxy on a compromised web server.
- **S1190 Kapeka** (software) — Kapeka can identify system proxy settings via `WinHttpGetIEProxyConfigForCurrentUser()` during initialization and utilize these settings for subsequent command and control operations.
- **S1197 GoBear** (software) — GoBear implements SOCKS5 proxy functionality.
- **S1210 Sagerunex** (software) — Sagerunex uses several proxy configuration settings to ensure connectivity.
- **S1212 RansomHub** (software) — RansomHub can use a proxy to connect to remote SFTP servers.
- **S1229 Havoc** (software) — Havoc has the ability to route HTTP/S communications through designated proxies.
- **S9044 Kali365** (software) — Kali365 has leveraged Cloudflare workers as reverse proxy infrastructure.
- **S9051 The Gentlemen Ransomware** (software) — The Gentlemen Ransomware has utilized SOCKS proxy connections for C2.
