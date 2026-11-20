import os
import sys
from pathlib import Path

import reflex as rx


CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
	sys.path.insert(0, str(CODE_ROOT))


origin = os.getenv("RENDER_EXTERNAL_URL")
public_urls = {"api_url": origin, "deploy_url": origin} if origin else {}
config = rx.Config(app_name="healthify", **public_urls)
