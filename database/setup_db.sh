#!/bin/bash
# Database setup script for News Bias Analyzer

set -e  # Exit on any error

# Load environment variables from .env file if it exists
if [ -f ../.env ]; then
  echo "Loading environment variables from ../.env file..."
  set -a
  source ../.env
  set +a
elif [ -f ./.env ]; then
  echo "Loading environment variables from ./.env file..."
  set -a
  source ./.env
  set +a
fi

# Check for DATABASE_URL environment variable
if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL environment variable is not set."
  echo "Please set it before running this script."
  echo "Example:"
  echo "  export DATABASE_URL=\"postgresql://username:password@localhost:5432/news_bias\""
  exit 1
fi

# Print current directory for context
echo "Working directory: $(pwd)"

# Default options
DROP_EXISTING=false
USE_TIMESCALEDB=false
MIGRATIONS_ONLY=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --drop-existing) DROP_EXISTING=true ;;
    --use-timescaledb) USE_TIMESCALEDB=true ;;
    --migrations-only) MIGRATIONS_ONLY=true ;;
    --help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --drop-existing    Drop existing tables before creating new ones"
      echo "  --use-timescaledb  Configure TimescaleDB extension for time-series data"
      echo "  --migrations-only  Only run migrations, don't create tables directly"
      exit 0
      ;;
    *) echo "Unknown parameter: $1"; exit 1 ;;
  esac
  shift
done

# Check if alembic is installed
if ! command -v alembic &> /dev/null; then
  echo "WARNING: alembic command not found."
  echo "You may need to install it using: pip install alembic"
  if [ "$MIGRATIONS_ONLY" = true ]; then
    echo "ERROR: Cannot continue with --migrations-only flag without alembic."
    exit 1
  fi
fi

# Create directory structure if not exists
mkdir -p database/migrations database/seed_data

# Create database if it doesn't exist
DB_NAME=$(echo $DATABASE_URL | sed -E 's/.*\/([^?]+).*/\1/')
DB_USER=$(echo $DATABASE_URL | sed -E 's/.*:\/\/([^:]+).*/\1/')
echo "Checking if database '$DB_NAME' exists..."

if psql -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
  echo "Database '$DB_NAME' already exists."
else
  echo "Creating database '$DB_NAME'..."
  createdb $DB_NAME -O $DB_USER
  echo "Database created."
fi

# Direct table creation using create_tables.py
if [ "$MIGRATIONS_ONLY" = false ]; then
  echo "Creating database tables..."
  
  # Build options string
  OPTIONS=""
  if [ "$DROP_EXISTING" = true ]; then
    OPTIONS="$OPTIONS --drop-existing"
  fi
  if [ "$USE_TIMESCALEDB" = true ]; then
    OPTIONS="$OPTIONS --use-timescaledb"
  fi
  
  python -m database.create_tables $OPTIONS
  echo "Tables created successfully."
fi

# Run migrations
if command -v alembic &> /dev/null; then
  echo "Running database migrations..."
  cd database/migrations
  alembic upgrade head
  cd ../..
  echo "Migrations completed."
fi

# No database seeding - we only use real data

echo "Database setup completed successfully."
exit 0