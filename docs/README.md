K8s AI Project/
├── 📁 app/                          ✅ GOOD - Application code
│   └── dashboard.py
├── 📁 core/                         ✅ GOOD - Business logic
│   ├── __init__.py
│   └── system.py
├── 📁 tests/                        ✅ GOOD - All test files organized
│   ├── test_system.py
│   ├── test_windows.py
│   ├── test-pod.yaml
│   └── vm_specs.sh                  (moved here)
├── 📁 docs/                         ✅ EXCELLENT - Documentation organized!
│   ├── README.md
│   ├── STATUS.md
│   ├── plan.md
│   ├── file-purpose.md
│   ├── AUTO_REFRESH_GUIDE.md
│   └── POD_MANAGER_GUIDE.md
├── 📁 .github/                      ✅ GOOD - AI instructions
│   ├── copilot-instructions.md
│   ├── claude-instructions.md
│   └── gemini-instructions.md
├── 🔧 keep-tunnel-alive.sh          ✅ GOOD - K8s tunnel scripts (root level OK)
├── 🔧 restart-k8s-tunnel.sh         ✅ GOOD
├── 📝 requirements.txt              ✅ CRITICAL - Must stay at root
├── 📝 .env.example                  ✅ GOOD - Config template
├── 📝 streamlit.log                 ⚠️ Log file (can delete)
└── 📝 tunnel-monitor.log            ⚠️ Log file (can delete)





# Kubernetes AI-Powered Cluster Manager

A Streamlit web application that validates hosts, monitors VMs, manages pods, and provides an AI assistant for your Kubernetes cluster.

## 🔄 System Architecture & Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE (Streamlit)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────────────┐   │
│  │   Host   │  │    VM    │  │   Pod    │  │     AI Assistant        │   │
│  │Validator │  │  Status  │  │ Monitor  │  │  (Gemini 2.0 Flash)     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────────┬─────────────┘   │
└───────┼─────────────┼─────────────┼────────────────────┼─────────────────┘
        │             │             │                    │
        │             │             │         ┌──────────▼──────────┐
        │             │             │         │   AI Agent Engine   │
        │             │             │         │ ┌─────────────────┐ │
        │             │             │         │ │ 1. Planning     │ │
        │             │             │         │ │ 2. Tool Exec    │ │
        │             │             │         │ │ 3. Synthesis    │ │
        │             │             │         │ └─────────────────┘ │
        │             │             │         └──────────┬──────────┘
        │             │             │                    │
        ▼             ▼             ▼                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER (Python Core)                         │
│  ┌──────────────┐   ┌─────────────┐   ┌─────────────────────────────┐    │
│  │  Paramiko    │   │   GCloud    │   │    5 AI Tools               │    │
│  │  SSH Client  │   │     CLI     │   │ • get_cluster_resources     │    │
│  └──────┬───────┘   └──────┬──────┘   │ • describe_resource         │    │
│         │                  │          │ • get_pod_logs              │    │
│         │                  │          │ • check_node_health         │    │
│         │                  │          │ • check_cluster_health      │    │
│         │                  │          └──────────┬──────────────────┘    │
└─────────┼──────────────────┼─────────────────────┼────────────────────────┘
          │                  │                     │
          │                  │                     │
          ▼                  ▼                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                                    │
│  ┌────────────────┐      ┌──────────────────────────────────────┐         │
│  │  Direct SSH    │      │      Google Cloud Platform           │         │
│  │  Target Hosts  │      │  ┌────────────────────────────────┐  │         │
│  └────────────────┘      │  │  Kubernetes Cluster (GKE)      │  │         │
│                          │  │  ┌──────────────────────────┐  │  │         │
│                          │  │  │  k8s-master-001 (Master) │  │  │         │
│                          │  │  │  • kubectl commands      │  │  │         │
│                          │  │  │  • API Server           │  │  │         │
│                          │  │  └──────────────────────────┘  │  │         │
│                          │  │  ┌──────────────────────────┐  │  │         │
│                          │  │  │  k8s-worker-01 (Worker)  │  │  │         │
│                          │  │  │  • Pod Workloads        │  │  │         │
│                          │  │  │  • Resource Metrics     │  │  │         │
│                          │  │  └──────────────────────────┘  │  │         │
│                          │  └────────────────────────────────┘  │         │
│                          └──────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────────────┘

                                    ▲  ▼
                          ┌─────────────────────┐
                          │   Google Gemini API │
                          │   (AI Processing)   │
                          └─────────────────────┘
```

## 📊 Data Flow Example: AI Assistant Query

```
User: "Compare master and worker node taints"
   │
   ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 1: Planning (Gemini AI)                      │
│ → Selects tools: describe_resource × 2             │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 2: Execution                                  │
│ Tool 1: kubectl describe node k8s-master-001        │
│   └→ SSH → Master → Returns taints/conditions      │
│ Tool 2: kubectl describe node k8s-worker-01         │
│   └→ SSH → Worker → Returns taints/conditions      │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│ PHASE 3: Synthesis (Gemini AI)                     │
│ → Analyzes both results                            │
│ → Creates comparison table                         │
│ → Returns natural language answer                  │
└─────────────────────┬───────────────────────────────┘
                      ▼
              User sees answer
```

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit | Web UI framework |
| **Backend** | Python 3.10+ | Core logic |
| **SSH** | Paramiko | Remote server access |
| **Cloud** | GCloud CLI | Google Cloud integration |
| **Orchestration** | Kubernetes | Container management |
| **AI** | Google Gemini 2.0 Flash | Intelligent query processing |
| **Configuration** | python-dotenv | Environment management |
| **Testing** | Pytest | Unit & integration tests |

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
