#!/bin/bash

# Flask App Management Script
# Usage: ./manage_app.sh {start|stop|restart|status}

APP_NAME="flask_app2.0"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$APP_DIR/app.pid"
LOG_FILE="$APP_DIR/app.log"
PYTHON_APP="app.py"

# MCP Server settings
MCP_HEALTH_SERVER_NAME="mcp_health_server"
MCP_HEALTH_SERVER_SCRIPT="MCP/mcp_health/mcp_health_server.py"
MCP_HEALTH_PID_FILE="$APP_DIR/mcp_health.pid"
MCP_HEALTH_LOG_FILE="$APP_DIR/mcp_health.log"

MCP_DESCRIBE_SERVER_NAME="mcp_describe_server"
MCP_DESCRIBE_SERVER_SCRIPT="MCP/mcp_describe/mcp_describe_server.py"
MCP_DESCRIBE_PID_FILE="$APP_DIR/mcp_describe.pid"
MCP_DESCRIBE_LOG_FILE="$APP_DIR/mcp_describe.log"
MCP_DESCRIBE_PORT=8002

MCP_RESOURCES_SERVER_NAME="mcp_resources_server"
MCP_RESOURCES_SERVER_SCRIPT="MCP/mcp_resources/mcp_resources_server.py"
MCP_RESOURCES_PID_FILE="$APP_DIR/mcp_resources.pid"
MCP_RESOURCES_LOG_FILE="$APP_DIR/mcp_resources.log"
MCP_RESOURCES_PORT=8001

MCP_OPERATIONS_SERVER_NAME="mcp_operations_server"
MCP_OPERATIONS_SERVER_SCRIPT="MCP/mcp_operations/mcp_operations_server.py"
MCP_OPERATIONS_PID_FILE="$APP_DIR/mcp_operations.pid"
MCP_OPERATIONS_LOG_FILE="$APP_DIR/mcp_operations.log"

MCP_MONITOR_SERVER_NAME="mcp_monitor_server"
MCP_MONITOR_SERVER_SCRIPT="MCP/mcp_monitor/mcp_monitor_server.py"
MCP_MONITOR_PID_FILE="$APP_DIR/mcp_monitor.pid"
MCP_MONITOR_LOG_FILE="$APP_DIR/mcp_monitor.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to activate virtual environment
activate_venv() {
    # Stay in app2.0 directory - use local .venv only
    cd "$APP_DIR" || exit 1
    
    # Always activate virtual environment first (local to app2.0)
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        return 0
    else
        echo -e "${RED}ERROR: Virtual environment not found at $APP_DIR/.venv/bin/activate${NC}"
        echo -e "${RED}Please create virtual environment first in app2.0: python3 -m venv .venv${NC}"
        exit 1
    fi
}

# Function to check if app is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is not running
            rm -f "$PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# Function to check if MCP health server is running
is_mcp_health_running() {
    if [ -f "$MCP_HEALTH_PID_FILE" ]; then
        MCP_PID=$(cat "$MCP_HEALTH_PID_FILE")
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is not running
            rm -f "$MCP_HEALTH_PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# Function to check if MCP describe server is running
is_mcp_describe_running() {
    if [ -f "$MCP_DESCRIBE_PID_FILE" ]; then
        MCP_PID=$(cat "$MCP_DESCRIBE_PID_FILE")
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is not running
            rm -f "$MCP_DESCRIBE_PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

is_mcp_resources_running() {
    if [ -f "$MCP_RESOURCES_PID_FILE" ]; then
        MCP_PID=$(cat "$MCP_RESOURCES_PID_FILE")
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is not running
            rm -f "$MCP_RESOURCES_PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# Function to check if MCP operations server is running
is_mcp_operations_running() {
    if [ -f "$MCP_OPERATIONS_PID_FILE" ]; then
        MCP_PID=$(cat "$MCP_OPERATIONS_PID_FILE")
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is not running
            rm -f "$MCP_OPERATIONS_PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# Function to check if MCP monitor server is running
is_mcp_monitor_running() {
    if [ -f "$MCP_MONITOR_PID_FILE" ]; then
        MCP_PID=$(cat "$MCP_MONITOR_PID_FILE")
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            return 0
        else
            # PID file exists but process is not running
            rm -f "$MCP_MONITOR_PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# Function to start the app
start() {
    echo -e "${YELLOW}Starting $APP_NAME...${NC}"
    
    if is_running; then
        echo -e "${YELLOW}$APP_NAME is already running (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi
    
    # Activate virtual environment (local to app2.0)
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    activate_venv
    
    # Start MCP Health Server first
    echo -e "${YELLOW}Starting MCP Health Server on port 8000...${NC}"
    nohup python3 "$MCP_HEALTH_SERVER_SCRIPT" > "$MCP_HEALTH_LOG_FILE" 2>&1 &
    echo $! > "$MCP_HEALTH_PID_FILE"
    sleep 2
    
    if is_mcp_health_running; then
        echo -e "${GREEN}MCP Health Server started successfully (PID: $(cat $MCP_HEALTH_PID_FILE))${NC}"
    else
        echo -e "${RED}Failed to start MCP Health Server${NC}"
        if [ -f "$MCP_HEALTH_LOG_FILE" ]; then
            echo -e "${RED}Check logs: $MCP_HEALTH_LOG_FILE${NC}"
            tail -10 "$MCP_HEALTH_LOG_FILE"
        fi
    fi
    
    # Start MCP Describe Server
    echo -e "${YELLOW}Starting MCP Describe Server on port 8002...${NC}"
    export PORT=8002
    nohup python3 "$MCP_DESCRIBE_SERVER_SCRIPT" > "$MCP_DESCRIBE_LOG_FILE" 2>&1 &
    echo $! > "$MCP_DESCRIBE_PID_FILE"
    unset PORT
    sleep 2
    
    if is_mcp_describe_running; then
        echo -e "${GREEN}MCP Describe Server started successfully (PID: $(cat $MCP_DESCRIBE_PID_FILE))${NC}"
    else
        echo -e "${RED}Failed to start MCP Describe Server${NC}"
        if [ -f "$MCP_DESCRIBE_LOG_FILE" ]; then
            echo -e "${RED}Check logs: $MCP_DESCRIBE_LOG_FILE${NC}"
            tail -10 "$MCP_DESCRIBE_LOG_FILE"
        fi
    fi
    
    # Start MCP Resources Server
    echo -e "${YELLOW}Starting MCP Resources Server on port 8001...${NC}"
    export PORT=8001
    nohup python3 "$MCP_RESOURCES_SERVER_SCRIPT" > "$MCP_RESOURCES_LOG_FILE" 2>&1 &
    echo $! > "$MCP_RESOURCES_PID_FILE"
    unset PORT
    sleep 2
    
    if is_mcp_resources_running; then
        echo -e "${GREEN}MCP Resources Server started successfully (PID: $(cat $MCP_RESOURCES_PID_FILE))${NC}"
    else
        echo -e "${RED}Failed to start MCP Resources Server${NC}"
        if [ -f "$MCP_RESOURCES_LOG_FILE" ]; then
            echo -e "${RED}Check logs: $MCP_RESOURCES_LOG_FILE${NC}"
            tail -10 "$MCP_RESOURCES_LOG_FILE"
        fi
    fi
    
    # Start MCP Operations Server
    echo -e "${YELLOW}Starting MCP Operations Server on port 8003...${NC}"
    export PORT=8003
    nohup python3 "$MCP_OPERATIONS_SERVER_SCRIPT" > "$MCP_OPERATIONS_LOG_FILE" 2>&1 &
    echo $! > "$MCP_OPERATIONS_PID_FILE"
    unset PORT
    sleep 2
    
    if is_mcp_operations_running; then
        echo -e "${GREEN}MCP Operations Server started successfully (PID: $(cat $MCP_OPERATIONS_PID_FILE))${NC}"
    else
        echo -e "${RED}Failed to start MCP Operations Server${NC}"
        if [ -f "$MCP_OPERATIONS_LOG_FILE" ]; then
            echo -e "${RED}Check logs: $MCP_OPERATIONS_LOG_FILE${NC}"
            tail -10 "$MCP_OPERATIONS_LOG_FILE"
        fi
    fi
    
    # Start MCP Monitor Server
    echo -e "${YELLOW}Starting MCP Monitor Server on port 8004...${NC}"
    export PORT=8004
    nohup python3 "$MCP_MONITOR_SERVER_SCRIPT" > "$MCP_MONITOR_LOG_FILE" 2>&1 &
    echo $! > "$MCP_MONITOR_PID_FILE"
    unset PORT
    sleep 2
    
    if is_mcp_monitor_running; then
        echo -e "${GREEN}MCP Monitor Server started successfully (PID: $(cat $MCP_MONITOR_PID_FILE))${NC}"
    else
        echo -e "${RED}Failed to start MCP Monitor Server${NC}"
        if [ -f "$MCP_MONITOR_LOG_FILE" ]; then
            echo -e "${RED}Check logs: $MCP_MONITOR_LOG_FILE${NC}"
            tail -10 "$MCP_MONITOR_LOG_FILE"
        fi
    fi
    
    # Start the app in background
    echo -e "${YELLOW}Launching Flask app on port 7000...${NC}"
    nohup python3 "$PYTHON_APP" > "$LOG_FILE" 2>&1 &
    
    # Save PID
    echo $! > "$PID_FILE"
    
    # Wait a moment to check if it started successfully
    sleep 2
    
    if is_running; then
        echo -e "${GREEN}$APP_NAME started successfully (PID: $(cat $PID_FILE))${NC}"
        echo -e "${GREEN}App is running at: http://localhost:7000${NC}"
        echo -e "${GREEN}MCP Health Server: http://localhost:8000/mcp${NC}"
        echo -e "${GREEN}MCP Describe Server: http://localhost:8002/mcp${NC}"
        echo -e "${GREEN}MCP Resources Server: http://localhost:8001/mcp${NC}"
        echo -e "${GREEN}MCP Operations Server: http://localhost:8003/mcp${NC}"
        echo -e "${GREEN}MCP Monitor Server: http://localhost:8004/mcp${NC}"
        echo -e "${GREEN}Logs: $LOG_FILE${NC}"
        return 0
    else
        echo -e "${RED}Failed to start $APP_NAME${NC}"
        if [ -f "$LOG_FILE" ]; then
            echo -e "${RED}Check logs: $LOG_FILE${NC}"
            tail -10 "$LOG_FILE"
        fi
        return 1
    fi
}

# Function to stop the app
stop() {
    echo -e "${YELLOW}Stopping $APP_NAME...${NC}"
    
    # Stop Flask app
    if ! is_running; then
        echo -e "${YELLOW}$APP_NAME is not running${NC}"
    else
        PID=$(cat "$PID_FILE")
        
        # Try graceful shutdown first
        kill "$PID" 2>/dev/null
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing $APP_NAME...${NC}"
            kill -9 "$PID" 2>/dev/null
        fi
        
        # Clean up PID file
        rm -f "$PID_FILE"
        echo -e "${GREEN}$APP_NAME stopped${NC}"
    fi
    
    # Stop MCP Health Server
    echo -e "${YELLOW}Stopping MCP Health Server...${NC}"
    if ! is_mcp_health_running; then
        echo -e "${YELLOW}MCP Health Server is not running${NC}"
    else
        MCP_PID=$(cat "$MCP_HEALTH_PID_FILE")
        
        # Try graceful shutdown first
        kill "$MCP_PID" 2>/dev/null
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing MCP Health Server...${NC}"
            kill -9 "$MCP_PID" 2>/dev/null
        fi
        
        # Clean up PID file
        rm -f "$MCP_HEALTH_PID_FILE"
        echo -e "${GREEN}MCP Health Server stopped${NC}"
    fi
    
    # Stop MCP Describe Server
    echo -e "${YELLOW}Stopping MCP Describe Server...${NC}"
    if ! is_mcp_describe_running; then
        echo -e "${YELLOW}MCP Describe Server is not running${NC}"
    else
        MCP_PID=$(cat "$MCP_DESCRIBE_PID_FILE")
        
        # Try graceful shutdown first
        kill "$MCP_PID" 2>/dev/null
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing MCP Describe Server...${NC}"
            kill -9 "$MCP_PID" 2>/dev/null
        fi
        
        # Clean up PID file
        rm -f "$MCP_DESCRIBE_PID_FILE"
        echo -e "${GREEN}MCP Describe Server stopped${NC}"
    fi
    
    echo -e "${YELLOW}Stopping MCP Resources Server...${NC}"
    if ! is_mcp_resources_running; then
        echo -e "${YELLOW}MCP Resources Server is not running${NC}"
    else
        MCP_PID=$(cat "$MCP_RESOURCES_PID_FILE")
        
        # Try graceful shutdown first
        kill "$MCP_PID" 2>/dev/null
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing MCP Resources Server...${NC}"
            kill -9 "$MCP_PID" 2>/dev/null
        fi
        
        # Clean up PID file
        rm -f "$MCP_RESOURCES_PID_FILE"
        echo -e "${GREEN}MCP Resources Server stopped${NC}"
    fi
    
    # Stop MCP Operations Server
    echo -e "${YELLOW}Stopping MCP Operations Server...${NC}"
    if ! is_mcp_operations_running; then
        echo -e "${YELLOW}MCP Operations Server is not running${NC}"
    else
        MCP_PID=$(cat "$MCP_OPERATIONS_PID_FILE")
        
        # Try graceful shutdown first
        kill "$MCP_PID" 2>/dev/null
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing MCP Operations Server...${NC}"
            kill -9 "$MCP_PID" 2>/dev/null
        fi
        
        # Clean up PID file
        rm -f "$MCP_OPERATIONS_PID_FILE"
        echo -e "${GREEN}MCP Operations Server stopped${NC}"
    fi
    
    # Stop MCP Monitor Server
    echo -e "${YELLOW}Stopping MCP Monitor Server...${NC}"
    if ! is_mcp_monitor_running; then
        echo -e "${YELLOW}MCP Monitor Server is not running${NC}"
    else
        MCP_PID=$(cat "$MCP_MONITOR_PID_FILE")
        
        # Try graceful shutdown first
        kill "$MCP_PID" 2>/dev/null
        
        # Wait up to 10 seconds for graceful shutdown
        for i in {1..10}; do
            if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$MCP_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing MCP Monitor Server...${NC}"
            kill -9 "$MCP_PID" 2>/dev/null
        fi
        
        # Clean up PID file
        rm -f "$MCP_MONITOR_PID_FILE"
        echo -e "${GREEN}MCP Monitor Server stopped${NC}"
    fi
    
    return 0
}

# Function to restart the app
restart() {
    echo -e "${YELLOW}Restarting $APP_NAME...${NC}"
    stop
    echo -e "${YELLOW}Waiting 5 seconds before starting...${NC}"
    sleep 5
    start
}

# Function to show status
status() {
    # Check Flask app
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo -e "${GREEN}$APP_NAME is running (PID: $PID)${NC}"
        echo -e "${GREEN}App URL: http://localhost:7000${NC}"
        echo -e "${GREEN}Log file: $LOG_FILE${NC}"
        
        # Show recent logs
        if [ -f "$LOG_FILE" ]; then
            echo -e "\n${YELLOW}Recent Flask app logs:${NC}"
            tail -5 "$LOG_FILE"
        fi
    else
        echo -e "${RED}$APP_NAME is not running${NC}"
    fi
    
    echo ""
    
    # Check MCP Health Server
    if is_mcp_health_running; then
        MCP_PID=$(cat "$MCP_HEALTH_PID_FILE")
        echo -e "${GREEN}MCP Health Server is running (PID: $MCP_PID)${NC}"
        echo -e "${GREEN}MCP URL: http://localhost:8000/mcp${NC}"
        echo -e "${GREEN}Log file: $MCP_HEALTH_LOG_FILE${NC}"
        
        # Show recent logs
        if [ -f "$MCP_HEALTH_LOG_FILE" ]; then
            echo -e "\n${YELLOW}Recent MCP Health server logs:${NC}"
            tail -5 "$MCP_HEALTH_LOG_FILE"
        fi
    else
        echo -e "${RED}MCP Health Server is not running${NC}"
    fi
    
    echo ""
    
    # Check MCP Describe Server
    if is_mcp_describe_running; then
        MCP_PID=$(cat "$MCP_DESCRIBE_PID_FILE")
        echo -e "${GREEN}MCP Describe Server is running (PID: $MCP_PID)${NC}"
        echo -e "${GREEN}MCP URL: http://localhost:8002/mcp${NC}"
        echo -e "${GREEN}Log file: $MCP_DESCRIBE_LOG_FILE${NC}"
        
        # Show recent logs
        if [ -f "$MCP_DESCRIBE_LOG_FILE" ]; then
            echo -e "\n${YELLOW}Recent MCP Describe server logs:${NC}"
            tail -5 "$MCP_DESCRIBE_LOG_FILE"
        fi
    else
        echo -e "${RED}MCP Describe Server is not running${NC}"
    fi
    
    echo ""
    
    # MCP Resources Server status
    if is_mcp_resources_running; then
        MCP_PID=$(cat "$MCP_RESOURCES_PID_FILE")
        echo -e "${GREEN}MCP Resources Server is running (PID: $MCP_PID)${NC}"
        echo -e "${GREEN}MCP URL: http://localhost:8001/mcp${NC}"
        echo -e "${GREEN}Log file: $MCP_RESOURCES_LOG_FILE${NC}"
        
        # Show recent logs
        if [ -f "$MCP_RESOURCES_LOG_FILE" ]; then
            echo -e "\n${YELLOW}Recent MCP Resources server logs:${NC}"
            tail -5 "$MCP_RESOURCES_LOG_FILE"
        fi
    else
        echo -e "${RED}MCP Resources Server is not running${NC}"
    fi
    
    echo ""
    
    # MCP Operations Server status
    if is_mcp_operations_running; then
        MCP_PID=$(cat "$MCP_OPERATIONS_PID_FILE")
        echo -e "${GREEN}MCP Operations Server is running (PID: $MCP_PID)${NC}"
        echo -e "${GREEN}MCP URL: http://localhost:8003/mcp${NC}"
        echo -e "${GREEN}Log file: $MCP_OPERATIONS_LOG_FILE${NC}"
        
        # Show recent logs
        if [ -f "$MCP_OPERATIONS_LOG_FILE" ]; then
            echo -e "\n${YELLOW}Recent MCP Operations server logs:${NC}"
            tail -5 "$MCP_OPERATIONS_LOG_FILE"
        fi
    else
        echo -e "${RED}MCP Operations Server is not running${NC}"
    fi
    
    echo ""
    
    # MCP Monitor Server status
    if is_mcp_monitor_running; then
        MCP_PID=$(cat "$MCP_MONITOR_PID_FILE")
        echo -e "${GREEN}MCP Monitor Server is running (PID: $MCP_PID)${NC}"
        echo -e "${GREEN}MCP URL: http://localhost:8004/mcp${NC}"
        echo -e "${GREEN}Log file: $MCP_MONITOR_LOG_FILE${NC}"
        
        # Show recent logs
        if [ -f "$MCP_MONITOR_LOG_FILE" ]; then
            echo -e "\n${YELLOW}Recent MCP Monitor server logs:${NC}"
            tail -5 "$MCP_MONITOR_LOG_FILE"
        fi
    else
        echo -e "${RED}MCP Monitor Server is not running${NC}"
    fi
}

# Function to show logs
logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}Showing logs for $APP_NAME:${NC}"
        tail -f "$LOG_FILE"
    else
        echo -e "${RED}Log file not found: $LOG_FILE${NC}"
    fi
}

# Ensure virtual environment is activated before any operation
echo -e "${YELLOW}Ensuring virtual environment is activated...${NC}"
activate_venv

# Main script logic
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the Flask app in background"
        echo "  stop    - Stop the Flask app"
        echo "  restart - Restart the Flask app"
        echo "  status  - Show app status and recent logs"
        echo "  logs    - Show live logs (Ctrl+C to exit)"
        exit 1
        ;;
esac

exit 0