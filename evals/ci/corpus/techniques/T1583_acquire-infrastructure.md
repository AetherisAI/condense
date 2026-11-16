# T1583 — Acquire Infrastructure

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Resource Development
- **Platforms:** PRE
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1583
- **Last modified:** 2026-09-18

## Description

Adversaries may buy, lease, rent, or obtain infrastructure that can be used during targeting. A wide variety of infrastructure exists for hosting and orchestrating adversary operations. Infrastructure solutions include physical or cloud servers, domains, and third-party web services. Some infrastructure providers offer free trial periods, enabling infrastructure acquisition at limited to no cost. Additionally, botnets are available for rent or purchase.

Use of these infrastructure solutions allows adversaries to stage, launch, and execute operations. Solutions may help adversary operations blend in with traffic that is seen as normal, such as contacting third-party web services or acquiring infrastructure to support Proxy, including from residential proxy services. Depending on the implementation, adversaries may use infrastructure that makes it difficult to physically tie back to them as well as utilize infrastructure that can be rapidly provisioned, modified, and shut down.

## Sub-techniques

- **T1583.001 Acquire Infrastructure: Domains**
- **T1583.002 Acquire Infrastructure: DNS Server**
- **T1583.003 Acquire Infrastructure: Virtual Private Server**
- **T1583.004 Acquire Infrastructure: Server**
- **T1583.005 Acquire Infrastructure: Botnet**
- **T1583.006 Acquire Infrastructure: Web Services**
- **T1583.007 Acquire Infrastructure: Serverless**
- **T1583.008 Acquire Infrastructure: Malvertising**

## Mitigations

- **M1056 Pre-compromise** — This technique cannot be easily mitigated with preventive controls since it is based on behaviors performed outside of the scope of enterprise defenses and controls.

## Detection strategies

- **DET0895 Detection of Acquire Infrastructure**
  - AN2027 (PRE): Monitor for contextual data about an Internet-facing resource gathered from a scan, such as running services or ports that may buy, lease, or rent infrastructure that can be used during targeting. Detection efforts may be focused on related stages of the adversary lifecycle, such as during Command and Control. Once adversaries have provisioned infrastructure (ex: a server for use in command and control), internet scans may help proactively discover adversary acquired infrastructure. Consider looking for identifiable patterns such as services listening, certificates in use, SSL/TLS negotiation features, or other response artifacts associated with adversary C2 software. Detection efforts may be focused on related stages of the adversary lifecycle, such as during Command and Control. Monitor for queried domain name system (DNS) registry data that may buy, lease, or rent infrastructure that can be used during targeting. Detection efforts may be focused on related stages of the adversary lifecycle, such as during Command and Control. Monitor for logged domain name system (DNS) data that may buy, lease, or rent infrastructure that can be used during targeting. Detection efforts may be focused on related stages of the adversary lifecycle, such as during Command and Control. Consider use of services that may aid in tracking of newly acquired infrastructure, such as WHOIS databases for domain registration information. Detection efforts may be focused on related stages of the adversary lifecycle, such as during Command and Control. Log sources: Internet Scan (None); Internet Scan (None); Domain Name (None); Domain Name (None); Domain Name (None).

## Procedure examples

- **G0034 Sandworm Team** (group) — Sandworm Team used various third-party email campaign management services to deliver phishing emails.
- **G0094 Kimsuky** (group) — Kimsuky has used funds from stolen and laundered cryptocurrency to acquire operational infrastructure.
- **G0119 Indrik Spider** (group) — Indrik Spider has purchased access to victim VPNs to facilitate access to victim environments.
- **G1003 Ember Bear** (group) — Ember Bear uses services such as IVPN, SurfShark, and Tor to add anonymization to operations.
- **G1030 Agrius** (group) — Agrius typically uses commercial VPN services for anonymizing last-hop traffic to victim networks, such as ProtonVPN.
- **G1033 Star Blizzard** (group) — Star Blizzard has used HubSpot and MailerLite marketing platform services to hide the true sender of phishing emails.
- **G1041 Sea Turtle** (group) — Sea Turtle accessed victim networks from VPN service provider networks.
- **G1052 Contagious Interview** (group) — Contagious Interview has used services such as Astrill VPN.
- **G1056 TeamPCP** (group) — In May 2026 TeamPCP announced co-ownership of the BreachForums cybercriminal forum claiming responsibility for platform operations, dispute resolution, personnel vetting, and hosting monetary contests.
