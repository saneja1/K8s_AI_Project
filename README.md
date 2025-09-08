# Kubernetes Cluster Host Validator

A Streamlit web application that checks whether a remote server meets the minimum requirements to join a Kubernetes cluster via SSH.

## Features

- **Web Interface**: Easy-to-use Streamlit UI for entering host details
- **SSH Authentication**: Supports both password and SSH key authentication
- **System Checks**: Validates CPU cores, memory, and disk space
- **Configurable**: Requirements and SSH settings via environment variables
- **Error Handling**: Clear error messages for common issues

## Requirements

- Python 3.8+
- Access to target Linux servers via SSH

## Quick Start

1. **Clone and setup environment:**
```powershell
git clone <repository-url>
cd "K8s AI Project"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. **Configure environment (optional):**
```powershell
copy .env.example .env
# Edit .env with your preferred defaults (do not commit this file)
```

3. **Run the application:**
```powershell
streamlit run app/streamlit_app.py
```

4. **Open your browser to:** http://localhost:8501

## Usage

1. Enter the target server's IP address or hostname
2. Provide SSH credentials (username + password or SSH key path)
3. Adjust SSH port if needed (default: 22)
4. Click "Test" to check requirements
5. View results and any failure details

## Default Requirements

- **CPU:** 2 logical cores minimum
- **Memory:** 4096 MiB (4 GiB) minimum
- **Disk:** 30 GiB free space on root filesystem (/)

## Configuration

Set these environment variables in `.env` file or system environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_PORT` | 22 | Default SSH port |
| `SSH_USERNAME` | "" | Default SSH username |
| `MIN_CPU_CORES` | 2 | Minimum CPU cores required |
| `MIN_MEMORY_MIB` | 4096 | Minimum memory in MiB |
| `MIN_DISK_GIB` | 30 | Minimum free disk space in GiB |

## Project Structure

```
├── app/
│   └── streamlit_app.py      # Streamlit web interface
├── core/
│   ├── __init__.py
│   └── system.py             # SSH system checks module
├── tests/
│   └── test_system.py        # Unit tests
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## Testing

Run the test suite:
```powershell
pytest -v
```

Run tests with coverage:
```powershell
pytest --cov=core tests/
```

## Security Notes

- Never commit `.env` files containing passwords or private keys
- Use SSH keys instead of passwords when possible
- Validate the target hosts you're connecting to
- Consider using SSH jump hosts for accessing internal networks

## Development

The project follows these conventions:
- Do one task at a time and test before proceeding
- All tests go in the `tests/` directory
- Use type hints and docstrings
- Handle errors gracefully with user-friendly messages

## Troubleshooting

**SSH Connection Failed:**
- Verify host is reachable: `ping <host>`
- Check SSH service: `nmap -p 22 <host>`
- Verify credentials and permissions

**Import Errors:**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**Permission Denied:**
- SSH user needs read access to `/proc/cpuinfo`, `/proc/meminfo`
- No sudo required for basic system checks

## License

This project is for internal use. See your organization's policies for distribution.
