# M0942 — Disable or Remove Feature or Program

- **Type:** mitigation
- **Domain:** ICS ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/mitigations/M0942
- **Last modified:** 2026-10-07

## Description

Remove or deny access to unnecessary and potentially vulnerable software to prevent abuse by adversaries.

## Techniques addressed

- **T0816 Device Restart/Shutdown** — Ensure remote commands that enable device shutdown are disabled if they are not necessary. Examples include DNP3's 0x0D function code or unnecessary device management functions.
- **T0822 External Remote Services** — Consider removal of remote services which are not regularly in use, or only enabling them when required (e.g., vendor remote access). Ensure all external remote access point (e.g., jump boxes, VPN concentrator) are configured with least functionality, especially the removal of unnecessary services.
- **T0830 Adversary-in-the-Middle** — Disable unnecessary legacy network protocols that may be used for AiTM if applicable.
- **T0847 Replication Through Removable Media** — Consider the disabling of features such as AutoRun.
- **T0866 Exploitation of Remote Services** — Ensure that unnecessary ports and services are closed to prevent risk of discovery and potential exploitation.
- **T0885 Commonly Used Port** — Ensure that unnecessary ports and services are closed to prevent risk of discovery and potential exploitation.
- **T1701 Command and Scripting Interpreter** — Consider removing or restricting features that are unnecessary to an asset's intended function within the control environment.
- **T1701.001 Command and Scripting Interpreter: PowerShell** — Where PowerShell is not required for the documented function of an ICS asset, disable or remove access to it. Do not apply this control to systems where vendor support, engineering workflows, backup, patching, or approved automation depend on PowerShell.
- **T1701.004 Command and Scripting Interpreter: Visual Basic** — Disable Windows Script Host, Office macro capability, or other VB execution surfaces only on ICS assets where they are not required by validated vendor or engineering workflows.
- **T1701.006 Command and Scripting Interpreter: JavaScript** — Disable or remove JavaScript/JScript execution surfaces that are not required for the documented role of an ICS asset, while preserving validated HMI, vendor, and engineering dependencies.
