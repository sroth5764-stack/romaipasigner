#!/bin/bash
# Basic macOS IPA re-sign helper. Only sign software and credentials you are
# authorized to use. Some apps require a more specialized signing pipeline.
set -euo pipefail
[[ "$#" -eq 4 ]] || { echo "Usage: $0 input.ipa certificate.p12 profile.mobileprovision output.ipa" >&2; exit 2; }

IPA="$1"; P12="$2"; PROFILE="$3"; OUTPUT="$4"
for f in "$IPA" "$P12" "$PROFILE"; do [[ -f "$f" ]] || { echo "Missing file: $f" >&2; exit 1; }; done

WORK="$(mktemp -d)"
KEYCHAIN="$WORK/roma.keychain-db"
cleanup(){ security delete-keychain "$KEYCHAIN" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

echo "P12 password:"
IFS= read -r -s P12_PASSWORD; echo
echo "Temporary keychain password:"
IFS= read -r -s KEYCHAIN_PASSWORD; echo

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 900 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security import "$P12" -k "$KEYCHAIN" -P "$P12_PASSWORD" -T /usr/bin/codesign
security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN" >/dev/null

IDENTITY="$(security find-identity -v -p codesigning "$KEYCHAIN" | awk '/^[[:space:]]*[0-9]+\)/ {print $2; exit}')"
[[ -n "$IDENTITY" ]] || { echo "No valid code-signing identity found in P12." >&2; exit 1; }

mkdir "$WORK/unpacked"
ditto -x -k "$IPA" "$WORK/unpacked"
APP="$(find "$WORK/unpacked/Payload" -maxdepth 1 -type d -name '*.app' -print -quit)"
[[ -n "$APP" ]] || { echo "IPA has no Payload/*.app" >&2; exit 1; }

security cms -D -i "$PROFILE" > "$WORK/profile.plist"
APP_ID=$(/usr/libexec/PlistBuddy -c 'Print :Entitlements:application-identifier' "$WORK/profile.plist")
PROFILE_BUNDLE="${APP_ID#*.}"
BUNDLE_ID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Info.plist")
if [[ "$PROFILE_BUNDLE" != "$BUNDLE_ID" && "$PROFILE_BUNDLE" != "*" ]]; then
  echo "Bundle ID mismatch: app=$BUNDLE_ID profile=$PROFILE_BUNDLE" >&2; exit 1
fi

cp "$PROFILE" "$APP/embedded.mobileprovision"
/usr/libexec/PlistBuddy -x -c 'Print :Entitlements' "$WORK/profile.plist" > "$WORK/entitlements.plist"

# Sign embedded frameworks, dylibs and extensions before the containing app.
while IFS= read -r -d '' item; do
  codesign --force --sign "$IDENTITY" --timestamp=none "$item"
done < <(find "$APP" -type d \( -name '*.framework' -o -name '*.appex' \) -prune -print0)

while IFS= read -r -d '' item; do
  codesign --force --sign "$IDENTITY" --timestamp=none "$item"
done < <(find "$APP" -type f -name '*.dylib' -print0)

codesign --force --sign "$IDENTITY" --entitlements "$WORK/entitlements.plist" \
  --generate-entitlement-der --timestamp=none "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

mkdir -p "$(dirname "$OUTPUT")"
(
  cd "$WORK/unpacked"
  ditto -c -k --sequesterRsrc --keepParent Payload "$OUTPUT"
)
echo "Signed IPA created: $OUTPUT"
