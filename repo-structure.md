# Healthify repository structure

```text
Healthify/
├── README.md
├── .env.example
├── .gitignore
├── pytest.ini
├── run_healthify.bat                 # Windows launcher
├── code/
│   ├── requirements.txt             # Authoritative Python dependencies
│   ├── backend/
│   │   ├── api/
│   │   ├── tests/
│   │   ├── alerts.py
│   │   ├── email_alerts.py
│   │   ├── goals.py
│   │   ├── profile_controller.py
│   │   ├── telemetry_emulator.py
│   │   └── token_store.py
│   ├── frontend/
│   │   ├── rxconfig.py
│   │   ├── healthify/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   ├── state/
│   │   │   └── healthify.py
│   │   └── reflex.lock/
│   ├── scripts/
│   └── specs/
│       ├── features/
│       ├── 01_Requirements.md
│       ├── roadmap.md
│       └── tech-stack.md
├── data/                            # Local/sample data
├── docs/
│   └── Reports/
└── .github/
    └── ISSUE_TEMPLATE/
```

The Reflex app is launched from `code/frontend`, where `rxconfig.py` is located.
The root virtual environment is `.venv`, and dependencies are installed from
`code/requirements.txt`.
