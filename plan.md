

# Implementation Requirements: Adding New Hosts to a Kubernetes Cluster
## 6. Streamlit UI (Step 1)
- [x] 6.1 Create `app/streamlit_app.py` with:
	- [x] 6.1.1 Title and description. ✅
	- [x] 6.1.2 Static text above the button: "Does this server meet minimum cluster requirements?" ✅
	- [x] 6.1.3 Inputs: host IP/DNS, SSH username, auth method (password or key), password or key path, port (default from config), and a "Test" button. ✅
	- [x] 6.1.4 On "Test" click, call `core.system.check_requirements(...)` and show a spinner while running. ✅
	- [x] 6.1.5 Display result message:
		- Success: "Congratulations, your host meets the minimum server requirements to be part of the cluster." ✅
		- Failure: "Your host doesn't meet minimum server requirements to be part of the cluster. Please ensure: CPU=..., Memory=..., Disk=..." ✅
	- [x] 6.1.6 Also display the measured values and any specific failing reasons. ✅
	- [x] 6.1.7 Handle and show user-friendly errors (SSH unreachable, auth failure, timeouts). ✅ent defines a step-by-step, testable implementation plan to build a Streamlit tool that verifies whether a given server meets the minimum requirements to be added to a Kubernetes cluster. Follow the numbered steps sequentially. Do one task at a time, commit, and test before starting the next.

Note on naming: We will use `system.py` (lowercase) as the canonical filename (instead of `System.py`).

## 0. Working Style and Conventions
- [x] 0.1 Do exactly one task at a time; do not start another until tests for the current one pass.
- [x] 0.2 Keep the workspace neat and clean (use clear directories, avoid committing secrets, add a `.gitignore`).
- [x] 0.3 Place all test files under `tests/`.
- [x] 0.4 Use PowerShell-friendly commands on Windows where applicable.

## 1. Assumptions and Scope
- [x] 1.1 Target hosts are Linux servers reachable via SSH on port 22 (configurable).
- [x] 1.2 We use SSH username/password or SSH private key for authentication.
- [x] 1.3 Minimum requirements are configurable; defaults are provided and can be changed without code edits.
- [x] 1.4 Streamlit is used for the UI; Paramiko is used for SSH from Python.

Default minimum requirements (edit in configuration later as needed):
- CPU cores (logical): 2
- Memory: 4 GiB (4096 MiB)
- Disk space on root (`/`): 30 GiB free

## 2. Project Structure
- [x] 2.1 Create/ensure the following layout (only create files when their step is reached):
	- `app/streamlit_app.py` – Streamlit UI. ✅
	- `core/system.py` – SSH checks module. ✅
	- `tests/` – All tests go here. ✅
	- `requirements.txt` – Python dependencies. ✅
	- `.env.example` – Example environment variables. ✅
	- `.gitignore` – Ignore venv, secrets, and build artifacts. ✅
	- `README.md` – Quick start and usage notes. ✅

## 3. Python Virtual Environment
- [x] 3.1 If `.venv/` does not exist in the project root, create it.
- [x] 3.2 Activate the virtual environment and install dependencies once `requirements.txt` exists.

PowerShell (Windows) commands:
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Deactivate when done:
```
deactivate
```

## 4. Dependencies
- [ ] 4.1 Add and pin required packages in `requirements.txt`:
	- `streamlit` – UI
	- `paramiko` – SSH
	- `python-dotenv` – Load environment variables from `.env` (optional but recommended)
	- `pytest` – Unit tests
	- `pytest-mock` – Mocking for tests

Example `requirements.txt` content (versions can be adjusted):
```
streamlit>=1.36
paramiko>=3.4
python-dotenv>=1.0
pytest>=8.0
pytest-mock>=3.14
```

## 5. Configuration
- [ ] 5.1 Support configuration via environment variables (read with `python-dotenv` if `.env` is present):
	- `SSH_PORT` (default `22`)
	- `SSH_USERNAME` (optional default)
	- `SSH_PASSWORD` (optional; avoid committing)
	- `SSH_KEY_PATH` (optional path to private key)
	- `MIN_CPU_CORES` (default `2`)
	- `MIN_MEMORY_MIB` (default `4096`)
	- `MIN_DISK_GIB` (default `30`)
- [ ] 5.2 Provide `.env.example` with placeholders; never commit an actual `.env` with secrets.

## 6. Streamlit UI (Step 1)
- [ ] 6.1 Create `app/streamlit_app.py` with:
	- [ ] 6.1.1 Title and description.
	- [ ] 6.1.2 Static text above the button: "Does this server meet minimum cluster requirements?"
	- [ ] 6.1.3 Inputs: host IP/DNS, SSH username, auth method (password or key), password or key path, port (default from config), and a "Test" button.
	- [ ] 6.1.4 On "Test" click, call `core.system.check_requirements(...)` and show a spinner while running.
	- [ ] 6.1.5 Display result message:
		- Success: "Congratulations, your host meets the minimum server requirements to be part of the cluster."
		- Failure: "Your host doesn’t meet minimum server requirements to be part of the cluster. Please ensure: CPU=..., Memory=..., Disk=..."
	- [ ] 6.1.6 Also display the measured values and any specific failing reasons.
	- [ ] 6.1.7 Handle and show user-friendly errors (SSH unreachable, auth failure, timeouts).

Acceptance criteria:
- The page renders with the heading and the exact prompt text above the button.
- Inputs exist for host, username, auth, and port; "Test" triggers a backend call.
- Success/failure messages match the required wording and show measured metrics.

Testing (manual + basic curl):
- Run the app and confirm the page loads:
```
streamlit run app/streamlit_app.py
```
- From another PowerShell, check the server responds (HTTP 200) on localhost:
```
curl http://localhost:8501/
```
- Perform a manual test with a known reachable host (or a test VM) and verify messages.

## 7. SSH Checks Module (Step 2)
- [x] 7.1 Create `core/system.py` with a function similar to:
	- `check_requirements(host: str, username: str, password: str | None, key_path: str | None, port: int = 22, timeouts: dict | None = None) -> dict` ✅
- [x] 7.2 Responsibilities:
	- [x] 7.2.1 Establish SSH connection using Paramiko (password or private key, port configurable). ✅
	- [x] 7.2.2 Gather metrics remotely (non-root):
		- CPU cores: `nproc` (fallback to parsing `/proc/cpuinfo`). ✅
		- Memory MiB: parse `MemAvailable` or `MemTotal` from `/proc/meminfo`. ✅
		- Disk GiB free on `/`: `df -BG /` and parse available GB. ✅
	- [x] 7.2.3 Compare values against configured thresholds and build a result object:
		- `{"ok": bool, "cpu_cores": int, "memory_mib": int, "disk_gib_free": int, "failures": [str]}` ✅
	- [x] 7.2.4 Ensure timeouts and safe error handling; return clear errors for unreachable host, auth failure, and command errors. ✅

Acceptance criteria:
- Can connect to a reachable Linux host using password or key.
- Returns structured results with all three metrics and an overall `ok` flag.
- Gracefully handles and reports common errors.

Testing:
- [ ] 7.3 Add unit tests in `tests/test_system.py`:
	- Mock Paramiko to simulate: success path, auth failure, unreachable host, and insufficient resources.
	- Assert the result structure and messages.
- Optional: If you have a test VM, run a real check to verify parsing logic.

## 8. Decision Messaging (Step 3)
- [ ] 8.1 In the Streamlit app, branch on `result["ok"]`:
	- [ ] 8.1.1 If True: display the exact success message required.
	- [ ] 8.1.2 If False: display the exact failure message and list the required thresholds (CPU, Memory, Disk) and what was observed.

Acceptance criteria:
- Messages exactly match the required text and include thresholds where relevant.

## 9. Integration (Step 4)
- [ ] 9.1 Wire `app/streamlit_app.py` to import and call `core.system.check_requirements` on button click.
- [ ] 9.2 Ensure sensitive inputs (password) are masked in the UI and never logged.
- [ ] 9.3 Display a summary panel with metrics and any failure reasons.

Testing:
- [ ] 9.4 Manual run: use a host that passes and one that fails to validate both branches.

## 10. Error Handling, Edge Cases, and Security
- [ ] 10.1 Edge cases:
	- Empty host input.
	- DNS resolution failure or closed port.
	- Wrong credentials.
	- Systems without `nproc` (fallback implemented).
	- Non-standard shells or minimal distros.
	- Very large memory/disk values (ensure integer handling).
- [ ] 10.2 Security:
	- Never commit secrets; use environment variables or Streamlit secrets.
	- If using password auth, prefer short-lived sessions; close SSH cleanly.
	- Validate and sanitize user input (basic host/IP validation).
- [ ] 10.3 Timeouts and retries:
	- Apply reasonable SSH connect timeout (e.g., 8–15s) and command timeout.

## 11. Deliverables and Acceptance
- [ ] 11.1 Functional Streamlit app meeting UI and messaging requirements.
- [ ] 11.2 `core/system.py` providing SSH checks with configurable thresholds.
- [ ] 11.3 Unit tests under `tests/` covering happy path and key failure scenarios (auth, unreachable, insufficient resources).
- [ ] 11.4 `requirements.txt`, `.env.example`, `.gitignore`, and `README.md` explaining setup and usage.
- [ ] 11.5 Ability to run locally with `.venv` and verify via browser and `curl`.

## 12. How to Test After Each Task
- [ ] 12.1 After venv/deps: import packages and run `pytest -q` (even if no tests yet, it should pass with 0 tests).
- [ ] 12.2 After Streamlit skeleton: start the app; `curl http://localhost:8501/` returns HTML.
- [ ] 12.3 After `system.py`: run unit tests (mocks) and, if possible, a real host check.
- [ ] 12.4 After integration: test pass and fail paths from the UI.

## 13. Optional Enhancements (Defer until core is done)
- [ ] 13.1 Save past results in a local JSON or SQLite for audit.
- [ ] 13.2 Add selectable disk mount target (e.g., `/var/lib/kubelet`).
- [ ] 13.3 Add an API endpoint (FastAPI) for automated checks separate from the UI.
- [ ] 13.4 Add CI for linting/tests (e.g., GitHub Actions).

---

## Quick Start (once implemented)
1) Create and activate venv, then install dependencies:
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
2) Copy `.env.example` to `.env` and fill in any defaults you want (do not commit `.env`).
3) Run the UI:
```
streamlit run app/streamlit_app.py
```
4) Open the URL shown (usually http://localhost:8501). Enter host details and click "Test".
5) Run tests:
```
pytest -q
```

Notes:
- All test files must be placed under `tests/`.
- Keep commits small and tied to single tasks; run tests after each.

















