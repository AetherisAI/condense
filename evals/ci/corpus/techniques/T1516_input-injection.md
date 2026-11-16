# T1516 — Input Injection

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Defense Evasion, Impact
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1516
- **Last modified:** 2026-05-12

## Description

A malicious application can inject input to the user interface to mimic user interaction through the abuse of Android's accessibility APIs.

Input Injection can be achieved using any of the following methods:

* Mimicking user clicks on the screen, for example to steal money from a user's PayPal account.
* Injecting global actions, such as `GLOBAL_ACTION_BACK` (programatically mimicking a physical back button press), to trigger actions on behalf of the user.
* Inserting input into text fields on behalf of the user. This method is used legitimately to auto-fill text fields by applications such as password managers.

## Mitigations

- **M1011 User Guidance** — Users should be warned against granting access to accessibility features, and to carefully scrutinize applications that request this dangerous permission.
- **M1012 Enterprise Policy** — An EMM/MDM can use the Android `DevicePolicyManager.setPermittedAccessibilityServices` method to set an explicit list of applications that are allowed to use Android's accessibility features.

## Detection strategies

- **DET0612 Detection of Input Injection**
  - AN1666 (Android): For Android, detect Input Injection from documented management, network, or vetting evidence; treat state queries as periodic observations rather than real-time events. Correlate Application State via Android Enterprise / EMM [Managed package inventory/status and package metadata]; OS API Execution via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: Accessibility-enabled app NOT IN $AccessibilityAllowList$ invokes performAction() click, global action (GLOBAL_ACTION_BACK/HOME/RECENTS), or insertText() on a UI element belonging to a different foregrounded app — cross-app UI action is the]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: android:EMM (Managed package inventory/status and package metadata); mobile:DynamicAnalysis (Dynamic API/runtime trace: Accessibility-enabled app NOT IN $AccessibilityAllowList$ invokes performAction() click, global action (GLOBAL_ACTION_BACK/HOME/RECENTS), or insertText() on a UI element belonging to a different foregrounded app — cross-app UI action is the).

## Procedure examples

- **S0403 Riltok** (software) — Riltok injects input to set itself as the default SMS handler by clicking the appropriate places on the screen. It can also close or minimize targeted antivirus applications and the device security settings screen.
- **S0406 Gustuff** (software) — Gustuff injects the global action `GLOBAL_ACTION_BACK` to mimic pressing the back button to close the application if a call to an open antivirus application is detected.
- **S0423 Ginp** (software) — Ginp can inject input to make itself the default SMS handler.
- **S0427 TrickMo** (software) — TrickMo can inject input to set itself as the default SMS handler, and to automatically click through pop-ups without giving the user any time to react.
- **S0479 DEFENSOR ID** (software) — DEFENSOR ID can abuse the accessibility service to perform actions on behalf of the user, including launching attacker-specified applications to steal data.
- **S0480 Cerberus** (software) — Cerberus can inject input to grant itself additional permissions without user interaction and to prevent application removal.
- **S0485 Mandrake** (software) — Mandrake abuses the accessibility service to prevent removing administrator permissions, accessibility permissions, and to set itself as the default SMS handler.
- **S0494 Zen** (software) — Zen can simulate user clicks on ads and system prompts to create new Google accounts.
- **S0545 TERRACOTTA** (software) — TERRACOTTA can inject clicks to launch applications, share posts on social media, and interact with WebViews to perform fraudulent actions.
- **S1055 SharkBot** (software) — SharkBot can use input injection via Accessibility Services to simulate user touch inputs, prevent applications from opening, change device settings, and bypass MFA protections.
- **S1062 S.O.V.A.** (software) — S.O.V.A. can programmatically tap the screen or swipe.
- **S1094 BRATA** (software) — BRATA can insert a given string of text into a data field. BRATA can abuse the Accessibility Service to interact with other installed applications and inject screen taps to grant permissions.
- **S1231 GodFather** (software) — GodFather has abused the Accessibility Service to mimic victims’ actions and to redirect victims to its StubActivity when the victims attempt to use the original, legitimate banking application.
- **S9004 Crocodilus** (software) — Crocodilus has the ability to perform clicks, swipes (left, right, up and down) on the screen and actions such as “Back,” “Home,” and “Menu.”
