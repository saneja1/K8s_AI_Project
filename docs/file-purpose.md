# 📋 K8s AI Project - File Purpose Documentation

This document provides a comprehensive overview of every file in this project, its purpose, and whether it's safe to delete.

---

## 🗂️ PROJECT STRUCTURE OVERVIEW

```
K8s AI Project/
├── app/                          # Application UI code
├── core/                         # Core business logic
├── tests/                        # Unit tests
├── .github/                      # AI assistant instructions
├── .logs/                        # Runtime application logs
├── .lxvenv/                      # Python virtual environment (Linux)
├── .vscode/                      # VS Code workspace settings
├── .pytest_cache/                # Pytest cache files
├── .git/                         # Git repository data
├── Configuration files           # Various config files
└── Documentation files           # User guides and docs
```

---

## 📁 CORE APPLICATION FILES (DO NOT DELETE)

### **app/dashboard.py** (1162 lines)
- **Purpose**: Main Streamlit web application - Kubernetes Management Dashboard
- **Features**:
  - Host Validator tab: Validates VMs for K8s cluster readiness via SSH
  - VM Status tab: Real-time monitoring of VM resources (CPU, Memory, Disk)
  - Pod Monitor tab: Live Kubernetes pod monitoring across all namespaces
  - Pod Manager tab: Create and delete Kubernetes pods via web UI
  - Auto-refresh functionality (30-second intervals)
- **Safe to delete?**: ❌ **NO** - This is the entire application!
- **Impact if deleted**: Application won't run at all

### **core/system.py** (626 lines)
- **Purpose**: SSH-based system requirements checker module
- **Functions**:
  - `check_requirements()`: Validates Linux/Windows servers via direct SSH
  - `check_requirements_cloud()`: Validates cloud VMs via gcloud/AWS/Azure CLI
  - `_get_cpu_cores()`, `_get_memory_mib()`, `_get_disk_gib_free()`: Metric collectors
- **Safe to delete?**: ❌ **NO** - Core business logic
- **Impact if deleted**: Host validation won't work

### **core/__init__.py**
- **Purpose**: Makes `core/` a Python package
- **Safe to delete?**: ❌ **NO** - Required for Python imports
- **Impact if deleted**: `from core.system import ...` will fail

---

## 🧪 TEST FILES (CAN DELETE IF NOT DEVELOPING)

### **tests/test_system.py** (198 lines)
- **Purpose**: Comprehensive unit tests for `core/system.py`
- **Coverage**: 12 test cases covering SSH connections, authentication, metric parsing
- **Safe to delete?**: ⚠️ **YES, BUT NOT RECOMMENDED**
- **Impact if deleted**: Can't verify code changes, harder to debug
- **When to keep**: If you're developing/modifying code
- **When to delete**: If you only want to run the app, not develop it

### **test_windows.py** (62 lines)
- **Purpose**: Quick test script for Windows SSH system detection
- **Usage**: Manual testing on Windows machines with SSH enabled
- **Safe to delete?**: ✅ **YES** - Development/testing tool only
- **Impact if deleted**: None on production usage
- **Recommendation**: Keep for testing Windows compatibility

---

## 📚 DOCUMENTATION FILES (SAFE TO DELETE BUT HELPFUL)

### **README.md** (173 lines)
- **Purpose**: Project overview, quick start guide, installation instructions
- **Safe to delete?**: ⚠️ **YES, BUT NOT RECOMMENDED**
- **Impact if deleted**: New users won't know how to set up the project
- **Recommendation**: Keep for reference

### **STATUS.md** (182 lines)
- **Purpose**: Project completion status, feature checklist, implementation log
- **Safe to delete?**: ✅ **YES** - Historical record only
- **Impact if deleted**: None on functionality
- **Recommendation**: Keep for project history, can archive

### **plan.md** (211 lines)
- **Purpose**: Original implementation requirements, step-by-step development plan
- **Safe to delete?**: ✅ **YES** - Planning document only
- **Impact if deleted**: None on functionality
- **Recommendation**: Archive or delete if project is complete

### **AUTO_REFRESH_GUIDE.md** (145 lines)
- **Purpose**: User guide for dashboard auto-refresh feature
- **Safe to delete?**: ⚠️ **YES, BUT HELPFUL**
- **Impact if deleted**: Users won't understand auto-refresh behavior
- **Recommendation**: Keep for user reference

### **POD_MANAGER_GUIDE.md** (145 lines)
- **Purpose**: User guide for Pod Manager tab functionality
- **Safe to delete?**: ⚠️ **YES, BUT HELPFUL**
- **Impact if deleted**: Users won't know how to use Pod Manager
- **Recommendation**: Keep for user reference

### **file-purpose.md** (THIS FILE)
- **Purpose**: Documentation of all files in the project
- **Safe to delete?**: ✅ **YES** - Meta-documentation
- **Impact if deleted**: None on functionality
- **Recommendation**: Keep for future reference

---

## ⚙️ CONFIGURATION FILES (DO NOT DELETE)

### **requirements.txt** (7 lines)
- **Purpose**: Python package dependencies list
- **Contents**: streamlit, paramiko, python-dotenv, pandas, pytest, pytest-mock
- **Safe to delete?**: ❌ **NO** - Required for installation
- **Impact if deleted**: `pip install` won't work
- **Recommendation**: Never delete

### **.env.example** (13 lines)
- **Purpose**: Template for environment variables (SSH, min requirements)
- **Safe to delete?**: ⚠️ **YES, BUT NOT RECOMMENDED**
- **Impact if deleted**: Users won't know what variables to configure
- **Recommendation**: Keep as reference template

### **.env** (NOT IN GIT)
- **Purpose**: Your actual environment variables (passwords, thresholds)
- **Safe to delete?**: ⚠️ **CAREFUL** - Will reset to defaults
- **Impact if deleted**: App uses default values from code
- **Recommendation**: Keep but never commit to Git
- **Note**: Should be in `.gitignore` (it is)

### **.gitignore** (20 lines)
- **Purpose**: Tells Git which files to ignore (secrets, cache, logs)
- **Safe to delete?**: ❌ **NO** - Security critical
- **Impact if deleted**: Secrets and cache files will be committed to Git
- **Recommendation**: Never delete

---

## 🔧 BASH SCRIPTS (LINUX/WSL ONLY)

### **keep-tunnel-alive.sh** (80 lines)
- **Purpose**: Monitoring daemon that auto-restarts SSH tunnel to K8s master
- **How it works**: Checks tunnel health every 30s, restarts if down
- **Safe to delete?**: ⚠️ **YES IF NOT USING KUBERNETES CLUSTER**
- **Impact if deleted**: Dashboard Pod Monitor/Manager won't work (no kubectl access)
- **Recommendation**: Keep if using K8s cluster, delete otherwise

### **restart-k8s-tunnel.sh** (35 lines)
- **Purpose**: Manual SSH tunnel restart script
- **Usage**: Run when tunnel dies manually
- **Safe to delete?**: ⚠️ **YES IF NOT USING KUBERNETES CLUSTER**
- **Impact if deleted**: Must manually recreate tunnel using gcloud commands
- **Recommendation**: Keep as backup to `keep-tunnel-alive.sh`

### **vm_specs.sh** (40 lines)
- **Purpose**: Bash script to list Google Cloud VM specifications
- **Usage**: Shows CPU, memory, disk for all GCP VMs
- **Safe to delete?**: ✅ **YES** - Convenience tool only
- **Impact if deleted**: Use `gcloud compute instances list` instead
- **Recommendation**: Keep if frequently checking VM specs

---

## 📄 KUBERNETES YAML FILES

### **test-pod.yaml** (13 lines)
- **Purpose**: Test Kubernetes pod definition (Ubuntu with 4Gi memory, 2 CPU)
- **Usage**: `kubectl apply -f test-pod.yaml` for testing resource limits
- **Safe to delete?**: ✅ **YES** - Testing artifact
- **Impact if deleted**: None, can recreate anytime
- **Recommendation**: Keep for quick testing, or delete to clean up

---

## 📝 LOG FILES (SAFE TO DELETE)

### **streamlit.log** (1613 lines)
- **Purpose**: Streamlit application runtime logs
- **Contains**: Deprecation warnings, app startup messages
- **Safe to delete?**: ✅ **YES** - Regenerates on next run
- **Impact if deleted**: None, creates new log file
- **Recommendation**: Delete periodically to save space

### **tunnel-monitor.log** (37 lines)
- **Purpose**: SSH tunnel monitoring script logs
- **Contains**: Tunnel restart events, timestamps, kubectl connectivity checks
- **Safe to delete?**: ✅ **YES** - Regenerates on next run
- **Impact if deleted**: None, creates new log file
- **Recommendation**: Delete periodically or keep for debugging

---

## 🗂️ DIRECTORIES

### **.lxvenv/** (Python virtual environment)
- **Purpose**: Isolated Python environment with all dependencies
- **Size**: ~100-500 MB
- **Safe to delete?**: ⚠️ **YES, BUT MUST RECREATE**
- **Impact if deleted**: App won't run until you recreate with `python -m venv .lxvenv`
- **Recommendation**: Keep unless you need to clean up space
- **Regeneration**: `python -m venv .lxvenv && source .lxvenv/bin/activate && pip install -r requirements.txt`

### **.logs/** (Runtime logs)
- **Purpose**: Application runtime logs directory
- **Contents**: `command_logs.pkl` - Pickled command execution logs
- **Safe to delete?**: ✅ **YES** - Regenerates automatically
- **Impact if deleted**: None, directory recreates on next app run
- **Recommendation**: Delete periodically to save space

### **.github/** (AI Assistant Instructions)
- **Purpose**: Configuration for AI coding assistants
- **Files**:
  - `copilot-instructions.md` - GitHub Copilot rules
  - `claude-instructions.md` - Claude AI rules (you're reading this!)
  - `gemini-instructions.md` - Gemini AI rules
- **Safe to delete?**: ⚠️ **YES IF NOT USING AI ASSISTANTS**
- **Impact if deleted**: AI assistants won't follow project conventions
- **Recommendation**: Keep if using GitHub Copilot or Claude

### **.vscode/** (VS Code Settings)
- **Purpose**: VS Code workspace configuration
- **Contents**: `settings.json` - Git warning settings
- **Safe to delete?**: ✅ **YES** - Personal preference
- **Impact if deleted**: VS Code uses default settings
- **Recommendation**: Keep for consistent editor experience

### **.pytest_cache/** (Pytest Cache)
- **Purpose**: Pytest testing framework cache
- **Safe to delete?**: ✅ **YES** - Regenerates on next test run
- **Impact if deleted**: Tests might be slightly slower first run
- **Recommendation**: Delete to clean up, or let pytest manage it

### **.git/** (Git Repository)
- **Purpose**: Git version control data
- **Safe to delete?**: ❌ **NO** - Deletes entire project history
- **Impact if deleted**: Loses all commits, branches, history
- **Recommendation**: Never delete unless intentionally removing Git

### **app/__pycache__/** (Python Cache)
- **Purpose**: Compiled Python bytecode cache
- **Safe to delete?**: ✅ **YES** - Regenerates automatically
- **Impact if deleted**: Slightly slower first import
- **Recommendation**: Delete to clean up, Python manages it

### **core/__pycache__/** (Python Cache)
- **Purpose**: Compiled Python bytecode cache
- **Safe to delete?**: ✅ **YES** - Regenerates automatically
- **Impact if deleted**: Slightly slower first import
- **Recommendation**: Delete to clean up, Python manages it

### **tests/__pycache__/** (Python Cache)
- **Purpose**: Compiled Python test bytecode cache
- **Safe to delete?**: ✅ **YES** - Regenerates automatically
- **Impact if deleted**: Slightly slower first test run
- **Recommendation**: Delete to clean up, Python manages it

---

## 🧹 CLEANUP RECOMMENDATIONS

### **FILES YOU CAN SAFELY DELETE RIGHT NOW:**
```bash
# Documentation (if you don't need reference)
rm STATUS.md plan.md

# Test artifacts
rm test-pod.yaml

# Old logs (they regenerate)
rm streamlit.log tunnel-monitor.log
rm -rf .logs/

# Python cache (regenerates)
rm -rf app/__pycache__/ core/__pycache__/ tests/__pycache__/ .pytest_cache/

# If not using AI assistants
rm -rf .github/

# If not using VS Code
rm -rf .vscode/
```

### **FILES TO KEEP FOR FUNCTIONALITY:**
- ✅ `app/dashboard.py` - Main application
- ✅ `core/system.py` - Core logic
- ✅ `core/__init__.py` - Package definition
- ✅ `requirements.txt` - Dependencies
- ✅ `.gitignore` - Security
- ✅ `.env.example` - Config template
- ✅ `README.md` - Setup instructions

### **FILES TO KEEP IF USING K8S CLUSTER:**
- ✅ `keep-tunnel-alive.sh` - Tunnel monitoring
- ✅ `restart-k8s-tunnel.sh` - Manual tunnel restart
- ✅ `vm_specs.sh` - VM info script

### **FILES TO KEEP FOR DEVELOPMENT:**
- ✅ `tests/test_system.py` - Unit tests
- ✅ `test_windows.py` - Windows testing
- ✅ `.github/` - AI assistant rules
- ✅ User guide docs (AUTO_REFRESH_GUIDE.md, POD_MANAGER_GUIDE.md)

---

## 🎯 QUICK CLEANUP COMMAND

**Safe cleanup (removes only regenerable files):**
```bash
cd "/mnt/c/Users/aneja/Desktop/K8s AI Project"

# Remove Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Remove pytest cache
rm -rf .pytest_cache/

# Remove old logs
rm -f streamlit.log tunnel-monitor.log
rm -rf .logs/

echo "✅ Cleanup complete! Removed cache and logs only."
```

**Aggressive cleanup (also removes documentation):**
```bash
cd "/mnt/c/Users/aneja/Desktop/K8s AI Project"

# Safe cleanup first
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache/ .logs/
rm -f streamlit.log tunnel-monitor.log

# Remove documentation
rm -f STATUS.md plan.md test-pod.yaml file-purpose.md

# Remove AI assistant instructions (if not needed)
rm -rf .github/

# Remove VS Code settings (if not needed)
rm -rf .vscode/

echo "✅ Aggressive cleanup complete!"
```

---

## 📊 FILE COUNT SUMMARY

| Category | Count | Safe to Delete |
|----------|-------|----------------|
| **Core Application** | 3 files | ❌ NO |
| **Tests** | 2 files | ⚠️ For development only |
| **Documentation** | 6 files | ⚠️ Helpful to keep |
| **Configuration** | 4 files | ❌ Keep .env.example, .gitignore |
| **Scripts** | 3 files | ⚠️ Keep if using K8s |
| **Logs** | 2 files | ✅ YES |
| **Directories** | 9 dirs | ✅ Cache dirs only |

---

## ⚠️ NEVER DELETE THESE:
1. `app/dashboard.py` - The entire application
2. `core/system.py` - Core business logic  
3. `core/__init__.py` - Python package file
4. `requirements.txt` - Dependency list
5. `.gitignore` - Security critical
6. `.lxvenv/` - Unless you want to reinstall everything

---

## 💡 FINAL RECOMMENDATIONS

### **For Production Use Only:**
Keep: Application files, configuration, K8s scripts, README
Delete: Tests, documentation, logs, cache, AI instructions

### **For Development:**
Keep: Everything except logs and cache
Delete: Only regenerable files (logs, __pycache__)

### **For Archival:**
Keep: Everything in a zip file
Delete: Nothing (full backup)

---

**Last Updated**: October 10, 2025
**Project Status**: Fully functional, production-ready
**Primary Purpose**: Kubernetes cluster host validation and management dashboard
