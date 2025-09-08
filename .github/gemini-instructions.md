# Gemini AI Agent Instructions for K8s Host Validator

This document provides guidelines for the Gemini AI agent when assisting with this project.

## 1. Project Overview
This is a Streamlit web application that validates remote servers for Kubernetes cluster readiness via SSH. The architecture follows a clean separation of concerns:
- **UI**: Streamlit in `app/streamlit_app.py`
- **Core Logic**: SSH-based system checking in `core/system.py`
- **Testing**: Pytest-based unit tests in `tests/`
- **Configuration**: Driven by environment variables, with `.env.example` as a template.

## 2. Core Mandates & Behavior

- **Adhere to Conventions**: Rigorously follow the existing project conventions. The primary sources of truth for style and structure are `app/streamlit_app.py` and `core/system.py`.
- **Verify Dependencies**: Before using a library, ensure it is listed in `requirements.txt`. The key libraries for this project are `streamlit`, `paramiko`, and `pytest`.
- **Environment-Driven Configuration**: All changes to validation logic (e.g., CPU cores, memory thresholds) should be done by modifying the `.env` file, not by hardcoding values.
- **Testing is Mandatory**: Before submitting any change, run the existing test suite to ensure no regressions have been introduced. New features should be accompanied by new tests.
- **Explain Critical Commands**: Before running any shell command that modifies the file system or system state (like `git commit`, `rm`, etc.), provide a clear and concise explanation of what it does.

## 3. Development & Testing Workflow

When asked to perform a task (e.g., fix a bug, add a feature), follow this sequence:

1.  **Understand the Context**: Use `read_file` and `glob` to analyze the relevant files (`app/*`, `core/*`, `tests/*`).
2.  **Formulate a Plan**: Create a clear plan of action. For code changes, this includes which files to modify and how.
3.  **Implement Changes**: Use `write_file` or `replace` to modify the code, adhering to the project's style.
4.  **Verify with Tests**: Run the project's test suite to validate the changes. The primary test commands are:
    - **Run all tests**: `pytest -v`
    - **Run tests with coverage**: `pytest --cov=core tests/`

## 4. Critical Implementation Details

- **SSH Logic**: The core of the application is in `core/system.py`. It uses the `paramiko` library for all SSH operations.
    - **Authentication**: Must support both password and SSH key methods.
    - **Remote Commands**: Use a Linux-first approach (`nproc`, `cat /proc/meminfo`, `df -BG /`) with fallbacks for Windows where appropriate.
    - **Error Handling**: Gracefully handle `paramiko` exceptions (e.g., `AuthenticationException`, `SSHException`) and return clear error messages in the result dictionary.
- **Streamlit UI**: The UI in `app/streamlit_app.py` should remain clean and focused.
    - **User Input**: Clearly defined input fields for host, credentials, and port.
    - **Results Display**: Use `st.metric()` for measured values and provide clear, user-friendly success or failure messages based on the dictionary returned from `core.system.check_requirements`.
- **Return Format**: Communication between the UI and the core logic is done via a standardized dictionary. Always maintain this structure:
  ```python
  {
      'ok': bool,
      'cpu_cores': int,
      'memory_mib': int,
      'disk_gib_free': int,
      'failures': list[str],
      'error': str | None
  }
  ```

## 5. Security
- **No Hardcoded Credentials**: Never write passwords or private keys directly in the code.
- **Use `.env` for Secrets**: Sensitive information should be managed via the `.env` file, which is listed in `.gitignore`.
- **SSH Host Key Policy**: The project currently uses `paramiko.AutoAddPolicy()` for convenience. Be aware of this and do not change it without explicit instruction.
