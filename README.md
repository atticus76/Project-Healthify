# HealthTrack (Healthify)

## Getting Started

You need **Python 3.12** (see [tech-stack.md](code/specs/tech-stack.md)) and Windows PowerShell. Reflex downloads its own JavaScript tooling the first time it runs, so you don't need Node.

### 1. Install Python 3.12

```powershell
py install 3.12        # Python install manager; or use the python.org installer
py list                # 3.12 should be listed
```

### 2. Create the virtual environment (once)

From the repo root:

```powershell
py -V:3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell refuses to run `Activate.ps1`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### 3. (Optional) Google Health credentials

Only needed to connect a real wearable on `/devices`. Copy `.env.example` to `.env` and fill in `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Without it, use the **Telemetry Emulator**.

### 4. Run the app

```powershell
.venv\Scripts\Activate.ps1
cd code\frontend
reflex run
```

Open http://localhost:3000. The backend runs on port 8000. The first run takes a minute while Reflex installs its frontend packages. Stop the app with `Ctrl+C`.

### 5. Run the tests

From the repo root, with the venv active:

```powershell
pytest
```

### Troubleshooting

- **`No Python at 'C:\Program Files\Python39\python.exe'`** or similar: your `.venv` was built from a Python that's gone. Delete `.venv` and redo step 2.
- **Port 3000 or 8000 already in use:** another `reflex run` is still open. Close it, or use `reflex run --frontend-port 3001 --backend-port 8001`.
- **`code/frontend/reflex.lock/` shows as modified after running:** Reflex rewrites these files' line endings. Discard the change (`git checkout -- code/frontend/reflex.lock`) unless you changed dependencies.

---

## Working Notes

Group Members:
Atticus Crook
Antsey Hans
Mohamed Dawoud
Yogi Chopra



Project: HealthTrack: A Real-Time Health Monitoring System Using Wearable Devices -
Using wearable technologies and bioinformatics (? heart rate monitor? Apple watch? I might have an old one I can steal from my dad, should provide loads of info about heart rate, heart rate variability, sleep w/ iPhone or watch)

Do we really have to use a real watch? What about an engine or a simulator?

That could be fine, we could make something that simulates the output of a smart devices data as it gets routed to application.


Other bioinformatic logs – diet, sleep, physical activity, 

Features –
Daily suggestions for health (lacking certain nutrients in diet, poor sleep -> go light on workout vs good sleep -> go hard in workout, spO2 sleep apnea detector)
Connect to a food database to gather info on dietary nutrition(calories, macros, etc.)
SQL based user credential, using a free or lightweight variant (like MySQL, SQLite, DuckDB, or at the extreme level Azure SQL)

Do we want to do a web app? Or a windowed cross-platform app? Mobile app? Apple apps cost liek 100$ per year and are pretty hard to get up. What OS’ is everyone running? I have a windows machine I can use if I need

What frameworks/stacks/languages are you all familiar w/. 
User Stories –

Feature: User Login
User Story
    Scenario: Successful login with valid credentials 
    Given the user is on the login page
    And clicks the login button
    When the user enters a valid username or password
    Then the users home page is displayed

  Scenario: Unsuccessful login with invalid credentials
    Given the user is on the login page
    And clicks the login button
    When the user enters an invalid username or password
    Then an error message should be displayed
    And the users login attempt is tracked 

Feature: Connected Devices Page
User Story
    Scenario: Trying to sync a new device for the first time.
    Given the user opens the application and chooses to use a wearable device.
    And the device is discoverable via Bluetooth. (Or maybe wifi later)
    When the user tries to connect a device that wasn't connected before.
    Then it fails to connect as it can't see the device.
    And takes the user back to the connected devices page.

  Scenario: [Alternate, failure, or boundary scenario name]
    Given [initial state or precondition]
    And [relevant business rule or condition]
    When [user action or event]
    Then [observable and testable result]
    And [additional result, if needed]

Feature: [Feature name]
User Story
    Scenario: [Successful scenario name]
    Given [initial state or precondition]
    And [additional precondition, if needed]
    When [user action or event]
    Then [observable and testable result]
    And [additional result, if needed]

  Scenario: [Alternate, failure, or boundary scenario name]
    Given [initial state or precondition]
    And [relevant business rule or condition]
    When [user action or event]
    Then [observable and testable result]
    And [additional result, if needed]

Review - 
	Does each story identify a specific user, goal, and value?
Is the story small enough to test independently?
Does each scenario describe one primary behavior?
Are the Then outcomes observable and testable?
Does the alternate scenario examine a meaningful condition?
Can you identify which business rule is verified?


