# Security Policy 🛡️

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| < 2.0   | :x:                |

---

## Reporting Vulnerabilities

Security is taken very seriously in **PulseMusic**.

If you discover a security vulnerability, RCE vector, or session leakage in PulseMusic:
1. Please **DO NOT** create a public issue.
2. Contact the maintainer directly via Telegram: **[@Zcziiyy](https://t.me/Zcziiyy)** or via GitHub Security Advisory.
3. Provide details and proof of concept.
4. We will investigate and publish a patch promptly.

---

## Best Practices
- Never share your Telegram Pyrogram `STRING_SESSION` or `BOT_TOKEN` in public groups.
- Use MongoDB IP whitelists and complex database passwords.
- Run the assistant client using a dedicated spare Telegram account.
