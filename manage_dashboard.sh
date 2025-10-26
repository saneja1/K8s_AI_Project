#!/bin/bash
# Streamlit Dashboard Management Script
# Usage: ./manage_dashboard.sh [start|stop|restart|status]

PROJECT_DIR="/mnt/c/Users/aneja/Desktop/K8s AI Project"
VENV_PATH="$PROJECT_DIR/.venv/bin/activate"
APP_FILE="$PROJECT_DIR/app/dashboard.py"
PID_FILE="$PROJECT_DIR/.streamlit.pid"
LOG_FILE="$PROJECT_DIR/streamlit.log"
PORT=8501

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if virtual environment exists
check_venv() {
    if [ ! -f "$VENV_PATH" ]; then
        echo -e "${RED}❌ Virtual environment not found at: $VENV_PATH${NC}"
        echo "Please create virtual environment first."
        exit 1
    fi
}

# Function to check if Streamlit is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # Running
        else
            # PID file exists but process is dead
            rm -f "$PID_FILE"
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Function to get PID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

# Function to start Streamlit
start_streamlit() {
    echo -e "${YELLOW}🚀 Starting Streamlit Dashboard...${NC}"
    
    # Check if already running
    if is_running; then
        echo -e "${YELLOW}⚠️  Streamlit is already running (PID: $(get_pid))${NC}"
        echo "Use './manage_dashboard.sh stop' to stop it first, or './manage_dashboard.sh restart' to restart."
        exit 1
    fi
    
    # Check virtual environment
    check_venv
    
    # Change to project directory
    cd "$PROJECT_DIR" || exit 1
    
    # Activate virtual environment and start Streamlit in background
    echo -e "${YELLOW}📦 Activating virtual environment...${NC}"
    source "$VENV_PATH"
    
    echo -e "${YELLOW}🌐 Starting Streamlit on port $PORT...${NC}"
    # Use streamlit directly - the activated venv will provide the correct one
    nohup streamlit run "$APP_FILE" --server.port="$PORT" > "$LOG_FILE" 2>&1 &
    
    # Save PID
    echo $! > "$PID_FILE"
    
    # Wait a moment for startup
    sleep 3
    
    # Check if it started successfully
    if is_running; then
        echo -e "${GREEN}✅ Streamlit started successfully!${NC}"
        echo -e "${GREEN}   PID: $(get_pid)${NC}"
        echo -e "${GREEN}   URL: http://localhost:$PORT${NC}"
        echo -e "${GREEN}   Logs: $LOG_FILE${NC}"
        echo ""
        echo "Use './manage_dashboard.sh stop' to stop the dashboard."
    else
        echo -e "${RED}❌ Failed to start Streamlit. Check logs: $LOG_FILE${NC}"
        exit 1
    fi
}

# Function to stop Streamlit
stop_streamlit() {
    echo -e "${YELLOW}🛑 Stopping Streamlit Dashboard...${NC}"
    
    if ! is_running; then
        echo -e "${YELLOW}⚠️  Streamlit is not running.${NC}"
        exit 0
    fi
    
    PID=$(get_pid)
    echo -e "${YELLOW}   Terminating process (PID: $PID)...${NC}"
    
    # Try graceful shutdown first
    kill "$PID" 2>/dev/null
    
    # Wait up to 5 seconds for graceful shutdown
    for i in {1..5}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}   Force killing process...${NC}"
        kill -9 "$PID" 2>/dev/null
        sleep 1
    fi
    
    # Clean up PID file
    rm -f "$PID_FILE"
    
    echo -e "${GREEN}✅ Streamlit stopped successfully.${NC}"
}

# Function to restart Streamlit
restart_streamlit() {
    echo -e "${YELLOW}🔄 Restarting Streamlit Dashboard...${NC}"
    echo ""
    
    if is_running; then
        stop_streamlit
        echo ""
        sleep 2
    fi
    
    start_streamlit
}

# Function to show status
show_status() {
    echo -e "${YELLOW}📊 Streamlit Dashboard Status${NC}"
    echo "=================================="
    
    if is_running; then
        PID=$(get_pid)
        echo -e "${GREEN}Status: Running ✅${NC}"
        echo "PID: $PID"
        echo "Port: $PORT"
        echo "URL: http://localhost:$PORT"
        echo "Log file: $LOG_FILE"
        echo ""
        echo "Process details:"
        ps aux | grep "$PID" | grep -v grep || echo "  (Process info not available)"
    else
        echo -e "${RED}Status: Not running ❌${NC}"
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "Last 10 lines from log:"
            tail -n 10 "$LOG_FILE"
        fi
    fi
}

# Function to show logs
show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}❌ Log file not found: $LOG_FILE${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}📜 Streaming Streamlit logs (Ctrl+C to exit)...${NC}"
    echo "=================================="
    tail -f "$LOG_FILE"
}

# Main script logic
case "$1" in
    start)
        start_streamlit
        ;;
    stop)
        stop_streamlit
        ;;
    restart)
        restart_streamlit
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Streamlit Dashboard Management Script"
        echo "======================================"
        echo ""
        echo "Usage: ./manage_dashboard.sh [command]"
        echo ""
        echo "Commands:"
        echo "  start    - Start the Streamlit dashboard"
        echo "  stop     - Stop the Streamlit dashboard"
        echo "  restart  - Restart the Streamlit dashboard"
        echo "  status   - Show dashboard status"
        echo "  logs     - Stream dashboard logs (tail -f)"
        echo ""
        echo "Examples:"
        echo "  ./manage_dashboard.sh start"
        echo "  ./manage_dashboard.sh restart"
        echo "  ./manage_dashboard.sh status"
        echo ""
        exit 1
        ;;
esac
