# ROMA IPA SIGNER — Safari Web Panel

A mobile-first Safari control panel plus a local macOS signing service. Safari is the user interface; the Mac performs Apple's certificate-based signing with `security`, `codesign`, and `ditto`.

## Architecture

- `web/`: responsive black/crimson Safari panel.
- `server.py`: authenticated Flask service on your Mac.
- `MacSigner/sign-ipa.sh`: basic certificate-based signing helper.

**This is a starter workflow, not a universal IPA re-signing service.** Apps with extensions, Watch apps, special entitlements, nested profiles, encrypted/protected resources, or vendor-specific requirements may need a specialized signing pipeline. The helper does not bypass Apple provisioning or signature checks.

## Requirements

- A Mac with Xcode Command Line Tools installed (`xcode-select --install`).
- Python 3.10+.
- A valid P12 containing a code-signing certificate and its private key.
- A matching provisioning profile and an IPA you are authorized to sign.
- iPhone and Mac on the same trusted private Wi-Fi network.

## Setup on the Mac

1. Extract this ZIP on your Mac.
2. Open Terminal in the extracted folder.
3. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Make the helper executable:

```bash
chmod 700 MacSigner/sign-ipa.sh
```

5. Generate a long random access token:

```bash
export ROMA_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "$ROMA_TOKEN"
```

Keep this token private. Enter it in Safari's Access Token field.

6. Start the service:

```bash
python3 server.py
```

The service listens on port `8765`. Find your Mac's private Wi-Fi IP address in System Settings → Wi-Fi → Details, then open:

`http://MAC-LAN-IP:8765`

Use the actual private IP in place of `MAC-LAN-IP`. Keep the service on a trusted network; do not port-forward it or expose it to the public internet.

## Signing from Safari

1. Open the panel on your iPhone Safari.
2. Select your `.ipa`, `.p12`, and `.mobileprovision`.
3. Enter the P12 password and the Mac service access token.
4. Tap **PREPARE & SIGN**.
5. When the Mac finishes signing and verification, tap **DOWNLOAD SIGNED IPA**.

The service deletes uploaded source files and temporary signing work after the job. The resulting IPA is deleted after its download response closes. The P12 password is passed to the helper over standard input, not command-line arguments. Use only a trusted private Wi-Fi network.

## Security notes

- Do not deploy this starter server to a public host.
- Do not share your P12, private key, P12 password, or access token.
- The built-in Flask development server is intended for local testing, not production. A production deployment requires HTTPS, hardened hosting, authentication, rate limiting, audit controls, and careful secret handling.
- The app/profile/certificate must be compatible. A successful local signature verification does not guarantee that an app can be installed or launched on a particular device.
- The panel currently has no account system, remote hosting, or cloud storage.
