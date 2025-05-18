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
  echo "  docker [COMMAND]       Manage Docker database container (up, down, status, init, backup, restore, shell)"
  echo "  status [TYPE]          Show database statistics"
  echo "                         Types: sources - Show detailed source statistics"
  echo "  restore_openai [ARGS]  Restore OpenAI batch data to database with source detection"
  echo "                         Run without args for more information"
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

# Function previously used for local environment setup (now removed in favor of docker)

# Show database statistics
show_status() {
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Fetching database statistics...${NC}"
  if [ -n "$1" ]; then
    # Pass the argument to db_stats.py
    python -m database.db_stats "$1"
  else
    # No argument, show general stats
    python -m database.db_stats
  fi
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

# Manage Docker database
manage_docker_db() {
  # Use the db-docker.sh script from the database folder
  DB_DOCKER_SCRIPT="$PROJECT_ROOT/database/db-docker.sh"
  
  # Check if the script exists
  if [ ! -f "$DB_DOCKER_SCRIPT" ]; then
    echo -e "${RED}Error: Docker database script not found at $DB_DOCKER_SCRIPT${NC}"
    echo -e "${BLUE}Make sure you have set up the Docker database correctly${NC}"
    exit 1
  fi
  
  # Make the script executable if it's not already
  if [ ! -x "$DB_DOCKER_SCRIPT" ]; then
    chmod +x "$DB_DOCKER_SCRIPT"
  fi
  
  # Default to showing help if no command is provided
  DOCKER_COMMAND=${1:-"help"}
  
  echo -e "${GREEN}Managing Docker database: $DOCKER_COMMAND${NC}"
  
  # Execute the database Docker management script
  shift # Remove the first argument (the command)
  "$DB_DOCKER_SCRIPT" "$DOCKER_COMMAND" "$@"
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

# Restore OpenAI data to database
restore_openai_data() {
  setup_python_env
  cd "$PROJECT_ROOT"
  echo -e "${GREEN}Restoring OpenAI data to database...${NC}"
  
  # Check if any additional arguments were passed
  if [ -n "$1" ]; then
    python -m database.hard_openai_extraction.restore_openai_data "$@"
  else
    # Default arguments
    echo -e "${BLUE}Using default settings. Add arguments to customize:${NC}"
    echo "  --batch-dir DIR            Directory with batch files (default: temporary directory)"
    echo "  --disable-source-detection Disable automatic source detection"
    echo "  --disable-web-search       Disable web search for source detection (use only pattern matching)"
    echo "  --web-search-limit NUM     Limit the number of web searches performed in a batch (default: 10)"
    echo "  --cache-size NUM           Maximum size of source detection cache (default: 1000)"
    echo "  --parallel-workers NUM     Number of parallel workers for source detection (default: 5)"
    echo "  --dry-run                  Don't modify database, just show what would happen"
    echo "  --source-id ID             Custom default news source ID (default: 1)"
    echo "  --year YEAR                Year to filter batches (default: 2025)"
    echo ""
    python -m database.hard_openai_extraction.restore_openai_data
  fi
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
    echo -e "${YELLOW}The setup command has been deprecated. Please use './run.sh docker init' instead${NC}"
    echo -e "${BLUE}For a full setup, run:${NC}"
    echo "  ./run.sh docker up    # Start the database container"
    echo "  ./run.sh docker init  # Initialize the database"
    ;;
  docker)
    shift  # Remove the 'docker' command, leaving any arguments
    manage_docker_db "$@"
    ;;
  status)
    shift  # Remove the 'status' command, leaving any arguments
    show_status "$@"
    ;;
  restore_openai)
    shift  # Remove the 'restore_openai' command, leaving any arguments
    restore_openai_data "$@"
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