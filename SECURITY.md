# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Design guarantees

AgentABI is designed to be safe to run against personal agent state directories:

- It is **offline**: no network requests are made.
- It is **read-only**: scanned directories are never modified.
- It **never reads secret-file contents** (`.env`, `auth.json`, `credentials.json`,
  `*.pem`, `*.key`, `*.pfx`, `*.p12`, `*.jks`, `*.keystore`, `*.gpg`, `*.asc`,
  `id_rsa`, `id_ed25519`, `id_ecdsa`, `id_dsa`, `secrets.*`, `tokens.*`,
  `private*`, `credential*`, `password*`, `cookie*`, `vault*`, `.htpasswd`,
  `.netrc`, `.pgpass`, `*.keyring`, `service-account*.json`,
  `*-credentials.json`); only their existence, safe relative path, and size
  are recorded.
- It **redacts** metadata keys containing `token`, `secret`, `password`, `passwd`,
  `api_key`, `apikey`, `credential`, `cookie`, `bearer`, `private_key`,
  `access_key`, `refresh_token`, `client_secret`, `webhook`, `auth_token`,
  `session_id`, `session_key`, `signing_key`, `encryption_key`, `passphrase`,
  `service_account`, `connection_string`, or `database_url`.
- It never follows symlinks that resolve outside the scanned root, and enforces
  recursion-depth, file-count, and file-size limits.

If you find a violation of any of these guarantees, that is a security bug.

## Reporting a vulnerability

Please report vulnerabilities privately to the maintainers (for example through a
confidential issue) rather than in a public issue. Include reproduction steps and
the affected version. You should receive an acknowledgement within 7 days.
