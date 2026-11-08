"""Test-only server for e2e/smoke.mjs: Google mode with a fake token check
(the credential is the email address). Never run this anywhere real.

    python desktop/app/e2e/fake_google_server.py <db path> <port>
"""

import sys

import uvicorn

from studentide.app import create_app
from studentide.auth import Config


def fake_google(credential: str) -> dict:
    return {"email": credential, "email_verified": True, "hd": credential.split("@")[1], "name": credential.split("@")[0]}


if __name__ == "__main__":
    app = create_app(sys.argv[1], auth_config=Config(client_id="e2e-fake", secure_cookie=False), verify_google=fake_google)
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
