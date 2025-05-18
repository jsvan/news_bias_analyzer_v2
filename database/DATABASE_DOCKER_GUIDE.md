# News Bias Analyzer - Database Docker Guide

This document explains how to use the Docker-based database setup for the News Bias Analyzer project, including best practices for managing database persistence.

## Overview

The database setup uses Docker to run a PostgreSQL instance with the TimescaleDB extension from the main docker-compose.yml file. The setup provides:

1. **Data Persistence**: Data is stored in a named Docker volume
2. **Simplified Management**: A script for common database operations
3. **Backup & Restore**: Easy commands for backing up and restoring data
4. **Database Initialization**: Schema setup via migrations

## Quick Start

```bash
# Start the database
./database/db-docker.sh up

# Initialize the database schema (run migrations)
./database/db-docker.sh init

# Check the status
./database/db-docker.sh status

# Stop the database
./database/db-docker.sh down
```

## Understanding Database Persistence

The most important aspect of this setup is how database persistence works:

### How Docker Volumes Work

Docker volumes are the preferred way to persist data generated and used by Docker containers. The setup uses a named volume `postgres_data` to store PostgreSQL data.

#### Key Points:

1. **Named Volume**: Unlike a bind mount, a named volume is managed by Docker
2. **Persistence Across Restarts**: Data remains intact when containers are restarted
3. **Protection from Container Removal**: Data persists even if the container is removed
4. **Independent of Container Lifecycle**: Volumes have a separate lifecycle from containers

### Potential Issues with Database Persistence

If you're experiencing data loss, it could be due to one of these issues:

1. **Volume Pruning**: Running `docker volume prune` will delete unused volumes
2. **Explicit Volume Deletion**: Running `docker volume rm postgres_data` will delete the volume
3. **Force Removal with Container**: Using `docker-compose down -v` will remove volumes
4. **Docker Desktop Reset**: Resetting Docker Desktop will delete all volumes

### Best Practices for Database Persistence

1. **Regular Backups**: Use the backup command (`./database/db-docker.sh backup`)
2. **Avoid Pruning**: Be cautious with Docker cleanup commands
3. **Use Explicit Volume Names**: This setup uses a named volume for clarity
4. **Data Migration**: For full system rebuilds, backup before and restore after

## Complete Command Reference

### Basic Operations

- **Start the database**: `./database/db-docker.sh up`
- **Stop the database**: `./database/db-docker.sh down`
- **Restart the database**: `./database/db-docker.sh restart`
- **Check database status**: `./database/db-docker.sh status`
- **View database logs**: `./database/db-docker.sh logs`

### Database Management

- **Initialize schema**: `./database/db-docker.sh init`
- **Open psql shell**: `./database/db-docker.sh shell`
- **Create backup**: `./database/db-docker.sh backup`
- **Restore from backup**: `./database/db-docker.sh restore <backup_file>`

### Advanced Options

For initialization, you can use these options:

- **Drop existing tables**: `./database/db-docker.sh init --drop-existing`
- **Use TimescaleDB**: `./database/db-docker.sh init --use-timescaledb`

## Troubleshooting

### Connection Issues

If you can't connect to the database:

1. Verify the container is running: `./database/db-docker.sh status`
2. Check logs for errors: `./database/db-docker.sh logs`
3. Ensure port 5432 is not in use by another service
4. Confirm your .env settings match what you're using to connect

### Data Loss

If you're experiencing data loss:

1. Check if the volume exists: `docker volume ls | grep postgres_data`
2. If it doesn't exist, it may have been pruned or deleted
3. Restore from your most recent backup if available
4. If no backup is available, you'll need to recreate your data

## Architecture Decisions

This setup was designed with these principles in mind:

1. **Simplicity**: Focused on just running the database, separate from other services
2. **Robustness**: Using Docker best practices for data persistence
3. **Flexibility**: Allowing for easy extension (TimescaleDB, etc.)
4. **Maintainability**: Simple script interface for common operations

## Schema Management

Database schema is managed through:

1. **Alembic Migrations**: Found in `database/migrations/versions/`
2. **Model Definitions**: Found in `database/models.py`

When making schema changes, create a new migration file rather than modifying existing ones.