# S0601 — Hildegard

- **Type:** software (malware)
- **Domain:** Enterprise ATT&CK
- **Platforms:** Linux, Containers, IaaS
- **ATT&CK URL:** https://attack.mitre.org/software/S0601
- **Last modified:** 2024-04-11

## Description

Hildegard is malware that targets misconfigured kubelets for initial access and runs cryptocurrency miner operations. The malware was first observed in January 2021. The TeamTNT activity group is believed to be behind Hildegard.

## Techniques used

- **T1014 Rootkit** — Hildegard has modified /etc/ld.so.preload to overwrite readdir() and readdir64().
- **T1027.002 Obfuscated Files or Information: Software Packing** — Hildegard has packed ELF files into other binaries.
- **T1027.013 Obfuscated Files or Information: Encrypted/Encoded File** — Hildegard has encrypted an ELF file.
- **T1036.004 Masquerading: Masquerade Task or Service** — Hildegard has disguised itself as a known Linux process.
- **T1046 Network Service Discovery** — Hildegard has used masscan to look for kubelets in the internal Kubernetes network.
- **T1059.004 Command and Scripting Interpreter: Unix Shell** — Hildegard has used shell scripts for execution.
- **T1068 Exploitation for Privilege Escalation** — Hildegard has used the BOtB tool which exploits CVE-2019-5736.
- **T1070.003 Indicator Removal: Clear Command History** — Hildegard has used history -c to clear script shell logs.
- **T1070.004 Indicator Removal: File Deletion** — Hildegard has deleted scripts after execution.
- **T1071 Application Layer Protocol** — Hildegard has used an IRC channel for C2 communications.
- **T1082 System Information Discovery** — Hildegard has collected the host's OS, CPU, and memory information.
- **T1102 Web Service** — Hildegard has downloaded scripts from GitHub.
- **T1105 Ingress Tool Transfer** — Hildegard has downloaded additional scripts that build and run Monero cryptocurrency miners.
- **T1133 External Remote Services** — Hildegard was executed through an unsecure kubelet that allowed anonymous access to the victim environment.
- **T1136.001 Create Account: Local Account** — Hildegard has created a user named “monerodaemon”.
- **T1140 Deobfuscate/Decode Files or Information** — Hildegard has decrypted ELF files with AES.
- **T1219 Remote Access Tools** — Hildegard has established tmate sessions for C2 communications.
- **T1496.001 Resource Hijacking: Compute Hijacking** — Hildegard has used xmrig to mine cryptocurrency.
- **T1543.002 Create or Modify System Process: Systemd Service** — Hildegard has started a monero service.
- **T1552.001 Unsecured Credentials: Credentials In Files** — Hildegard has searched for SSH keys, Docker credentials, and Kubernetes service tokens.
- **T1552.004 Unsecured Credentials: Private Keys** — Hildegard has searched for private keys in .ssh.
- **T1552.005 Unsecured Credentials: Cloud Instance Metadata API** — Hildegard has queried the Cloud Instance Metadata API for cloud credentials.
- **T1574.006 Hijack Execution Flow: Dynamic Linker Hijacking** — Hildegard has modified /etc/ld.so.preload to intercept shared library import functions.
- **T1609 Container Administration Command** — Hildegard was executed through the kubelet API run command and by executing commands on running containers.
- **T1611 Escape to Host** — Hildegard has used the BOtB tool that can break out of containers.
- **T1613 Container and Resource Discovery** — Hildegard has used masscan to search for kubelets and the kubelet API for additional running containers.
- **T1685 Disable or Modify Tools** — Hildegard has modified DNS resolvers to evade DNS monitoring tools.

## Used by

- **G0139 TeamTNT** (group)
