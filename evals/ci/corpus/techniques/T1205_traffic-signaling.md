# T1205 — Traffic Signaling

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Command and Control, Persistence, Stealth
- **Platforms:** Linux, macOS, Network Devices, Windows
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1205
- **Last modified:** 2026-11-04

## Description

Adversaries may use traffic signaling to hide open ports or other malicious functionality used for persistence or command and control. Traffic signaling involves the use of a magic value or sequence that must be sent to a system to trigger a special response, such as opening a closed port or executing a malicious task. This may take the form of sending a series of packets with certain characteristics before a port will be opened that the adversary can use for command and control. Usually this series of packets consists of attempted connections to a predefined sequence of closed ports (i.e. Port Knocking), but can involve unusual flags, specific strings, or other unique characteristics. After the sequence is completed, opening a port may be accomplished by the host-based firewall, but could also be implemented by custom software.

Adversaries may also communicate with an already open port, but the service listening on that port will only respond to commands or trigger other malicious functionality if passed the appropriate magic value(s).

The observation of the signal packets to trigger the communication can be conducted through different methods. One means, originally implemented by Cd00r, is to use the libpcap libraries to sniff for the packets in question. Another method leverages raw sockets, which enables the malware to use ports that are already open for use by other programs.

On network devices, adversaries may use crafted packets to enable Network Device Authentication for standard services offered by the device such as telnet. Such signaling may also be used to open a closed service port such as telnet, or to trigger module modification of malware implants on the device, adding, removing, or changing malicious capabilities. Adversaries may use crafted packets to attempt to connect to one or more (open or closed) ports, but may also attempt to connect to a router interface, broadcast, and network address IP on the same port in order to achieve their goals and objectives. To enable this traffic signaling on embedded devices, adversaries must first achieve and leverage Patch System Image due to the monolithic nature of the architecture.

Adversaries may also use the Wake-on-LAN feature to turn on powered off systems. Wake-on-LAN is a hardware feature that allows a powered down system to be powered on, or woken up, by sending a magic packet to it. Once the system is powered on, it may become a target for lateral movement.

## Sub-techniques

- **T1205.001 Traffic Signaling: Port Knocking**
- **T1205.002 Traffic Signaling: Socket Filters**

## Mitigations

- **M1037 Filter Network Traffic** — Mitigation of some variants of this technique could be achieved through the use of stateful firewalls, depending upon how it is implemented.
- **M1042 Disable or Remove Feature or Program** — Disable Wake-on-LAN if it is not needed within an environment.

## Detection strategies

- **DET0524 Traffic Signaling (Port-knock / magic-packet → firewall or service activation) – T1205**
  - AN1448 (Windows): A remote host sends a short sequence of failed connection attempts (RST/ICMP unreachable) to a set of closed ports. Within a brief window the endpoint (a) adds/enables a firewall rule or (b) a sniffer-backed process begins listening or opens a new socket, after which a successful connection occurs. Also detects Wake-on-LAN magic packets seen on local segment. Log sources: WinEventLog:Sysmon (EventCode=1); WinEventLog:Sysmon (EventCode=3, 22); WinEventLog:Microsoft-Windows-Windows Firewall With Advanced Security/Firewall (EventCode=2004, 2005, 2006); WinEventLog:PowerShell (EventCode=4103, 4104, 4105, 4106).
  - AN1449 (Linux): Closed-port knock sequence from a remote IP followed by on-host firewall change (iptables/nftables) or daemon starts listening (socket open) and a successful TCP/UDP connect. Optional detection of libpcap/raw-socket sniffers spawning to watch for secret values. Log sources: auditd:SYSCALL (execve: Commands altering firewall or enabling listeners (iptables, nft, ufw, firewall-cmd, systemctl start *ssh*/*telnet*, ip route add, tcpdump, tshark)); auditd:SYSCALL (socket/bind: Process binds to a new local port shortly after knock); NSM:Flow (Knock pattern: multiple REJ/S0 to distinct closed ports then successful connection to service_port); NSM:Flow (Packets with unusual flags or payloads outside established flows (e.g., WoL magic FF×6 + 16×MAC)).
  - AN1450 (macOS): Remote knock sequence followed by PF/socketfilterfw rule update or a background process listening on a new port; then a successful TCP session. Also flags WoL magic packets on local segment. Log sources: macos:unifiedlog (exec: Execution of /sbin/pfctl, /usr/libexec/ApplicationFirewall/socketfilterfw, ifconfig, tcpdump, npcap/libpcap consumers); macos:unifiedlog (Firewall rule enable/disable or listen socket changes); NSM:Flow (Closed-port hits followed by success from same src_ip).
  - AN1451 (Network Devices): Crafted ‘synful knock’ patterns toward routers/switches (same src hits interface/broadcast/network address on same port in short order) followed by ACL/telnet/SSH enablement or module change. Detect device image/ACL updates then a new mgmt session. Log sources: networkdevice:syslog (Config/ACL/line vty changes, service enable (telnet/ssh/http(s)), module reloads); NSM:Flow (Port-knock pattern from one src to device unicast,broadcast,network addresses on same port within TimeWindowKnock).

## Procedure examples

- **C0029 Cutting Edge** (campaign) — During Cutting Edge, threat actors sent a magic 48-byte sequence to enable the PITSOCK backdoor to communicate via the `/tmp/clientsDownload.sock` socket.
- **C0056 RedPenguin** (campaign) — During RedPenguin, UNC3886 leveraged malware capable of inpecting packets for a magic-string to activate backdoor functionalities.
- **G0094 Kimsuky** (group) — Kimsuky has used TRANSLATEXT to redirect clients to legitimate Gmail, Naver or Kakao pages if the clients connect with no parameters.
- **G0129 Mustang Panda** (group) — Mustang Panda has utilized a magic value in C2 communications and only executes in memory when response packets match specific values of “17 03 03” or “46 77 4d”.
- **G1048 UNC3886** (group) — UNC3886 has used the TABLEFLIP traffic redirection utility to listen for specialized command packets on compromised FortiManager devices.
- **S0022 Uroburos** (software) — Uroburos can intercept the first client to server packet in the 3-way TCP handshake to determine if the packet contains the correct unique value for a specific Uroburos implant. If the value does not match, the packet and the rest of the TCP session are passed to the legitimate listening application.
- **S0220 Chaos** (software) — Chaos provides a reverse shell is triggered upon receipt of a packet with a special string, sent to any port.
- **S0221 Umbreon** (software) — Umbreon provides additional access using its backdoor Espeon, providing a reverse shell upon receipt of a special packet.
- **S0430 Winnti for Linux** (software) — Winnti for Linux has used a passive listener, capable of identifying a specific magic value before executing tasking, as a secondary command and control (C2) mechanism.
- **S0446 Ryuk** (software) — Ryuk has used Wake-on-Lan to power on turned off systems for lateral movement.
- **S0519 SYNful Knock** (software) — SYNful Knock can be sent instructions via special packets to change its functionality. Code for new functionality can be included in these messages.
- **S0587 Penquin** (software) — Penquin will connect to C2 only after sniffing a "magic packet" value in TCP or UDP packets matching specific conditions.
- **S0641 Kobalos** (software) — Kobalos is triggered by an incoming TCP connection to a legitimate service from a specific source port.
- **S0664 Pandora** (software) — Pandora can identify if incoming HTTP traffic contains a token and if so it will intercept the traffic and process the received command.
- **S1114 ZIPLINE** (software) — ZIPLINE can identify a specific string in intercepted network traffic, `SSH-2.0-OpenSSH_0.3xx.`, to trigger its command functionality.
- **S1118 BUSHWALK** (software) — BUSHWALK can modify the `DSUserAgentCap.pm` Perl module on Ivanti Connect Secure VPNs and either activate or deactivate depending on the value of the user agent in incoming HTTP requests.
- **S1201 TRANSLATEXT** (software) — TRANSLATEXT has redirected clients to legitimate Gmail, Naver or Kakao pages if the clients connect with no parameters.
- **S1203 J-magic** (software) — J-magic can monitor TCP traffic for packets containing one of five different predefined parameters and will spawn a reverse shell if one of the parameters and the proper response string to a subsequent challenge is received.
- **S1219 REPTILE** (software) — The REPTILE reverse shell component can listen for a specialized packet in TCP, UDP, or ICMP for activation.
- **S1228 PUBLOAD** (software) — PUBLOAD has utilized a magic value in C2 communications and only executes in memory when response packets match specific values of 17 03 03. PUBLOAD has also used magic bytes consisting of 46 77 4d.
- **S1239 TONESHELL** (software) — TONESHELL has utilized a magic value in C2 communications and only executes in memory when response packets match specific values.
- **S9011 BRUSHFIRE** (software) — BRUSHFIRE has monitored inbound VPN traffic to compromised appliances until specific inbound packets contain a specific magic string/pattern instead of external beaconing.
- **S9043 Mini Shai-Hulud** (software) — Mini Shai-Hulud has examined commit messages for a keyword followed by base64 encoded segments to validate communications and to execute subsequent actions to include exfiltration.
