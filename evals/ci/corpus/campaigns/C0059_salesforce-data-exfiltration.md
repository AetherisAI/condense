# C0059 — Salesforce Data Exfiltration

- **Type:** campaign
- **Domain:** Enterprise ATT&CK
- **First seen:** 2024-10-01
- **Last seen:** 2025-09-01
- **ATT&CK URL:** https://attack.mitre.org/campaigns/C0059
- **Last modified:** 2026-10-09

## Description

The Salesforce Data Exfiltration campaign began in October 2024 with financially-motivated threat actor UNC6040 using Spearphishing Voice (vishing) to compromise corporate Salesforce instances for large-scale data theft and extortion. Following the initial data theft, victim organizations received extortion demands from a separate threat actor, UNC6240, who claimed to be the “ShinyHunters” group. The observed infrastructure and TTPs used during the Salesforce Data Exfiltration campaign overlap with those used by threat groups with suspected ties to the broader collective known as "The Com.” These overlaps could plausibly be the result of associated actors operating within the same communities and are not necessarily an indication of a direct operational relationship.

## Techniques used

- **T1020 Automated Exfiltration** — During Salesforce Data Exfiltration, threat actors used API queries to automatically exfiltrate large volumes of data.
- **T1036 Masquerading** — During Salesforce Data Exfiltration, threat actors used voice calls to socially engineer victims into authorizing a modified version of the Salesforce Data Loader app.
- **T1059.006 Command and Scripting Interpreter: Python** — During Salesforce Data Exfiltration, threat actors used custom applications developed in python.
- **T1078.002 Valid Accounts: Domain Accounts** — During Salesforce Data Exfiltration, threat actors used compromised credentials for lateral movement.
- **T1083 File and Directory Discovery** — During Salesforce Data Exfiltration, threat actors queried customers' Salesforce environments to identify sensitive information for exfiltration.
- **T1090 Proxy** — During Salesforce Data Exfiltration, threat actors used Mullvad VPN IPs to proxy voice phishing calls.
- **T1090.003 Proxy: Multi-hop Proxy** — During Salesforce Data Exfiltration, threat actors used Tor IPs for voice calls and for the collection of stolen data.
- **T1213.004 Data from Information Repositories: Customer Relationship Management Software** — During Salesforce Data Exfiltration, threat actors accessed and exfiltrated sensitive information from compromised Salesforce instances.
- **T1567 Exfiltration Over Web Service** — During Salesforce Data Exfiltration, threat actors exfiltrated data via legitimate Salesforce API communication channels including the Salesforce Data Loader application.
- **T1585 Establish Accounts** — During Salesforce Data Exfiltration, threat actors created Salesforce trial accounts to register their malicious applications.
- **T1585.002 Establish Accounts: Email Accounts** — During Salesforce Data Exfiltration, threat actors registered emails shinycorp@tuta[.]com and shinygroup@tuta[.]com to send victims extortion demands.
- **T1586.002 Compromise Accounts: Email Accounts** — During Salesforce Data Exfiltration, threat actors used compromised emails to create Salesforce trial accounts.
- **T1587.001 Develop Capabilities: Malware** — During Salesforce Data Exfiltration, threat actors created malicious applications within Salesforce trial accounts, typically Python scripts with similar function to the Salesforce Data Loader.
- **T1588.002 Obtain Capabilities: Tool** — During Salesforce Data Exfiltration, threat actors initially relied on the legitimate Salesforce Data Loader app for data exfiltration.
- **T1598.004 Phishing for Information: Spearphishing Voice** — During Salesforce Data Exfiltration, threat actors initiated voice calls with victims to socially engineer them into authorizing malicious applications or divulging sensitive credentials.
- **T1608.005 Stage Capabilities: Link Target** — During Salesforce Data Exfiltration, threat actors established an Okta phishing panel which victims were tricked into accessing from mobile phones or work computers during social engineering calls.
- **T1671 Cloud Application Integration** — During Salesforce Data Exfiltration, threat actors deceived victims into authorizing malicious connected apps to their organization's Salesforce portal.
- **T1684.001 Social Engineering: Impersonation** — During Salesforce Data Exfiltration, threat actors impersonated IT support personnel in voice calls with victims at times claiming to be addressing enterprise-wide connectivity issues.

## Software used

- **S0183 Tor** — During Salesforce Data Exfiltration, threat actors used Tor IPs for voice calls and data collection.
