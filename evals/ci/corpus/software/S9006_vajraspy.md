# S9006 — VajraSpy

- **Type:** software (malware)
- **Domain:** Mobile ATT&CK
- **Platforms:** Android
- **ATT&CK URL:** https://attack.mitre.org/software/S9006
- **Last modified:** 2026-05-12

## Description

VajraSpy is Android malware distributed via trojanized messaging and news applications. It has been used to target individuals in Pakistan and India since at least 2021 and has been delivered through the Google Play Store, malicious domains, and other uncontrolled distribution channels. VajraSpy is attributed with high confidence to Patchwork which has used the malware to conduct targeted espionage, primarily against devices in Pakistan.

## Techniques used

- **T1409 Stored Application Data** — VajraSpy has collected messages in WhatsApp, WhatsApp Business, and Signal.
- **T1417.001 Input Capture: Keylogging** — VajraSpy has logged keystrokes of an infected device.
- **T1418 Software Discovery** — VajraSpy has obtained and exfiltrated a list of installed applications.
- **T1420 File and Directory Discovery** — VajraSpy has searched for files with specific extensions, such as .txt, .jpg, .Om4a, .aac and .opus, before exfiltration.
- **T1422.002 System Network Configuration Discovery: Wi-Fi Discovery** — VajraSpy has scanned for Wi-Fi networks.
- **T1426 System Information Discovery** — VajraSpy has requested for `android.permission.READ_PHONE_STATE` to collect information about the device.
- **T1429 Audio Capture** — VajraSpy has recorded surrounding audio and phone calls from WhatsApp, WhatsApp Business, Signal, and Telegram by requesting `android.permission.RECORD_AUDIO`.
- **T1430 Location Tracking** — VajraSpy has exfiltrated the device’s location. VajraSpy has also requested for `android.permission.ACCESS_FINE_LOCATION` and `android.permission.ACCESS_COARSE_LOCATION` to obtain the device’s location.
- **T1453 Abuse Accessibility Features** — VajraSpy has exploited accessibility features to intercept and exfiltrate communication from WhatsApp, WhatsApp Business and Signal and to automatically enable necessary permissions on the user’s behalf.
- **T1461 Lockscreen Bypass** — VajraSpy has requested for `android.permission.DISABLE_KEYGUARD` to disable the device lock screen password.
- **T1481.002 Web Service: Bidirectional Communication** — VajraSpy has used Firebase and Google Cloud Storage to send and receive C2 communications and to send collected data.
- **T1512 Video Capture** — VajraSpy has captured pictures using the device’s camera by requesting for `android.permission.CAMERA`.
- **T1517 Access Notifications** — VajraSpy has monitored and exfiltrated notifications from messaging applications and from SMS messages.
- **T1533 Data from Local System** — VajraSpy has collected files with specific extensions, such as .txt, .jpg, .Om4a, .aac and .opus, before exfiltration. VajraSpy has also requested for `android.permission.WRITE_EXTERNAL_STORAGE` and `android.permission.READ_EXTERNAL_STORAGE`.
- **T1616 Call Control** — VajraSpy has requested for `android.permission.CALL_PHONE`.
- **T1636.002 Protected User Data: Call Log** — VajraSpy has collected and exfiltrated the call log.
- **T1636.003 Protected User Data: Contact List** — VajraSpy has collected and exfiltrated the contact list.
- **T1636.004 Protected User Data: SMS Messages** — VajraSpy has collected and exfiltrated SMS messages.
- **T1636.005 Protected User Data: Accounts** — VajraSpy has requested for `android.permission.GET_ACCOUNTS`.
- **T1639.001 Exfiltration Over Alternative Protocol: Exfiltration Over Unencrypted Non-C2 Protocol** — VajraSpy has used Retrofit, an HTTP client for Android, to upload unencrypted data to the C2 server via HTTP.
- **T1646 Exfiltration Over C2 Channel** — VajraSpy has exfiltrated captured data to C2 via POST requests.
- **T1655 Masquerading** — VajraSpy has masqueraded as messaging and news applications.
- **T1660 Phishing** — VajraSpy has used a romance trap scam to convince victims into downloading the trojanized application.

## Used by

- **G0040 Patchwork** (group)
