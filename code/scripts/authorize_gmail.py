"""Authorize Healthify's project mailbox locally for outbound Gmail API delivery."""

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from google_auth_oauthlib.flow import InstalledAppFlow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_file", type=Path, help="Downloaded Google Desktop OAuth client JSON")
    args = parser.parse_args()
    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_file), scopes=["https://www.googleapis.com/auth/gmail.send"]
    )
    credentials = flow.run_local_server(host="127.0.0.1", port=0, prompt="consent")
    if not credentials.refresh_token:
        parser.exit(1, "Google did not grant offline access. Authorize again with the project mailbox.\n")
    destination = Path.home() / ".healthify" / "gmail-mailbox.json"
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    with NamedTemporaryFile("w", dir=destination.parent, delete=False, encoding="utf-8") as out:
        json.dump({
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
        }, out)
    os.replace(out.name, destination)
    print(f"Gmail authorization saved to {destination}")


if __name__ == "__main__":
    main()
