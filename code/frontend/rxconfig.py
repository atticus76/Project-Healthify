import sys
from pathlib import Path

import reflex as rx


CODE_ROOT = Path(__file__).resolve().parent.parent
if str(CODE_ROOT) not in sys.path:
	sys.path.insert(0, str(CODE_ROOT))


config = rx.Config(
	app_name="dashBoardUI",
	app_module_import="dashBoardUI.dashBoardUI",
)
