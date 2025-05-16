#!/bin/bash

# Simple run script for News Bias Analyzer components

# Set color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load environment variables from .env file if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
  echo -e "${BLUE}Loading environment variables from .env file...${NC}"
  set -o allexport
  source "$PROJECT_ROOT/.env"
  set +o allexport
  echo -e "${GREEN}Environment variables loaded.${NC}"
else
  echo -e "${YELLOW}No .env file found. Please create one based on .env.example${NC}"
fi

# Default database URL if not set
if [ -z "$DATABASE_URL" ]; then
  export DATABASE_URL="postgresql://newsbias:newsbias@localhost:5432/news_bias"
  echo -e "${YELLOW}Using default DATABASE_URL: $DATABASE_URL${NC}"
fi

# Default scraper limit if not set
if [ -z "$SCRAPER_LIMIT_PER_FEED" ]; then
  export SCRAPER_LIMIT_PER_FEED=5
  echo -e "${YELLOW}Using default SCRAPER_LIMIT_PER_FEED: $SCRAPER_LIMIT_PER_FEED${NC}"
fi

# Setup Python environment
setup_python_env() {
  # Create and activate virtual environment if it doesn't exist
  if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${BLUE}Creating Python virtual environment...${NC}"
    python3 -m venv "$PROJECT_ROOT/venv"
  fi
  
  # Activate the virtual environment
  source "$PROJECT_ROOT/venv/bin/activate"
  
  # Install required packages - quietly to avoid the long output
  echo -e "${BLUE}Checking required Python packages...${NC}"
  pip install -q -r "$PROJECT_ROOT/requirements.txt"
}

# Show usage information
show_help() {
  echo -e "${BLUE}News Bias Analyzer - Simplified Runner${NC}"
  echo ""
  echo "Usage: ./run.sh COMMAND [OPTIONS]"
  echo ""
  echo "Commands:"
  echo "  scraper                Run the news scraper (uses SCRAPER_LIMIT_PER_FEED from .env)"
  echo "  analyzer [LIMIT]       Analyze articles with OpenAI (optional: limit articles to analyze)"
  echo "  analyze                Run the batch analyzer for efficient batch processing"
  echo "  analyze daemon         Run the batch analyzer in daemon mode (continuous polling)"
  echo "  batch                  Run the batch analyzer"
  echo "  api                    Start the API server"
  echo "  dashboard              Start the web dashboard"
  echo "  extension              Build the browser extension"
  echo "  server [TYPE]          Start the API servers (TYPE: extension, dashboard, or both [default])"
  echo "                         Automatically cleans up any existing server processes"
  echo "  setup                  Set up the environment and database"
  echo "  status                 Show database statistics"
  echo "  custom <FILE>          Run a custom Python script file"
  echo "  help                   Show this help message"
  echo ""
}

# Run the scraper
run_scraper() {
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Running News Scraper (limit: $SCRAPER_LIMIT_PER_FEED articles per feed)...${NC}"
  python -m scrapers.scrape_to_db
}

# Run the analyzer
run_analyzer() {
  setup_python_env
  cd "$PROJECT_ROOT"
  LIMIT=${1:-10}  # Default to 10 articles if not specified
  echo -e "${GREEN}Running Article Analyzer (limit: $LIMIT articles)...${NC}"
  python -m processors.direct_analysis --limit $LIMIT
}

# Run the batch analyzer
run_batch() {
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Running Batch Analyzer...${NC}"
  python -m processors.batch_prepare
}

# Start the API server
start_api() {
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Starting API Server...${NC}"
  uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
}

# Start the dashboard
start_dashboard() {
  cd "$PROJECT_ROOT/frontend/dashboard"
  echo -e "${GREEN}Starting Dashboard...${NC}"
  echo -e "${YELLOW}Note: You need to have Node.js installed${NC}"
  if [ ! -d "node_modules" ]; then
    echo -e "${BLUE}Installing dashboard dependencies...${NC}"
    npm install
  fi
  npm start
}

# Build the extension
build_extension() {
  cd "$PROJECT_ROOT/frontend/browser_extension"
  echo -e "${GREEN}Building Browser Extension...${NC}"
  echo -e "${BLUE}Extension files are in the browser_extension directory${NC}"
  echo -e "${BLUE}Load the unpacked extension in Chrome from this directory${NC}"
}

# Setup the environment
setup_environment() {
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Setting up database...${NC}"
  cd database
  bash setup_db.sh
}

# Show database statistics
show_status() {
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Fetching database statistics...${NC}"
  python -m database.db_stats
}

# Run a custom Python script
run_custom_script() {
  if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide a file path${NC}"
    echo "Usage: ./run.sh custom <file_path>"
    exit 1
  fi
  
  SCRIPT_PATH="$1"
  
  if [ ! -f "$SCRIPT_PATH" ]; then
    echo -e "${RED}Error: File $SCRIPT_PATH does not exist${NC}"
    exit 1
  fi
  
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Running custom script: $SCRIPT_PATH${NC}"
  
  # Check if the script has a go() function
  if grep -q "def go()" "$SCRIPT_PATH"; then
    python -c "import os, sys, importlib.util; sys.path.insert(0, os.getcwd()); script_path = '$SCRIPT_PATH'; module_name = os.path.splitext(os.path.basename(script_path))[0]; spec = importlib.util.spec_from_file_location(module_name, script_path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.go()"
  else
    # Execute the script directly
    python "$SCRIPT_PATH"
  fi
}

# Run the batch analyzer
run_batch_analyzer() {
  setup_python_env
  cd "$PROJECT_ROOT"
  
  if [ "$1" = "daemon" ]; then
    echo -e "${GREEN}Starting Batch Analyzer in daemon mode...${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    python -m analyzer.batch_analyzer --daemon
  else
    echo -e "${GREEN}Running Batch Analyzer (one-time check)...${NC}"
    python -m analyzer.batch_analyzer
  fi
}

# Start server(s)
start_servers() {
  setup_python_env
  cd "$PROJECT_ROOT"
  
  # Set server type (default to "both" if not specified)
  SERVER_TYPE=${1:-"both"}
  
  echo -e "${GREEN}Starting News Bias Analyzer server(s)...${NC}"
  echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
  echo -e "${BLUE}Any existing server processes will be automatically cleaned up${NC}"
  
  # Start the servers (automatic cleanup is now built in)
  python -m server.server_manager --type "$SERVER_TYPE"
}

# Parse command
case "$1" in
  scraper)
    run_scraper
    ;;
  analyzer)
    run_analyzer "$2"
    ;;
  analyze)
    run_batch_analyzer "$2"
    ;;
  batch)
    run_batch
    ;;
  api)
    start_api
    ;;
  dashboard)
    start_dashboard
    ;;
  extension)
    build_extension
    ;;
  server)
    shift  # Remove the 'server' command, leaving any arguments
    start_servers "$@"
    ;;
  setup)
    setup_environment
    ;;
  status)
    show_status
    ;;
  custom)
    run_custom_script "$2"
    ;;
  help)
    show_help
    ;;
  *)
    show_help
    exit 1
    ;;
esac