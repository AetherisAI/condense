# T1608 — Stage Capabilities

- **Type:** technique
- **Domain:** Enterprise ATT&CK
- **Tactics:** Resource Development
- **Platforms:** PRE
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1608
- **Last modified:** 2025-10-24

## Description

Adversaries may upload, install, or otherwise set up capabilities that can be used during targeting. To support their operations, an adversary may need to take capabilities they developed (Develop Capabilities) or obtained (Obtain Capabilities) and stage them on infrastructure under their control. These capabilities may be staged on infrastructure that was previously purchased/rented by the adversary (Acquire Infrastructure) or was otherwise compromised by them (Compromise Infrastructure). Capabilities may also be staged on web services, such as GitHub or Pastebin, or on Platform-as-a-Service (PaaS) offerings that enable users to easily provision applications.

Staging of capabilities can aid the adversary in a number of initial access and post-compromise behaviors, including (but not limited to):

* Staging web resources necessary to conduct Drive-by Compromise when a user browses to a site.
* Staging web resources for a link target to be used with spearphishing.
* Uploading malware or tools to a location accessible to a victim network to enable Ingress Tool Transfer.
* Installing a previously acquired SSL/TLS certificate to use to encrypt command and control traffic (ex: Asymmetric Cryptography with Web Protocols).

## Sub-techniques

- **T1608.001 Stage Capabilities: Upload Malware**
- **T1608.002 Stage Capabilities: Upload Tool**
- **T1608.003 Stage Capabilities: Install Digital Certificate**
- **T1608.004 Stage Capabilities: Drive-by Target**
- **T1608.005 Stage Capabilities: Link Target**
- **T1608.006 Stage Capabilities: SEO Poisoning**
- **T1608.007 Stage Capabilities: AI Result Poisoning**

## Mitigations

- **M1056 Pre-compromise** — This technique cannot be easily mitigated with preventive controls since it is based on behaviors performed outside of the scope of enterprise defenses and controls.

## Detection strategies

- **DET0839 Detection of Stage Capabilities**
  - AN1971 (PRE): If infrastructure or patterns in malware, tooling, certificates, or malicious web content have been previously identified, internet scanning may uncover when an adversary has staged their capabilities. Much of this activity will take place outside the visibility of the target organization, making detection of this behavior difficult. Detection efforts may be focused on related stages of the adversary lifecycle, such as initial access and post-compromise behaviors. Log sources: Internet Scan (None).

## Procedure examples

- **G0129 Mustang Panda** (group) — Mustang Panda has used servers under their control to validate tracking pixels sent to phishing victims.
