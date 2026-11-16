# M0816 — Mitigation Limited or Not Effective

- **Type:** mitigation
- **Domain:** ICS ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/mitigations/M0816
- **Last modified:** 2026-05-12

## Description

This type of attack technique cannot be easily mitigated with preventative controls since it is based on the abuse of system features.

## Techniques addressed

- **T0801 Monitor Process State** — This type of attack technique cannot be easily mitigated with preventive controls since it is based on the abuse of system features.
- **T0823 Graphical User Interface** — Once an adversary has access to a remote GUI they can abuse system features, such as required HMI functions.
- **T0835 Manipulate I/O Image** — This technique may not be effectively mitigated against, consider controls for assets and processes that lead to the use of this technique.
- **T0840 Network Connection Enumeration** — Network connection enumeration is likely obtained by using common system tools (e.g., netstat, ipconfig).
- **T0852 Screen Capture** — Preventing screen capture on a device may require disabling various system calls supported by the operating systems (e.g., Microsoft Windows.Graphics.Capture APIs), however, these may be needed for other critical applications.
- **T0877 I/O Image** — This technique may not be effectively mitigated against, consider controls for assets and processes that lead to the use of this technique.
