#!/bin/bash
# Manual deployment script for News Bias Analyzer

# Set default values
ENV="prod"
TARGET_HOST=""
SSH_KEY=""
SSH_USER="ec2-user"
REMOTE_DIR="~/news-bias-analyzer"

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --env) ENV="$2"; shift ;;
        --host) TARGET_HOST="$2"; shift ;;
        --key) SSH_KEY="$2"; shift ;;
        --user) SSH_USER="$2"; shift ;;
        --dir) REMOTE_DIR="$2"; shift ;;
        --help) 
            echo "Usage: deploy.sh [options]"
            echo ""
            echo "Options:"
            echo "  --env ENV       Deployment environment (dev, staging, prod) [default: prod]"
            echo "  --host HOST     Target server hostname or IP address [required]"
            echo "  --key KEY       Path to SSH private key [required]"
            echo "  --user USER     SSH username [default: ec2-user]"
            echo "  --dir DIR       Remote directory [default: ~/news-bias-analyzer]"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Check required arguments
if [ -z "$TARGET_HOST" ]; then
    echo "Error: Target host is required (--host)"
    exit 1
fi

if [ -z "$SSH_KEY" ]; then
    echo "Error: SSH key is required (--key)"
    exit 1
fi

# Display deployment info
echo "News Bias Analyzer - Deployment"
echo "------------------------------"
echo "Environment: $ENV"
echo "Target Host: $TARGET_HOST"
echo "SSH User: $SSH_USER"
echo "Remote Directory: $REMOTE_DIR"
echo ""

# Build Docker images (if local deployment)
if [ "$ENV" = "dev" ]; then
    echo "Building Docker images locally..."
    docker-compose build
    echo "Docker images built successfully!"
fi

# Create deployment directory
echo "Creating deployment package..."
DEPLOY_DIR=$(mktemp -d)
mkdir -p "$DEPLOY_DIR/docker"

# Copy necessary files
cp docker-compose.prod.yml "$DEPLOY_DIR/"
cp .env-example "$DEPLOY_DIR/.env-example"
cp docker/*.Dockerfile "$DEPLOY_DIR/docker/"
cp docker/nginx.conf "$DEPLOY_DIR/docker/"
cp docker/setup-monitoring.sh "$DEPLOY_DIR/docker/"
cp docker/cloudwatch-agent-config.json "$DEPLOY_DIR/docker/"

# Create deploy script for remote execution
cat > "$DEPLOY_DIR/remote-deploy.sh" << 'EOF'
#!/bin/bash
set -e

# Change to project directory
cd ~/news-bias-analyzer

# Ensure .env file exists
if [ ! -f .env ]; then
    cp .env-example .env
    echo "Created .env file from template. Please update it with your values."
    exit 1
fi

# Stop services if they're running
docker-compose -f docker-compose.prod.yml down || true

# Pull latest images (if using registry)
if grep -q "ECR_REGISTRY" .env; then
    source .env
    if [ ! -z "$ECR_REGISTRY" ] && [ ! -z "$AWS_ACCESS_KEY_ID" ]; then
        echo "Logging in to ECR..."
        aws ecr get-login-password --region ${AWS_DEFAULT_REGION:-us-east-1} | docker login --username AWS --password-stdin $ECR_REGISTRY
        echo "Pulling latest images..."
        images=("api" "frontend" "worker" "scraper" "scheduler")
        for img in "${images[@]}"; do
            docker pull $ECR_REGISTRY/$ECR_REPOSITORY:$img-${IMAGE_TAG:-latest} || echo "Warning: Failed to pull $img image"
        done
    fi
fi

# Start services
echo "Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Setup monitoring if needed
if [ -f docker/setup-monitoring.sh ]; then
    echo "Setting up monitoring..."
    chmod +x docker/setup-monitoring.sh
    docker/setup-monitoring.sh
fi

echo "Deployment completed successfully!"
EOF

chmod +x "$DEPLOY_DIR/remote-deploy.sh"

# Copy files to the remote server
echo "Copying files to remote server..."
rsync -avz --delete -e "ssh -i $SSH_KEY" \
    "$DEPLOY_DIR/" "$SSH_USER@$TARGET_HOST:$REMOTE_DIR"

# Execute remote deployment script
echo "Executing deployment on remote server..."
ssh -i "$SSH_KEY" "$SSH_USER@$TARGET_HOST" "chmod +x $REMOTE_DIR/remote-deploy.sh && $REMOTE_DIR/remote-deploy.sh"

# Clean up temporary directory
rm -rf "$DEPLOY_DIR"

echo "Deployment completed!"
echo "To check the status of your deployment:"
echo "ssh -i $SSH_KEY $SSH_USER@$TARGET_HOST 'cd $REMOTE_DIR && docker-compose -f docker-compose.prod.yml ps'"