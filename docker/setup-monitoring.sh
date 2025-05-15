#!/bin/bash
# Simple script to set up CloudWatch monitoring on EC2 instance

# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
sudo rpm -U ./amazon-cloudwatch-agent.rpm

# Copy the CloudWatch agent configuration
sudo cp cloudwatch-agent-config.json /opt/aws/amazon-cloudwatch-agent/bin/config.json

# Start the CloudWatch agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/bin/config.json

# Create a simple dashboard for monitoring
cat > create-dashboard.sh << 'EOF'
#!/bin/bash

# Get instance ID
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

# Create CloudWatch dashboard
aws cloudwatch put-dashboard --dashboard-name NewsBiasAnalyzer --dashboard-body "{
  \"widgets\": [
    {
      \"type\": \"metric\",
      \"x\": 0,
      \"y\": 0,
      \"width\": 12,
      \"height\": 6,
      \"properties\": {
        \"metrics\": [
          [ \"NewsBiasAnalyzer\", \"cpu_usage_active\", \"InstanceId\", \"$INSTANCE_ID\" ]
        ],
        \"period\": 300,
        \"stat\": \"Average\",
        \"region\": \"$(curl -s http://169.254.169.254/latest/meta-data/placement/region)\",
        \"title\": \"CPU Usage\"
      }
    },
    {
      \"type\": \"metric\",
      \"x\": 0,
      \"y\": 6,
      \"width\": 12,
      \"height\": 6,
      \"properties\": {
        \"metrics\": [
          [ \"NewsBiasAnalyzer\", \"mem_used_percent\", \"InstanceId\", \"$INSTANCE_ID\" ]
        ],
        \"period\": 300,
        \"stat\": \"Average\",
        \"region\": \"$(curl -s http://169.254.169.254/latest/meta-data/placement/region)\",
        \"title\": \"Memory Usage\"
      }
    },
    {
      \"type\": \"metric\",
      \"x\": 12,
      \"y\": 0,
      \"width\": 12,
      \"height\": 6,
      \"properties\": {
        \"metrics\": [
          [ \"NewsBiasAnalyzer\", \"disk_used_percent\", \"InstanceId\", \"$INSTANCE_ID\", \"path\", \"/\" ]
        ],
        \"period\": 300,
        \"stat\": \"Average\",
        \"region\": \"$(curl -s http://169.254.169.254/latest/meta-data/placement/region)\",
        \"title\": \"Disk Usage\"
      }
    },
    {
      \"type\": \"metric\",
      \"x\": 12,
      \"y\": 6,
      \"width\": 12,
      \"height\": 6,
      \"properties\": {
        \"metrics\": [
          [ \"NewsBiasAnalyzer\", \"netstat_tcp_established\", \"InstanceId\", \"$INSTANCE_ID\" ]
        ],
        \"period\": 300,
        \"stat\": \"Average\",
        \"region\": \"$(curl -s http://169.254.169.254/latest/meta-data/placement/region)\",
        \"title\": \"TCP Connections\"
      }
    }
  ]
}"
EOF

chmod +x create-dashboard.sh
./create-dashboard.sh

# Set up a simple health check for the API
cat > health-check.sh << 'EOF'
#!/bin/bash

API_ENDPOINT="http://localhost:8000/health"
SLACK_WEBHOOK_URL="YOUR_SLACK_WEBHOOK_URL"  # Replace with your actual webhook URL

# Check if the API is responding
response=$(curl -s -o /dev/null -w "%{http_code}" $API_ENDPOINT)

if [ $response -ne 200 ]; then
  # Send alert to Slack
  if [ -n "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST -H 'Content-type: application/json' --data "{\"text\":\"❌ News Bias Analyzer API is down! HTTP response: $response\"}" $SLACK_WEBHOOK_URL
  fi
  
  # Log the issue
  echo "$(date): API health check failed with HTTP code $response" >> /var/log/api-health.log
  
  # Try to restart the API container
  docker restart news-bias-analyzer_api_1
else
  echo "$(date): API health check passed" >> /var/log/api-health.log
fi
EOF

chmod +x health-check.sh

# Add the health check to cron to run every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/ec2-user/health-check.sh") | crontab -

echo "Monitoring setup complete!"