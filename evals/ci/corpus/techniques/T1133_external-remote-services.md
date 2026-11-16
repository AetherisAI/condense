# T1133 — External Remote Services

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Initial Access, Persistence
- **Platforms:** Containers, Linux, macOS, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1133
- **Last modified:** 2026-05-12

## Description

Adversaries may leverage external-facing remote services to initially access and/or persist within a network. Remote services such as VPNs, Citrix, and other access mechanisms allow users to connect to internal enterprise network resources from external locations. There are often remote service gateways that manage connections and credential authentication for these services. Services such as Windows Remote Management and VNC can also be used externally.

Access to Valid Accounts to use the service is often a requirement, which could be obtained through credential pharming or by obtaining the credentials from users after compromising the enterprise network. Access to remote services may be used as a redundant or persistent access mechanism during an operation.

Access may also be gained through an exposed service that doesn’t require authentication. In containerized environments, this may include an exposed Docker API, Kubernetes API server, kubelet, or web application such as the Kubernetes dashboard.

Adversaries may also establish persistence on network by configuring a Tor hidden service on a compromised system. Adversaries may utilize the tool `ShadowLink` to facilitate the installation and configuration of the Tor hidden service. Tor hidden service is then accessible via the Tor network because `ShadowLink` sets up a .onion address on the compromised system. `ShadowLink` may be used to forward any inbound connections to RDP, allowing the adversaries to have remote access. Adversaries may get `ShadowLink` to persist on a system by masquerading it as an MS Defender application.

## Mitigations

- **M1021 Restrict Web-Based Content** — Restrict all traffic to and from public Tor nodes.
- **M1030 Network Segmentation** — Deny direct remote access to internal systems through the use of network proxies, gateways, and firewalls.
- **M1032 Multi-factor Authentication** — Use strong two-factor or multi-factor authentication for remote service accounts to mitigate an adversary's ability to leverage stolen credentials, but be aware of Multi-Factor Authentication Interception techniques for some two-factor authentication implementations.
- **M1035 Limit Access to Resource Over Network** — Limit access to remote services through centrally managed concentrators such as VPNs and other managed remote access systems.
- **M1042 Disable or Remove Feature or Program** — Disable or block remotely available services that may be unnecessary.

## Detection strategies

- **DET0354 Behavior-chain detection for T1133 External Remote Services across Windows, Linux, macOS, Containers**
  - AN1004 (Windows): Unusual or unauthorized external remote access attempts (e.g., RDP, VPN, Citrix) → repeated failed logins followed by a successful session from uncommon geolocations or outside business hours → subsequent internal lateral movement or data exfiltration activities. Log sources: WinEventLog:Security (EventCode=4776, 4625); WinEventLog:Application (VPN, Citrix, or remote access gateway logs showing external IP addresses); WinEventLog:Sysmon (EventCode=3, 22).
  - AN1005 (Linux): Repeated SSH, VPN, or RDP gateway authentication attempts from external IPs → subsequent successful logon → remote shell or lateral movement activity (e.g., scp/sftp). Log sources: auditd:SYSCALL (ssh logins or execve of remote commands); NSM:Connections (Failed password or accepted password for SSH users); NSM:Flow (connection: Inbound connections to SSH or VPN ports).
  - AN1006 (macOS): Unexpected inbound or outbound VNC/SSH/Screen Sharing connections from external sources → repeated failed logins followed by success → remote interactive sessions or abnormal file transfers. Log sources: macos:unifiedlog (Remote login (ssh) or screen sharing authentication attempts); macos:unifiedlog (Inbound connections to VNC/SSH ports); PF:Logs (External traffic to remote access services).
  - AN1007 (Containers): Connections to exposed container services (e.g., Docker API, Kubernetes API server) from unauthorized external IPs → abnormal container creation/start → lateral activity within cluster nodes. Log sources: ApplicationLog:API (Docker/Kubernetes API access from external sources); kubernetes:audit (Unauthorized container creation or kubelet exec logs); NSM:Flow (External access to container ports (2375, 6443)).

## Procedure examples

- **C0002 Night Dragon** (campaign) — During Night Dragon, threat actors used compromised VPN accounts to gain access to victim systems.
- **C0004 CostaRicto** (campaign) — During CostaRicto, the threat actors set up remote tunneling using an SSH tool to maintain access to a compromised environment.
- **C0012 Operation CuckooBees** (campaign) — During Operation CuckooBees, the threat actors enabled WinRM over HTTP/HTTPS as a backup persistence mechanism using the following command: `cscript //nologo "C:\Windows\System32\winrm.vbs" set winrm/config/service@{EnableCompatibilityHttpsListener="true"}`.
- **C0014 Operation Wocao** (campaign) — During Operation Wocao, threat actors used stolen credentials to connect to the victim's network via VPN.
- **C0024 SolarWinds Compromise** (campaign) — For the SolarWinds Compromise, APT29 used compromised identities to access networks via SSH, VPNs, and other remote access tools.
- **C0027 C0027** (campaign) — During C0027, Scattered Spider used Citrix and VPNs to persist in compromised environments.
- **C0028 2015 Ukraine Electric Power Attack** (campaign) — During the 2015 Ukraine Electric Power Attack, Sandworm Team installed a modified Dropbear SSH client as the backdoor to target systems.
- **C0032 C0032** (campaign) — During the C0032 campaign, TEMP.Veles used VPN access to persist in the victim environment.
- **C0046 ArcaneDoor** (campaign) — ArcaneDoor used WebVPN sessions commonly associated with Clientless SSLVPN services to communicate to compromised devices.
- **C0063 2025 Poland Wiper Attacks** (campaign) — During the 2025 Poland Wiper Attacks, threat actors leveraged the FortiGate VPN interface that was exposed to the internet to gain access to the victim environment.
- **G0004 Ke3chang** (group) — Ke3chang has gained access through VPNs including with compromised accounts and stolen VPN certificates.
- **G0007 APT28** (group) — APT28 has used Tor and a variety of commercial VPN services to route brute force authentication attempts.
- **G0016 APT29** (group) — APT29 has used compromised identities to access networks via VPNs and Citrix.
- **G0026 APT18** (group) — APT18 actors leverage legitimate credentials to log into external remote services.
- **G0027 Threat Group-3390** (group) — Threat Group-3390 actors look for and use VPN profiles during an operation to access the network using external VPN services. Threat Group-3390 has also obtained OWA account credentials during intrusions that it subsequently used to attempt to regain access when evicted from a victim network.
- **G0034 Sandworm Team** (group) — Sandworm Team has used Dropbear SSH with a hardcoded backdoor password to maintain persistence within the target network. Sandworm Team has also used VPN tunnels established in legitimate software company infrastructure to gain access to internal networks of that software company's users.
- **G0035 Dragonfly** (group) — Dragonfly has used VPNs and Outlook Web Access (OWA) to maintain access to victim networks.
- **G0049 OilRig** (group) — OilRig uses remote services such as VPN, Citrix, or OWA to persist in an environment.
- **G0053 FIN5** (group) — FIN5 has used legitimate VPN, Citrix, or VNC credentials to maintain access to a victim environment.
- **G0065 Leviathan** (group) — Leviathan has used external remote services such as virtual private networks (VPN) to gain initial access.
- **G0093 GALLIUM** (group) — GALLIUM has used VPN services, including SoftEther VPN, to access and maintain persistence in victim environments.
- **G0094 Kimsuky** (group) — Kimsuky has used RDP to establish persistence.
- **G0096 APT41** (group) — APT41 compromised an online billing/payment service using VPN access between a third-party service provider and the targeted payment service.
- **G0099 APT-C-36** (group) — APT-C-36 has used VPNs in their operational infrastructure.
- **G0102 Wizard Spider** (group) — Wizard Spider has accessed victim networks by using stolen credentials to access the corporate VPN infrastructure.
- **G0114 Chimera** (group) — Chimera has used legitimate credentials to login to an external VPN, Citrix, SSH, and other remote services.
- **G0115 GOLD SOUTHFIELD** (group) — GOLD SOUTHFIELD has used publicly-accessible RDP and remote management and monitoring (RMM) servers to gain access to victim machines.
- **G0139 TeamTNT** (group) — TeamTNT has used open-source tools such as Weave Scope to target exposed Docker API ports and gain initial access to victim environments. TeamTNT has also targeted exposed kubelets for Kubernetes environments.
- **G1003 Ember Bear** (group) — Ember Bear have used VPNs both for initial access to victim environments and for persistence within them following compromise.
- **G1004 LAPSUS$** (group) — LAPSUS$ has gained access to internet-facing systems and applications, including virtual private network (VPN), remote desktop protocol (RDP), and virtual desktop infrastructure (VDI) including Citrix.
- **G1015 Scattered Spider** (group) — Scattered Spider has leveraged legitimate remote management tools to maintain persistent access.
- **G1016 FIN13** (group) — FIN13 has gained access to compromised environments via remote access services such as the corporate virtual private network (VPN).
- **G1017 Volt Typhoon** (group) — Volt Typhoon has used VPNs to connect to victim environments and enable post-exploitation actions.
- **G1024 Akira** (group) — Akira uses compromised VPN accounts for initial access to victim networks.
- **G1040 Play** (group) — Play has used Remote Desktop Protocol (RDP) and Virtual Private Networks (VPN) for initial access.
- **G1041 Sea Turtle** (group) — Sea Turtle has used external-facing SSH to achieve initial access to the IT environments of victim organizations.
- **G1047 Velvet Ant** (group) — Velvet Ant has leveraged access to internet-facing remote services to compromise and retain access to victim environments.
- **G1055 VOID MANTICORE** (group) — VOID MANTICORE has leveraged public facing VPN infrastructure to gain initial access to victim environments.
- **S0362 Linux Rabbit** (software) — Linux Rabbit attempts to gain access to the server via SSH.
- **S0599 Kinsing** (software) — Kinsing was executed in an Ubuntu container deployed via an open Docker daemon API.
- **S0600 Doki** (software) — Doki was executed through an open Docker daemon API port.
- **S0601 Hildegard** (software) — Hildegard was executed through an unsecure kubelet that allowed anonymous access to the victim environment.
- **S1060 Mafalda** (software) — Mafalda can establish an SSH connection from a compromised host to a server.
