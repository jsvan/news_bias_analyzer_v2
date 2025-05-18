#!/bin/bash
# Database Docker management script for News Bias Analyzer
# This script simplifies running and managing the PostgreSQL database in Docker

set -e  # Exit on any error

# Default action
ACTION=${1:-"up"}

# Function to display help message
show_help() {
  echo "Database Docker Management for News Bias Analyzer"
  echo "Usage: $0 [command] [options]"
  echo ""
  echo "Commands:"
  echo "  up         Start the database container (default)"
  echo "  down       Stop and remove the database container"
  echo "  restart    Restart the database container"
  echo "  status     Show the status of the database container"
  echo "  logs       Show the logs of the database container"
  echo "  backup     Create a backup of the database"
  echo "  restore    Restore the database from a backup"
  echo "  init       Initialize the database schema (run migrations)"
  echo "  shell      Connect to the database with psql"
  echo "  help       Show this help message"
  echo ""
  echo "Options (for init command):"
  echo "  --drop-existing    Drop existing tables before creating new ones"
  echo "  # TimescaleDB is now enabled by default"
}

# Directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CD_ROOT="$SCRIPT_DIR/.."

# Load environment variables
if [ -f "$CD_ROOT/.env" ]; then
  echo "Loading environment variables from .env file..."
  set -a
  source "$CD_ROOT/.env"
  set +a
else
  echo "Warning: No .env file found. Using default values."
  # Set defaults
  export DB_USER="postgres"
  export DB_PASSWORD="postgres"
  export DB_NAME="news_bias"
  export DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
fi

# Function to run docker-compose
run_docker_compose() {
  local cmd="docker-compose -f $CD_ROOT/docker-compose.yml $@ postgres"
  echo "Running: $cmd"
  eval $cmd
}

# Handle different commands
case "$ACTION" in
  up)
    echo "Starting database container..."
    run_docker_compose up -d
    
    echo "Waiting for database to be ready..."
    sleep 5
    
    # Display connection info
    echo ""
    echo "Database is running!"
    echo "Connection Information:"
    echo "  Host: localhost"
    echo "  Port: 5432"
    echo "  User: $DB_USER"
    echo "  Password: $DB_PASSWORD"
    echo "  Database: $DB_NAME"
    echo ""
    echo "Connection string: $DATABASE_URL"
    echo ""
    echo "To initialize the database schema, run: $0 init"
    ;;
    
  down)
    echo "Stopping database container..."
    run_docker_compose down
    echo "Database container stopped."
    ;;
    
  restart)
    echo "Restarting database container..."
    run_docker_compose restart
    echo "Database container restarted."
    ;;
    
  status)
    echo "Database container status:"
    run_docker_compose ps
    ;;
    
  logs)
    echo "Database container logs:"
    run_docker_compose logs -f
    ;;
    
  init)
    echo "Initializing database schema..."
    
    # Ensure the database is running
    run_docker_compose up -d
    
    echo "Waiting for database to be ready..."
    sleep 10
    
    # Set environment variables for database connection
    if [ -z "$DB_USER" ]; then
      export DB_USER="postgres"
    fi
    if [ -z "$DB_PASSWORD" ]; then
      export DB_PASSWORD="postgres"
    fi
    if [ -z "$DB_NAME" ]; then
      export DB_NAME="news_bias"
    fi
    if [ -z "$DATABASE_URL" ]; then
      export DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
    fi
    
    echo "Creating database and tables..."
    
    # Execute SQL commands directly in the PostgreSQL container
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec -T postgres psql -U $DB_USER -c "CREATE DATABASE $DB_NAME WITH OWNER $DB_USER;" postgres || echo "Database may already exist, continuing..."
    
    # Run Python script for creating tables
    cd "$CD_ROOT"
    
    # Prepare options for create_tables.py
    OPTIONS="--use-timescaledb"  # Always use TimescaleDB by default
    if [[ "$*" == *"--drop-existing"* ]]; then
      OPTIONS="$OPTIONS --drop-existing"
    fi
    
    # Run the create_tables.py script
    echo "Running table creation script..."
    python -m database.create_tables $OPTIONS
    
    # Run migrations if alembic is installed
    if command -v alembic &> /dev/null; then
      echo "Running database migrations..."
      cd "$SCRIPT_DIR/migrations"
      
      # Function to safely run migrations and handle errors gracefully
      run_migrations() {
        local config_path="$1"
        local config_arg=""
        if [ -n "$config_path" ]; then
          config_arg="-c $config_path"
        fi
        
        # First check if we're at the latest revision already
        if alembic $config_arg current | grep -q "(head)"; then
          echo "Database is already at the latest revision. No migrations needed."
          return 0
        fi
        
        # Run migrations and capture output and return code
        local migration_output
        migration_output=$(alembic $config_arg upgrade head 2>&1) || {
          local ret=$?
          
          # If there was an error, check if it was just a "table already exists" error
          if echo "$migration_output" | grep -q "relation.*already exists"; then
            echo "Tables already exist. This is normal for an existing database."
            echo "Stamping database as up-to-date..."
            alembic $config_arg stamp head
            echo "Database marked as up-to-date."
            return 0
          else
            # For other errors, show the output and return the error code
            echo "Migration failed with:"
            echo "$migration_output"
            return $ret
          fi
        }
        
        # If we got here, migrations succeeded
        echo "Migrations completed successfully."
        return 0
      }
      
      # Try to run migrations with the appropriate config
      if [ -f "alembic.ini" ]; then
        run_migrations
        cd "$CD_ROOT"
      else
        cd "$CD_ROOT"
        echo "alembic.ini not found in $SCRIPT_DIR/migrations. Looking in parent directory..."
        if [ -f "$SCRIPT_DIR/alembic.ini" ]; then
          cd "$SCRIPT_DIR"
          run_migrations "alembic.ini"
          cd "$CD_ROOT"
        else
          echo "alembic.ini not found. Skipping migrations."
          echo "Please ensure alembic.ini is in the database or database/migrations directory."
        fi
      fi
    else
      echo "Alembic not found. Skipping migrations."
      echo "To run migrations, install alembic: pip install alembic"
    fi
    
    echo "Database initialization complete."
    ;;
    
  backup)
    echo "Creating database backup..."
    BACKUP_FILE="$CD_ROOT/backups/news_bias_$(date +%Y%m%d_%H%M%S).sql"
    
    # Create backup directory if it doesn't exist
    mkdir -p "$CD_ROOT/backups"
    
    # Use docker exec to run pg_dump
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      pg_dump -U $DB_USER $DB_NAME > "$BACKUP_FILE"
    
    echo "Backup created: $BACKUP_FILE"
    ;;
    
  restore)
    # Check if a backup file was provided
    if [ -z "$2" ]; then
      echo "Error: No backup file specified."
      echo "Usage: $0 restore <backup_file>"
      exit 1
    fi
    
    BACKUP_FILE="$2"
    if [ ! -f "$BACKUP_FILE" ]; then
      # Try with full path if relative path doesn't work
      BACKUP_FILE="$CD_ROOT/backups/$2"
      if [ ! -f "$BACKUP_FILE" ]; then
        echo "Error: Backup file not found: $2"
        exit 1
      fi
    fi
    
    echo "Restoring database from backup: $BACKUP_FILE"
    
    # Drop and recreate the database
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      psql -U $DB_USER -c "DROP DATABASE IF EXISTS ${DB_NAME}_temp;"
    
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      psql -U $DB_USER -c "CREATE DATABASE ${DB_NAME}_temp;"
    
    # Restore to temporary database first to avoid active connection issues
    cat "$BACKUP_FILE" | docker-compose -f "$CD_ROOT/docker-compose.yml" exec -T postgres \
      psql -U $DB_USER -d ${DB_NAME}_temp
    
    # Terminate all connections to the main database
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      psql -U $DB_USER -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();"
    
    # Drop and recreate the main database
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      psql -U $DB_USER -c "DROP DATABASE IF EXISTS $DB_NAME;"
    
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      psql -U $DB_USER -c "CREATE DATABASE $DB_NAME WITH TEMPLATE ${DB_NAME}_temp;"
    
    # Clean up temporary database
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      psql -U $DB_USER -c "DROP DATABASE ${DB_NAME}_temp;"
    
    echo "Database restored successfully!"
    ;;
    
  shell)
    echo "Connecting to database with psql..."
    docker-compose -f "$CD_ROOT/docker-compose.yml" exec postgres \
      psql -U $DB_USER -d $DB_NAME
    ;;
    
  help|--help|-h)
    show_help
    ;;
    
  *)
    echo "Unknown command: $ACTION"
    show_help
    exit 1
    ;;
esac