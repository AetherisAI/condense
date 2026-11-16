# M1013 — Application Developer Guidance

- **Type:** mitigation
- **Domain:** Enterprise ATT&CK, Mobile ATT&CK
- **ATT&CK URL:** https://attack.mitre.org/mitigations/M1013
- **Last modified:** 2024-12-10

## Description

Application Developer Guidance focuses on providing developers with the knowledge, tools, and best practices needed to write secure code, reduce vulnerabilities, and implement secure design principles. By integrating security throughout the software development lifecycle (SDLC), this mitigation aims to prevent the introduction of exploitable weaknesses in applications, systems, and APIs. This mitigation can be implemented through the following measures:
 
Preventing SQL Injection (Secure Coding Practice):

- Implementation: Train developers to use parameterized queries or prepared statements instead of directly embedding user input into SQL queries.
- Use Case: A web application accepts user input to search a database. By sanitizing and validating user inputs, developers can prevent attackers from injecting malicious SQL commands.

Cross-Site Scripting (XSS) Mitigation:

- Implementation: Require developers to implement output encoding for all user-generated content displayed on a web page.
- Use Case: An e-commerce site allows users to leave product reviews. Properly encoding and escaping user inputs prevents malicious scripts from being executed in other users’ browsers.

Secure API Design:

- Implementation: Train developers to authenticate all API endpoints and avoid exposing sensitive information in API responses.
- Use Case: A mobile banking application uses APIs for account management. By enforcing token-based authentication for every API call, developers reduce the risk of unauthorized access.

Static Code Analysis in the Build Pipeline:

- Implementation: Incorporate tools into CI/CD pipelines to automatically scan for vulnerabilities during the build process.
- Use Case: A fintech company integrates static analysis tools to detect hardcoded credentials in their source code before deployment.

Threat Modeling in the Design Phase:

- Implementation: Use frameworks like STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) to assess threats during application design.
- Use Case: Before launching a customer portal, a SaaS company identifies potential abuse cases, such as session hijacking, and designs mitigations like secure session management.

**Tools for Implementation**:

- Static Code Analysis Tools: Use tools that can scan for known vulnerabilities in source code.
- Dynamic Application Security Testing (DAST): Use tools like Burp Suite or OWASP ZAP to simulate runtime attacks and identify vulnerabilities.
- Secure Frameworks: Recommend secure-by-default frameworks (e.g., Django for Python, Spring Security for Java) that enforce security best practices.

## Techniques addressed

- **T1078 Valid Accounts** — Ensure that applications do not store sensitive data or credentials insecurely. (e.g. plaintext credentials in code, published credentials in repositories, or credentials in public cloud storage).
- **T1195 Supply Chain Compromise** — Application developers should be cautious when selecting third-party libraries to integrate into their application. Additionally, where possible, developers should lock software dependencies to specific versions rather than pulling the latest version on build.
- **T1195.001 Supply Chain Compromise: Compromise Software Dependencies and Development Tools** — Application developers should be cautious when selecting third-party libraries to integrate into their application. Additionally, where possible, developers should lock software dependencies to specific versions rather than pulling the latest version on build. GitHub Actions may be pinned to a specific commit hash rather than a tag or branch.
- **T1212 Exploitation for Credential Access** — Application developers should consider taking measures to validate authentication requests by enabling one-time passwords, providing timestamps or sequence numbers for messages sent, using digital signatures, and/or using random session keys.
- **T1474 Supply Chain Compromise** — Application developers should be cautious when selecting third-party libraries to integrate into their application.
- **T1474.001 Supply Chain Compromise: Compromise Software Dependencies and Development Tools** — Application developers should be cautious when selecting third-party libraries to integrate into their application.
- **T1496.003 Resource Hijacking: SMS Pumping** — Consider implementing CAPTCHA protection on forms that send messages via SMS.
- **T1513 Screen Capture** — Application developers can apply the `FLAG_SECURE` property to sensitive screens within their apps to make it more difficult for the screen contents to be captured.
- **T1517 Access Notifications** — Application developers could be encouraged to avoid placing sensitive data in notification text.
- **T1550 Use Alternate Authentication Material** — Consider implementing token binding strategies, such as Azure AD token protection or OAuth Proof of Possession, that cryptographically bind a token to a secret. This may prevent the token from being used without knowledge of the secret or possession of the device the token is tied to.
- **T1550.001 Use Alternate Authentication Material: Application Access Token** — Consider implementing token binding strategies, such as Azure AD token protection or OAuth Proof of Possession, that cryptographically bind a token to a secret. This may prevent the token from being used without knowledge of the secret or possession of the device the token is tied to.
- **T1559 Inter-Process Communication** — Enable the Hardened Runtime capability when developing applications. Do not include the `com.apple.security.get-task-allow` entitlement with the value set to any variation of true.
- **T1559.003 Inter-Process Communication: XPC Services** — Enable the Hardened Runtime capability when developing applications. Do not include the `com.apple.security.get-task-allow` entitlement with the value set to any variation of true.
- **T1564 Hide Artifacts** — Application developers should consider limiting the requirements for custom or otherwise difficult to manage file/folder exclusions. Where possible, install applications to trusted system folder paths that are already protected by restricted file and directory permissions.
- **T1564.009 Hide Artifacts: Resource Forking** — Configure applications to use the application bundle structure which leverages the `/Resources` folder location.
- **T1564.012 Hide Artifacts: File/Path Exclusions** — Application developers should consider limiting the requirements for custom or otherwise difficult to manage file/folder exclusions. Where possible, install applications to trusted system folder paths that are already protected by restricted file and directory permissions.
- **T1574 Hijack Execution Flow** — When possible, include hash values in manifest files to help prevent side-loading of malicious libraries.
- **T1574.001 Hijack Execution Flow: DLL** — When possible, include hash values in manifest files to help prevent side-loading of malicious libraries.
- **T1593 Search Open Websites/Domains** — Application developers uploading to public code repositories should be careful to avoid publishing sensitive information such as credentials and API keys.
- **T1593.003 Search Open Websites/Domains: Code Repositories** — Application developers uploading to public code repositories should be careful to avoid publishing sensitive information such as credentials and API keys.
- **T1626 Abuse Elevation Control Mechanism** — Applications very rarely require administrator permission. Developers should be cautioned against using this higher degree of access to avoid being flagged as a potentially malicious application.
- **T1635 Steal Application Access Token** — Developers should use Android App Links and iOS Universal Links to provide a secure binding between URIs and applications, preventing malicious applications from intercepting redirections. Additionally, for OAuth use cases, PKCE should be used to prevent use of stolen authorization codes.
- **T1635.001 Steal Application Access Token: URI Hijacking** — Developers should use Android App Links and iOS Universal Links to provide a secure binding between URIs and applications, preventing malicious applications from intercepting redirections. Additionally, for OAuth use cases, PKCE should be used to prevent use of stolen authorization codes.
- **T1647 Plist File Modification** — Ensure applications are using Apple's developer guidance which enables hardened runtime.
