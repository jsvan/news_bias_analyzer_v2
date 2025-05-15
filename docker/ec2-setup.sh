#!/bin/bash
# EC2 instance setup script for News Bias Analyzer

# Exit on error
set -e

echo "Setting up News Bias Analyzer on EC2..."

# Update system packages
echo "Updating system packages..."
sudo yum update -y || sudo apt-get update -y

# Install Docker
echo "Installing Docker..."
if command -v apt-get &> /dev/null; then
    # Ubuntu/Debian
    sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    sudo apt-get update -y
    sudo apt-get install -y docker-ce
else
    # Amazon Linux
    sudo amazon-linux-extras install docker -y
    sudo service docker start
fi

# Add current user to docker group
sudo usermod -a -G docker $USER

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/download/v2.12.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install AWS CLI
echo "Installing AWS CLI..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip

# Create directories
echo "Creating project directories..."
mkdir -p ~/news-bias-analyzer/data
mkdir -p ~/news-bias-analyzer/logs
mkdir -p ~/news-bias-analyzer/backups

# Set up environment variables
echo "Setting up environment variables..."
cat > ~/.env.template << EOF
# API keys
OPENAI_API_KEY=your_openai_api_key_here

# Database configuration
DB_USER=postgres
DB_PASSWORD=your_secure_password_here
DB_NAME=news_bias
DATABASE_URL=postgresql://\${DB_USER}:\${DB_PASSWORD}@postgres:5432/\${DB_NAME}

# Redis configuration 
REDIS_URL=redis://redis:6379

# JWT Secret for authentication
JWT_SECRET=your_jwt_secret_key_here
JWT_EXPIRE_MINUTES=1440

# AWS configuration (if needed)
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_DEFAULT_REGION=us-east-1

# Docker registry (if using ECR)
ECR_REGISTRY=your_aws_account_id.dkr.ecr.region.amazonaws.com
ECR_REPOSITORY=news-bias-analyzer
IMAGE_TAG=latest

# Monitoring configuration
MONITORING_ENABLED=true
LOGGING_LEVEL=INFO
EOF

echo "Copy .env.template to .env and update with your values"
echo "cp ~/.env.template ~/news-bias-analyzer/.env"

# Install monitoring tools
echo "Installing monitoring tools..."
sudo yum install -y htop || sudo apt-get install -y htop

# Setup CloudWatch agent
echo "Setting up CloudWatch agent..."
if command -v apt-get &> /dev/null; then
    # Ubuntu/Debian
    wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
    sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
    rm ./amazon-cloudwatch-agent.deb
else
    # Amazon Linux
    sudo yum install -y amazon-cloudwatch-agent
fi

# Create a simple health check script
echo "Creating health check script..."
cat > ~/health-check.sh << EOF
#!/bin/bash

API_ENDPOINT="http://localhost:8000/health"
SLACK_WEBHOOK_URL="YOUR_SLACK_WEBHOOK_URL"  # Replace with your actual webhook URL if needed

# Check if the API is responding
response=\$(curl -s -o /dev/null -w "%{http_code}" \$API_ENDPOINT)

if [ \$response -ne 200 ]; then
  # Send alert to Slack if configured
  if [ -n "\$SLACK_WEBHOOK_URL" ] && [ "\$SLACK_WEBHOOK_URL" != "YOUR_SLACK_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' --data "{\\"text\\":\\"❌ News Bias Analyzer API is down! HTTP response: \$response\\"}" \$SLACK_WEBHOOK_URL
  fi
  
  # Log the issue
  echo "\$(date): API health check failed with HTTP code \$response" >> ~/news-bias-analyzer/logs/api-health.log
  
  # Try to restart the API container
  docker restart news-bias-analyzer_api_1 || echo "Failed to restart API container"
else
  echo "\$(date): API health check passed" >> ~/news-bias-analyzer/logs/api-health.log
fi
EOF

chmod +x ~/health-check.sh

# Setup cron job for health check
echo "Setting up health check cron job..."
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/health-check.sh") | crontab -

# Setup database backup cron job
echo "Setting up database backup cron job..."
cat > ~/backup-db.sh << EOF
#!/bin/bash

BACKUP_DIR=~/news-bias-analyzer/backups
TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE=\$BACKUP_DIR/news_bias_\$TIMESTAMP.sql.gz

# Create backup
docker exec news-bias-analyzer_postgres_1 pg_dump -U postgres news_bias | gzip > \$BACKUP_FILE

# Delete backups older than 7 days
find \$BACKUP_DIR -name "news_bias_*.sql.gz" -type f -mtime +7 -delete
EOF

chmod +x ~/backup-db.sh
(crontab -l 2>/dev/null; echo "0 2 * * * ~/backup-db.sh") | crontab -

echo "Setup complete! Next steps:"
echo "1. Copy environment template and update with your values:"
echo "   cp ~/.env.template ~/news-bias-analyzer/.env"
echo "2. Clone your repository or copy your docker-compose file:"
echo "   git clone https://github.com/yourusername/news-bias-analyzer.git"
echo "3. Start your services:"
echo "   cd ~/news-bias-analyzer && docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "Remember to update your health check script with your Slack webhook URL if needed."