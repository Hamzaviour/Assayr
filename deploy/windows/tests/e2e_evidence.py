"""Check a running Assayr from outside: sign-in, 93 controls, a clean upload verified, EICAR rejected.

Usage: python e2e_evidence.py BASE_URL EMAIL PASSWORD [--no-av]
Standard library only, so it runs with the Python bundled in the installation.
"""

import http.cookiejar
import json
import ssl
import sys
import time
import urllib.request
import uuid

BASE, EMAIL, PASSWORD = sys.argv[1:4]
CHECK_AV = "--no-av" not in sys.argv
# The EICAR test string, assembled at run time so no antivirus flags this script.
EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-" + "TEST-FILE!$H+H*").encode()

context = ssl._create_unverified_context()  # noqa: S323  local self-signed certificate
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(jar)
)


def fail(message: str) -> None:
    print(f"FAILED: {message}")
    sys.exit(1)


def call(method: str, path: str, body: bytes | None = None, content_type: str | None = None):
    request = urllib.request.Request(BASE + path, data=body, method=method)
    if content_type:
        request.add_header("Content-Type", content_type)
    csrf = next((c.value for c in jar if c.name == "assayr_csrf"), None)
    if csrf and method != "GET":
        request.add_header("X-CSRF-Token", csrf)
    with opener.open(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def upload(control: str, slot: str, name: str, data: bytes) -> str:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    link = call("POST", f"/api/v1/controls/{control}/slots/{slot}/artefacts", body,
                f"multipart/form-data; boundary={boundary}")  # fmt: skip
    return link["id"]


def settled(link_id: str, seconds: int = 120) -> dict:
    for _ in range(seconds):
        link = call("GET", f"/api/v1/artefact-links/{link_id}")
        if link["state"] != "verifying":
            return link
        time.sleep(1)
    fail(f"evidence {link_id} was never verified (is the worker running?)")


def malware_rule(link: dict) -> str:
    """Status of the malware-scan rule (V-AV) in the verification run."""
    return next((r["status"] for r in link["rules"] if r["code"] == "V-AV"), "missing")


call("POST", "/api/v1/auth/login", json.dumps({"email": EMAIL, "password": PASSWORD}).encode(), "application/json")
total = call("GET", "/api/v1/controls/summary")["total"]
if total != 93:
    fail(f"expected 93 controls, got {total}")

control = call("GET", "/api/v1/controls/A.5.1")
slot = control["slots"][0]["id"]
policy = b"Acme Financial Services\nInformation Security Policy\nVersion 1.0\nApproved by: E2E Admin\n"
# A tiny text file may still fail content rules (dates, approvals); what matters here is that the worker
# verified it and the malware scanner passed it.
clean = settled(upload("A.5.1", slot, "policy.txt", policy))
if CHECK_AV and malware_rule(clean) != "pass":
    fail(f"the malware scan did not pass the clean file: {malware_rule(clean)}")
print(f"Clean document verified by the worker: {clean['state']}, malware scan {malware_rule(clean)}")

if CHECK_AV:
    infected = settled(upload("A.5.1", slot, "eicar.txt", EICAR))
    if infected["state"] != "rejected" or malware_rule(infected) != "fail":
        fail(f"the EICAR test file ended {infected['state']} with malware scan {malware_rule(infected)}")
    print("EICAR test file rejected by the malware scan")

print("Evidence checks passed")
