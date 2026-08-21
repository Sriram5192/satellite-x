# Security Policy

## Never commit

- passwords or session tokens;
- Space-Track, SMS, government or cloud credentials;
- Ed25519 private keys or AES evidence keys;
- farmer identity/phone/Aadhaar;
- raw evidence photos or production databases.

Use a secret manager and environment references. `.env` files are ignored.

## Reporting a vulnerability

Do not open a public issue containing exploit details or personal data. Contact the repository owner privately and include affected version, reproduction steps, impact and suggested mitigation.

## Supported demo scope

The repository is a verified demo/research build. External production activation remains fail-closed until credentials, hardware, measurements and field acceptance are supplied.
