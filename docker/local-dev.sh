#!/bin/bash
# Helper script for local development

# Default values
ACTION="up"
SERVICES=""
DETACH=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        up|down|restart|logs|ps) ACTION="$1"; shift ;;
        -d|--detach) DETACH=true; shift ;;
        api|frontend|worker|scraper|scheduler|redis|postgres) 
            if [ -z "$SERVICES" ]; then
                SERVICES="$1"
            else
                SERVICES="$SERVICES $1"
            fi
            shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
done

# Check if .env file exists, create if not
if [ ! -f .env ]; then
    echo "No .env file found. Creating from .env-example..."
    cp .env-example .env
    echo "Please edit .env file with your configuration values."
    exit 1
fi

# Function to run docker-compose with appropriate options
run_docker_compose() {
    local cmd="docker-compose"
    
    case $ACTION in
        up)
            cmd="$cmd up"
            if [ "$DETACH" = true ]; then
                cmd="$cmd -d"
            fi
            ;;
        down)
            cmd="$cmd down"
            ;;
        restart)
            cmd="$cmd restart"
            ;;
        logs)
            cmd="$cmd logs"
            if [ "$DETACH" = false ]; then
                cmd="$cmd -f"
            fi
            ;;
        ps)
            cmd="$cmd ps"
            ;;
    esac
    
    # Add services if specified
    if [ ! -z "$SERVICES" ]; then
        cmd="$cmd $SERVICES"
    fi
    
    # Run the command
    echo "Running: $cmd"
    eval $cmd
}

# Display project status
display_status() {
    echo "News Bias Analyzer - Local Development"
    echo "--------------------------------------"
    echo "Action: $ACTION"
    if [ ! -z "$SERVICES" ]; then
        echo "Services: $SERVICES"
    else
        echo "Services: all"
    fi
    echo ""
}

# Main execution
display_status
run_docker_compose

if [ "$ACTION" = "up" ] && [ "$DETACH" = true ]; then
    echo ""
    echo "Services started in detached mode."
    echo "  - API should be available at: http://localhost:8000"
    echo "  - Frontend should be available at: http://localhost:3000"
    echo "  - Flower dashboard should be available at: http://localhost:5555"
    echo ""
    echo "Use './docker/local-dev.sh logs' to view logs."
fi