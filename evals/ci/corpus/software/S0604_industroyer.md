# S0604 — Industroyer

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK, ICS ATT&CK
- **Also known as:** CRASHOVERRIDE, Win32/Industroyer
- **Platforms:** Windows
- **ATT&CK URL:** https://attack.mitre.org/software/S0604
- **Last modified:** 2026-05-12

## Description

Industroyer is a sophisticated malware framework designed to cause an impact to the working processes of Industrial Control Systems (ICS), specifically components used in electrical substations. Industroyer was used in the attacks on the Ukrainian power grid in December 2016. This is the first publicly known malware specifically designed to target and impact operations in the electric grid.

## Techniques used

- **T0800 Activate Firmware Update Mode** — The Industroyer SIPROTEC DoS module places the victim device into firmware update mode. This is a legitimate use case under normal circumstances, but in this case is used the adversary to prevent the SIPROTEC from performing its designed protective functions. As a result the normal safeguards are disabled, leaving an unprotected link in the electric transmission.
- **T0801 Monitor Process State** — Industroyer's OPC and IEC 61850 protocol modules include the ability to send stVal requests to read the status of operational variables.
- **T0802 Automated Collection** — Industroyer automatically collects protocol object data to learn about control devices in the environment.
- **T0806 Brute Force I/O** — The Industroyer IEC 104 module has 3 modes available to perform its attack. These modes are range, shift, and sequence. The range mode operates in 2 stages. The first stage of range mode gathers Information Object Addresses (IOA) and sends select and execute packets to switch the state. The second stage of range mode has an infinite loop where it will switch the state of all of the previously discovered IOAs. Shift mode is similar to range mode, but instead of staying within the same range, it will add a shift value to the default range values.
- **T0809 Data Destruction** — Industroyer has a destructive wiper that overwrites all ICS configuration files across the hard drives and all mapped network drives specifically targeting ABB PCM600 configuration files.
- **T0813 Denial of Control** — Industroyer is able to block serial COM channels temporarily causing a denial of control.
- **T0814 Denial of Service** — The Industroyer SIPROTEC DoS module exploits the CVE-2015-5374 vulnerability in order to render a Siemens SIPROTEC device unresponsive. Once this vulnerability is successfully exploited, the target device stops responding to any commands until it is rebooted manually. Once the tool is executed it sends specifically crafted packets to port 50,000 of the target IP addresses using UDP. The UDP packet contains the following 18 byte payload: 0x11 49 00 00 00 00 00 00 00 00 00 00 00 00 00 00 28 9E.
- **T0815 Denial of View** — Industroyer is able to block serial COM channels temporarily causing a denial of view.
- **T0816 Device Restart/Shutdown** — The Industroyer SIPROTEC DoS module exploits the CVE-2015-5374 vulnerability in order to render a Siemens SIPROTEC device unresponsive. While the vulnerability does not directly cause the restart or shutdown of the device, the device must be restarted manually before it can resume operations.
- **T0827 Loss of Control** — Industroyer's data wiper component removes the registry image path throughout the system and overwrites all files, rendering the system unusable.
- **T0829 Loss of View** — Industroyer's data wiper component removes the registry image path throughout the system and overwrites all files, rendering the system unusable.
- **T0831 Manipulation of Control** — Industroyer toggles breakers to the open state utilizing unauthorized command messages.
- **T0832 Manipulation of View** — Industroyer's OPC module can brute force values and will send out a 0x01 status which for the target systems equates to a Primary Variable Out of Limits misdirecting operators from understanding protective relay status.
- **T0837 Loss of Protection** — Industroyer contained a module which leveraged a vulnerability in the Siemens SIPROTEC relays (CVE-2015-5374) to create a Denial of Service against automated protective relays.
- **T0840 Network Connection Enumeration** — Industroyer contains an IEC 61850 module that enumerates all connected network adapters to determine their TCP/IP subnet masks.
- **T0846 Remote System Discovery** — Industroyer contains an OPC DA module that enumerates all OPC servers using the `ICatInformation::EnumClassesOfCategories` method with `CATID_OPCDAServer20` category identifier and `IOPCServer::GetStatus` to identify the ones running.
- **T0846.001 Remote System Discovery: Port Scan** — The Industroyer IEC 61850 payload component has the ability to discover relevant devices in the infected host's network subnet by attempting to connect on port 102.
- **T0881 Service Stop** — Industroyer has the capability to stop a service itself, or to login as a user and stop a service as that user.
- **T0884 Connection Proxy** — Industroyer attempts to connect with a hardcoded internal proxy on TCP 3128 [default Squid proxy]. If established, the backdoor attempts to reach an external C2 server via the internal proxy.
- **T0888 Remote System Information Discovery** — The Industroyer IEC 61850 component sends the domain-specific MMSgetNameList request to determine what logical nodes the device supports. It then searches the logical nodes for the CSW value, which indicates the device performs a circuit breaker or switch control function. Industroyer's OPC DA module also uses IOPCBrowseServerAddressSpace to look for items with the following strings: ctlSelOn, ctlOperOn, ctlSelOff, ctlOperOff, Pos and stVal. Industroyer IEC 60870-5-104 module includes a range mode to discover Information Object Addresses (IOAs) by enumerating through each.
- **T1012 Query Registry** — Industroyer has a data wiper component that enumerates keys in the Registry `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services`.
- **T1016 System Network Configuration Discovery** — Industroyer’s 61850 payload component enumerates connected network adapters and their corresponding IP addresses.
- **T1018 Remote System Discovery** — Industroyer can enumerate remote computers in the compromised network.
- **T1027 Obfuscated Files or Information** — Industroyer uses heavily obfuscated code in its Windows Notepad backdoor.
- **T1041 Exfiltration Over C2 Channel** — Industroyer sends information about hardware profiles and previously-received commands back to the C2 server in a POST-request.
- **T1046 Network Service Discovery** — Industroyer uses a custom port scanner to map out a network.
- **T1071.001 Application Layer Protocol: Web Protocols** — Industroyer’s main backdoor connected to a remote C2 server using HTTPS.
- **T1078 Valid Accounts** — Industroyer can use supplied user credentials to execute processes and stop services.
- **T1082 System Information Discovery** — Industroyer collects the victim machine’s Windows GUID.
- **T1083 File and Directory Discovery** — Industroyer’s data wiper component enumerates specific files on all the Windows drives.
- **T1090.003 Proxy: Multi-hop Proxy** — Industroyer used Tor nodes for C2.
- **T1105 Ingress Tool Transfer** — Industroyer downloads a shellcode payload from a remote C2 server and loads it into memory.
- **T1140 Deobfuscate/Decode Files or Information** — Industroyer decrypts code to connect to a remote C2 server.
- **T1485 Data Destruction** — Industroyer’s data wiper module clears registry keys and overwrites both ICS configuration and Windows files.
- **T1489 Service Stop** — Industroyer’s data wiper module writes zeros into the registry keys in `SYSTEM\CurrentControlSet\Services` to render a system inoperable.
- **T1499.004 Endpoint Denial of Service: Application or System Exploitation** — Industroyer uses a custom DoS tool that leverages CVE-2015-5374 and targets hardcoded IP addresses of Siemens SIPROTEC devices.
- **T1543.003 Create or Modify System Process: Windows Service** — Industroyer can use an arbitrary system service to load at system boot for persistence and replaces the ImagePath registry value of a Windows service with a new backdoor binary.
- **T1554 Compromise Host Software Binary** — Industroyer has used a Trojanized version of the Windows Notepad application for an additional backdoor persistence mechanism.
- **T1572 Protocol Tunneling** — Industroyer attempts to perform an HTTP CONNECT via an internal proxy to establish a tunnel.
- **T1691.001 Block Operational Technology Message: Command Message** — In Industroyer the first COM port from the configuration file is used for the actual communication and the two other COM ports are just opened to prevent other processes accessing them. Thus, the IEC 101 payload component is able to take over and maintain control of the RTU device.
- **T1691.002 Block Operational Technology Message: Reporting Message** — Industroyer uses the first COM port from the configuration file for the communication and the other two COM ports are opened to prevent other processes accessing them. This may block processes or operators from getting reporting messages from a device.
- **T1692.001 Unauthorized Message: Command Message** — Using its protocol payloads, Industroyer sends unauthorized commands to RTUs to change the state of equipment.
- **T1695.001 Block Communications: Serial COM** — In Industroyer the first COM port from the configuration file is used for the actual communication and the two other COM ports are just opened to prevent other processes accessing them. Thus, the IEC 101 payload component is able to take over and maintain control of the RTU device.
- **T1701.002 Command and Scripting Interpreter: Windows Command Shell** — The name of the Industroyer payload DLL is supplied by the attackers via a command line parameter supplied in one of the main backdoors that executes shell commands.

## Used by

- **C0025 2016 Ukraine Electric Power Attack** (campaign) — Within the 2016 Ukraine Electric Power Attack, Industroyer was used to target and disrupt the Ukrainian power grid substation components.
- **G0034 Sandworm Team** (group)
