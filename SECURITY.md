# Security policy

Tuya IR Studio stores gateway Local Keys and optional QR authentication tokens within Home Assistant; it does not require a public dashboard, exposed port or third-party service for ordinary learned-code transmission.

**Never publish** Local Keys, tokens, Client Secrets, full `.storage` files, raw device IDs or real home-network IP addresses in GitHub issues or screenshots. Redact logs carefully. For a security vulnerability, use GitHub private vulnerability reporting when available; do not post credentials publicly.

The panel's profile backup/export workflow is restricted to Home Assistant administrators. Backup files may include profile labels, entity identifiers and imported IR signals, so treat them as private. Backups do not contain your gateway's Local Key or cloud login tokens.

Experimental remote-key imports have been removed. QR sign-in remains available solely to configure a physical Tuya gateway. Only minimum required Tuya API calls should be made for onboarding. Local IR sending does not depend on a recurring external cloud lookup.

**Compatibility:** the presence of stored code and a successful HA service call do not establish that a target device physically reacted. Test before creating consequential automations. Keep a Home Assistant configuration backup before installing a new version.

MIT-licensed project. For disclosure and remediation, open a private vulnerability report if supported.
