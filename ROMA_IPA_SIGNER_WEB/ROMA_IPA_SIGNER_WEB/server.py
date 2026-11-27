#!/usr/bin/env python3
"""
ROMA IPA SIGNER local Mac companion service.
Run only on a trusted Mac and preferably a trusted private network.
Set ROMA_TOKEN to a long random secret before starting.
"""
from flask import Flask, request, jsonify, send_file, send_from_directory, abort
from pathlib import Path
from werkzeug.utils import secure_filename
import os, secrets, subprocess, tempfile, uuid, threading, time

BASE = Path(__file__).resolve().parent
WEB = BASE / "web"
SIGN_SCRIPT = BASE / "MacSigner" / "sign-ipa.sh"
TOKEN = os.environ.get("ROMA_TOKEN", "")
MAX_UPLOAD = 2 * 1024 * 1024 * 1024  # 2 GiB total request cap
OUTPUTS = Path(tempfile.gettempdir()) / "roma-ipa-signer-outputs"
OUTPUTS.mkdir(mode=0o700, parents=True, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD
lock = threading.Lock()

def authorized():
    supplied = request.headers.get("X-ROMA-TOKEN", "")
    return bool(TOKEN) and secrets.compare_digest(supplied, TOKEN)

@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")

@app.get("/style.css")
def css():
    return send_from_directory(WEB, "style.css")

@app.get("/app.js")
def js():
    return send_from_directory(WEB, "app.js")

@app.get("/api/health")
def health():
    return jsonify({"status":"online","service":"ROMA IPA SIGNER Mac companion"})

@app.post("/api/sign")
def sign():
    if not authorized():
        return jsonify(error="Unauthorized. Check your Mac service access token."), 401

    required = ("ipa", "p12", "profile")
    if any(name not in request.files for name in required):
        return jsonify(error="Upload IPA, P12 and provisioning profile."), 400

    password = request.form.get("p12_password", "")
    if not password:
        return jsonify(error="P12 password is required."), 400

    job = uuid.uuid4().hex
    work = Path(tempfile.mkdtemp(prefix="roma-job-"))
    try:
        paths = {}
        expected = {"ipa":".ipa", "p12":".p12", "profile":".mobileprovision"}
        for key, suffix in expected.items():
            upload = request.files[key]
            if not upload.filename.lower().endswith(suffix):
                return jsonify(error=f"{key} must use the {suffix} extension."), 400
            dest = work / f"input{suffix}"
            upload.save(dest)
            paths[key] = dest

        output = OUTPUTS / f"ROMA-SIGNED-{job}.ipa"
        # The signing helper reads secrets from stdin; never put passwords in argv/logs.
        env = os.environ.copy()
        proc = subprocess.run(
            [str(SIGN_SCRIPT), str(paths["ipa"]), str(paths["p12"]),
             str(paths["profile"]), str(output)],
            input=(password + "\n" + secrets.token_urlsafe(24) + "\n"),
            text=True, capture_output=True, timeout=900, env=env,
            cwd=str(BASE)
        )
        if proc.returncode != 0 or not output.exists():
            detail = (proc.stderr or proc.stdout or "Signing helper failed")[-5000:]
            return jsonify(error=detail), 422
        return jsonify(message="IPA signing and signature verification completed.",
                       download_url=f"/api/download/{output.name}")
    except subprocess.TimeoutExpired:
        return jsonify(error="Signing timed out after 15 minutes."), 504
    except Exception as exc:
        return jsonify(error=f"Service error: {type(exc).__name__}: {exc}"), 500
    finally:
        # Remove uploaded private signing material and temporary extracted app data.
        import shutil
        shutil.rmtree(work, ignore_errors=True)

@app.get("/api/download/<name>")
def download(name):
    if not authorized():
        abort(401)
    safe = secure_filename(name)
    if safe != name or not safe.startswith("ROMA-SIGNED-") or not safe.endswith(".ipa"):
        abort(404)
    path = OUTPUTS / safe
    if not path.is_file():
        abort(404)
    response = send_file(path, as_attachment=True, download_name=safe,
                         mimetype="application/octet-stream")
    response.call_on_close(lambda: path.unlink(missing_ok=True))
    return response

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set ROMA_TOKEN to a long random secret before launching the server.")
    if not SIGN_SCRIPT.exists():
        raise SystemExit(f"Missing signing helper: {SIGN_SCRIPT}")
    # Bind on LAN so iPhone Safari can reach the Mac. Use only a trusted private Wi-Fi.
    app.run(host="0.0.0.0", port=8765, debug=False)
