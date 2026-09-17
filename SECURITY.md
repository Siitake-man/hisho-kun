# Security Policy

## Overview

Hisho-kun is designed as a **local-first** application. Sync and integrations are intended to run on your own machine without a cloud relay for your data.

## Secrets and credentials

- Do **not** commit secrets: `.env`, `.sync_token`, API keys, bearer tokens, private keys, or similar files.
- Prefer environment variables or local secret stores for bearer tokens and other credentials.
- Rotate any credential that may have been exposed.

## Reporting a vulnerability

If you discover a security issue:

1. Prefer [GitHub private vulnerability reporting](https://github.com/Siitake-man/hisho-kun/security/advisories/new) if enabled for this repository.
2. Otherwise open a GitHub Issue with a high-level description (avoid posting secrets or exploit details publicly), or contact the maintainer privately.

Please allow reasonable time for a fix before any public disclosure.