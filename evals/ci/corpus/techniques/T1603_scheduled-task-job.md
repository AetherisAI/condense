# T1603 — Scheduled Task/Job

- **Type:** technique
- **Domain:** Mobile ATT&CK
- **Tactics:** Execution, Persistence
- **Platforms:** Android, iOS
- **ATT&CK URL:** https://attack.mitre.org/techniques/T1603
- **Last modified:** 2025-10-24

## Description

Adversaries may abuse task scheduling functionality to facilitate initial or recurring execution of malicious code. On Android and iOS, APIs and libraries exist to facilitate scheduling tasks to execute at a specified date, time, or interval.

On Android, the `WorkManager` API allows asynchronous tasks to be scheduled with the system. `WorkManager` was introduced to unify task scheduling on Android, using `JobScheduler`, `GcmNetworkManager`, and `AlarmManager` internally. `WorkManager` offers a lot of flexibility for scheduling, including periodically, one time, or constraint-based (e.g. only when the device is charging).

On iOS, the `NSBackgroundActivityScheduler` API allows asynchronous tasks to be scheduled with the system. The tasks can be scheduled to be repeating or non-repeating, however, the system chooses when the tasks will be executed. The app can choose the interval for repeating tasks, or the delay between scheduling and execution for one-time tasks.

## Detection strategies

- **DET0707 Detection of Scheduled Task/Job**
  - AN1829 (Android): For Android, detect Scheduled Task/Job primarily during application vetting or controlled analysis rather than assuming a live device SOC feed. Correlate OS API Execution via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: App enqueues WorkManager work, schedules JobScheduler job, or sets AlarmManager with repeating interval NOT IN $ApprovedSchedulerApps$]; Scheduled Job Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: Scheduled task execution creates file, accesses sensor, or initiates network connection immediately after firing, with no recent user interaction triggering the task]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: App enqueues WorkManager work, schedules JobScheduler job, or sets AlarmManager with repeating interval NOT IN $ApprovedSchedulerApps$); mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: Scheduled task execution creates file, accesses sensor, or initiates network connection immediately after firing, with no recent user interaction triggering the task).
  - AN1830 (iOS): For iOS, detect Scheduled Task/Job primarily during application vetting or controlled analysis rather than assuming a live device SOC feed. Correlate OS API Execution via Application Vetting / Instrumented Dynamic Analysis [Dynamic API/runtime trace: Managed app creates NSBackgroundActivityScheduler activity or registers BGTask with repeating=true or deferred interval outside $ApprovedSchedulerApps$ function]; Scheduled Job Creation via Application Vetting / Forensic Acquisition [Dynamic filesystem trace or acquired app-container/filesystem artifacts: Scheduled task execution produces network, local-write, or sensor artifact while app_state=background or device_locked=true without user trigger]. Alert on a sequence or state change inconsistent with the device/app baseline, approved management policy, or expected user workflow; do not infer unobserved API calls, file/process activity, or payload content from management state alone. Log sources: mobile:DynamicAnalysis (Dynamic API/runtime trace: Managed app creates NSBackgroundActivityScheduler activity or registers BGTask with repeating=true or deferred interval outside $ApprovedSchedulerApps$ function); mobile:ForensicArtifacts (Dynamic filesystem trace or acquired app-container/filesystem artifacts: Scheduled task execution produces network, local-write, or sensor artifact while app_state=background or device_locked=true without user trigger).

## Procedure examples

- **S0536 GPlayed** (software) — GPlayed has used timers to enable Wi-Fi, ping the C2 server, register the device with the C2, and register wake locks on the system.
- **S0545 TERRACOTTA** (software) — TERRACOTTA has used timer events in React Native to initiate the foreground service.
- **S0558 Tiktok Pro** (software) — Tiktok Pro has contained an alarm that triggers every three minutes and timers for communicating with the C2.
- **S1083 Chameleon** (software) — Chameleon has used the AlarmManager API to schedule tasks.
- **S1231 GodFather** (software) — GodFather has utilized a timer to initiate a WebSocket connection.
