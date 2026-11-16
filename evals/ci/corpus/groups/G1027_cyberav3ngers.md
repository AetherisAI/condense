# G1027 — CyberAv3ngers

- **Type:** group
- **Domain:** ICS ATT&CK
- **Also known as:** Soldiers of Soloman
- **ATT&CK URL:** https://attack.mitre.org/groups/G1027
- **Last modified:** 2026-10-07

## Description

The CyberAv3ngers are a suspected Iranian Government Islamic Revolutionary Guard Corps (IRGC)-affiliated APT group. The CyberAv3ngers have been known to be active since at least 2020, with disputed and false claims of critical infrastructure compromises in Israel.

In 2023, the CyberAv3ngers engaged in a global targeting and hacking of the Unitronics Programmable Logic Controller (PLC) with Human-Machine Interface (HMI). This PLC can be found in multiple sectors, including water and wastewater, energy, food and beverage manufacturing, and healthcare. The most notable feature of this attack was the defacement of the devices user interface.

## Techniques used

- **T0826 Loss of Availability** — During the 2026 Iranian Water Campaign, CyberAv3ngers degraded operations across at least seven states that resulted in reported incidents, pressure loss and flooding.
- **T0827 Loss of Control** — During the 2026 Iranian Water Campaign, CyberAv3ngers manipulated process logic, HMI, and SCADA displays. In addition to this, adversaries locked victims out by changing the PLCs management passwords.
- **T0829 Loss of View** — During the 2026 Iranian Water Campaign, CyberAv3ngers manipulated process logic, HMI, and SCADA displays, which may disrupt operators view of the system.
- **T0838 Modify Alarm Settings** — During the 2026 Iranian Water Campaign, CyberAv3ngers manipulated critical shutdown and alarm logic.
- **T0843 Program Download** — During the 2026 Iranian Water Campaign, CyberAv3ngers used the manufacturers’ commercial PLC programming software to push new configurations to victim hardware. These include Rockwell Automation’s Studio Logix 5000 Designer, Schneider Electric’s EcoStruxure Control Expert, and Siemens’ Totally Integrated Automation (TIA) Portal. In these changes, adversaries deleted program logic, removed Add-On Instructions (AOIs) and manipulated alarm logic and HMI screens.
- **T0845 Program Upload** — During the 2026 Iranian Water Campaign, CyberAv3ngers used the program upload feature to exfiltrate project files from victim PLCs.
- **T0871 Execution through API** — During the 2026 Iranian Water Campaign, CyberAv3ngers leveraged existing PLC management protocols through the manufacturer’s engineering tools. These include EtherNet/IP CIP, S7Comm, and UMAS.
- **T0879 Damage to Property** — During the 2026 Iranian Water Campaign, CyberAv3ngers disrupted water operations that have included loss of water pressure and flooding.
- **T0880 Loss of Safety** — During the 2026 Iranian Water Campaign, CyberAv3ngers manipulated critical shutdown and alarm logic, which would allow the system to enter unsafe process states without proper notification or protections.
- **T0883 Internet Accessible Device** — During the 2026 Iranian Water Campaign, CyberAv3ngers accessed internet accessible PLCs that were exposed through cellular gateways across multiple vendors including Rockwell Automation/Allen-Bradley, Schneider Electric, and Siemens.
- **T0885 Commonly Used Port** — During the 2026 Iranian Water Campaign, CyberAv3ngers were observed using secure shell ports TCP/22 and common industrial ports (TCP/44818, TCP&UDP/2222, TCP/102, and TCP/502).
- **T0886 Remote Services** — During the 2026 Iranian Water Campaign, one victim reported actors leveraged Dropbear Secure Shell (SSH) software to enable remote access over port 22.
- **T0889 Modify Program** — During the 2026 Iranian Water Campaign, CyberAv3ngers used manufacturers’ commercial PLC programming software to modify their victim’s running PLC program logic. These include Rockwell Automation’s Studio Logix 5000 Designer, Schneider Electric’s EcoStruxure Control Expert, and Siemens’ Totally Integrated Automation (TIA) Portal.
- **T0892 Change Credential** — During the 2026 Iranian Water Campaign, CyberAv3ngers locked out operators by changing the PLCs passwords and IP addresses.
- **T1692.001 Unauthorized Message: Command Message** — During the 2026 Iranian Water Campaign, CyberAv3ngers used the manufacturers’ commercial PLC programming and maintenance software to send unauthorized command messages to multiple victim controllers. These include Rockwell Automation’s Studio Logix 5000 Designer, Schneider Electric’s EcoStruxure Control Expert, and Siemens’ Totally Integrated Automation (TIA) Portal .
- **T1694.001 Insecure Credentials: Default Credentials** — During the 2026 Iranian Water Campaign, CyberAv3ngers accessed internet-accessible equipment using default credentials.
- **T1695 Block Communications** — During the 2026 Iranian Water Campaign, CyberAv3ngers locked out operators by changing the PLC’s IP address.

## Campaigns

- **C0031 Unitronics Defacement Campaign**
