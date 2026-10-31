# Security Policy & Threat Model

## Threat Model

**(SheepFox) Zen browser** is engineered around a pragmatic, high-speed everyday threat model for **Zen Browser** (and Mozilla Firefox) comparable to **Brave Shields** combined with **LibreFox** anti-telemetry:

### Protected Out-of-the-Box (Default Profile)
- **Zero Vendor Telemetry:** Mozilla Unified Telemetry, Health Report, Normandy/Nimbus remote studies, crash ping senders, and Privacy-Preserving Attribution (PPA) are disabled and locked.
- **Cross-Site Tracking & Storage Isolation:** Total Cookie Protection (`cookieBehavior = 5`) + network/service-worker state partitioning isolate every domain into its own storage jar.
- **Network-Layer Ad, Tracker & Malware Blocking:** `distribution/policies.json` ("SheepShields") automatically provisions **uBlock Origin** with curated privacy, anti-malware, and query-stripping filter lists.
- **Passive Network Observers:** HTTPS-Only Mode upgrades cleartext navigation, CRLite checks certificate revocations locally without leaking visited domains via OCSP, and DNS-over-HTTPS (Quad9) encrypts DNS lookups.
- **LAN IP Leaks:** WebRTC ICE candidates are restricted to the default route (`media.peerconnection.ice.default_address_only = true`).

### High-Threat Anonymity (`--strict` Override & Tor)
- By default, SheepFox uses granular `privacy.fingerprintingProtection` rather than strict `privacy.resistFingerprinting` (RFP) to preserve 120Hz+ refresh rates, hardware WebGL speed, and site compatibility.
- Users requiring stricter anti-fingerprinting can install with `python3 scripts/install.py --strict`.
- For state-level anonymity or whistleblowing, always use **Tor Browser**.

## Upstream Security Updates

- **Drop-In Mode:** SheepFox deliberately sets `DisableAppUpdate` to **unset/false** in `policies.json` so Zen Browser and stock Firefox continue receiving critical security updates immediately.
- **Fork Build Mode:** Track upstream Gecko/Firefox security advisories and bump `mozbuild/firefox-version.json` promptly upon every Mozilla point release.

## Reporting a Vulnerability

If you discover a security regression caused by a SheepFox preference, policy, installer script, or source patch, please open a security advisory on the repository host before disclosing exploit details publicly.

## Verifying a Release Yourself

Every claim in this repository is checkable without trusting the maintainers:

```bash
python3 mozbuild/scripts/build-configs.py --check   # generated configs match the modules
python3 -m unittest discover -s tests -v            # invariants, policies, patches, installers
git apply --check -p1 patches/0001-*.patch          # patches apply to the pinned Firefox tree
```

`mozbuild/scripts/fetch-source.sh` downloads Mozilla's signed `SHA512SUMS` for the pinned release
and refuses to extract a tarball whose SHA-512 does not match, so a tampered mirror is detected
before any code is compiled.
