# M0804 — Human User Authentication

- **Type:** mitigation
- **Domain:** ICS ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/mitigations/M0804
- **Last modified:** 2026-05-12

## Description

Require user authentication before allowing access to data or accepting commands to a device. While strong multi-factor authentication is preferable, it is not always feasible within ICS environments. Performing strong user authentication also requires additional security controls and processes which are often the target of related adversarial techniques (e.g., Valid Accounts, Default Credentials). Therefore, associated ATT&CK mitigations should be considered in addition to this, including Multi-factor Authentication, Account Use Policies, Password Policies, User Account Management, Privileged Account Management, and User Account Control.

## Techniques addressed

- **T0800 Activate Firmware Update Mode** — Devices that allow remote management of firmware should require authentication before allowing any changes. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management
- **T0816 Device Restart/Shutdown** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0821 Modify Controller Tasking** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0836 Modify Parameter** — All field controllers should require that user authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0838 Modify Alarm Settings** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0843 Program Download** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0843.001 Program Download: Download All** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0843.002 Program Download: Online Edit** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0843.003 Program Download: Program Append** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0845 Program Upload** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0858 Change Operating Mode** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0861 Point & Tag Identification** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0868 Detect Operating Mode** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0871 Execution through API** — All APIs on remote systems or local processes should require the authentication of users before executing any code or system changes.
- **T0885 Commonly Used Port** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T0886 Remote Services** — All remote services should require strong authentication before providing user access.
- **T0889 Modify Program** — All field controllers should require users to authenticate for all remote or local management sessions. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T1693 Modify Firmware** — Devices that allow remote management of firmware should require authentication before allowing any changes. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T1693.001 Modify Firmware: System Firmware** — Devices that allow remote management of firmware should require authentication before allowing any changes. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
- **T1693.002 Modify Firmware: Module Firmware** — Devices that allow remote management of firmware should require authentication before allowing any changes. The authentication mechanisms should also support Account Use Policies, Password Policies, and User Account Management.
