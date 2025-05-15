# AWS Deployment Guide for News Bias Analyzer

This guide provides steps to deploy the News Bias Analyzer application to AWS infrastructure. The deployment uses Terraform for infrastructure as code and GitHub Actions for CI/CD.

## Prerequisites

Before you begin, make sure you have:

1. An AWS account
2. AWS CLI installed and configured with appropriate credentials
3. Terraform installed (v1.0.0+)
4. GitHub repository with your application code

## Infrastructure Overview

The application is deployed with the following AWS services:

- **RDS**: PostgreSQL database
- **ElastiCache**: Redis for caching and task queues
- **ECR**: Container registry for Docker images
- **S3**: Storage for assets
- **CloudWatch**: Monitoring and logging
- **EC2**: The simplest option is to use a single EC2 instance for a solo developer

## Deployment Steps

### 1. Prepare Local Environment

Clone the repository and set up your environment:

```bash
git clone https://github.com/yourusername/news-bias-analyzer.git
cd news-bias-analyzer
cp .env-example .env
# Edit .env to add your secrets and configuration
```

### 2. Provision AWS Infrastructure using Terraform

```bash
cd terraform
# Create a terraform.tfvars file with your specific values
echo 'db_password = "your-secure-password"' > terraform.tfvars

# Initialize Terraform
terraform init

# Plan the deployment to review changes
terraform plan -out=tfplan

# Apply the changes to create the infrastructure
terraform apply tfplan
```

Terraform will output important information like your RDS endpoint, Redis endpoint, and ECR repository URL. Save these for later configuration.

### 3. Deploy for a Solo Developer (Simple Approach)

For a solo developer with limited resources, the simplest approach is to use a single EC2 instance:

1. Launch an EC2 instance:
   - Use Amazon Linux 2 or Ubuntu Server
   - Instance type: t3.medium (minimum recommended)
   - Storage: At least 30GB gp2
   - Security Group: Allow SSH (port 22), HTTP (port 80), and HTTPS (port 443)

2. Connect to your instance:
   ```bash
   ssh -i your-key.pem ec2-user@your-instance-ip
   ```

3. Install Docker and Docker Compose:
   ```bash
   # For Amazon Linux 2
   sudo yum update -y
   sudo amazon-linux-extras install docker
   sudo service docker start
   sudo usermod -a -G docker ec2-user
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.12.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

4. Clone your repository:
   ```bash
   git clone https://github.com/yourusername/news-bias-analyzer.git
   cd news-bias-analyzer
   ```

5. Create an `.env` file with your configuration:
   ```bash
   cp .env-example .env
   nano .env
   # Add your configuration values, especially the database connection details
   ```

6. Start your application:
   ```bash
   docker-compose up -d
   ```

7. Set up a simple domain with Nginx:
   ```bash
   sudo apt-get install nginx
   sudo nano /etc/nginx/sites-available/default
   ```

   Add the following configuration:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:80;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   Restart Nginx:
   ```bash
   sudo systemctl restart nginx
   ```

8. Set up a free SSL certificate with Let's Encrypt:
   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

### 4. Monitoring and Logging (Simple Setup)

For a simple monitoring setup:

1. Install and configure CloudWatch agent:
   ```bash
   sudo amazon-linux-extras install collectd
   sudo yum install amazon-cloudwatch-agent -y
   ```

2. Create a basic CloudWatch agent configuration:
   ```bash
   sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
   # Follow the prompts to set up basic monitoring
   ```

3. Start the CloudWatch agent:
   ```bash
   sudo systemctl start amazon-cloudwatch-agent
   sudo systemctl enable amazon-cloudwatch-agent
   ```

4. Set up Docker log forwarding to CloudWatch:
   - Modify your docker-compose.yml to use the awslogs log driver:
   ```yaml
   services:
     api:
       # ... other configuration
       logging:
         driver: awslogs
         options:
           awslogs-region: us-east-1
           awslogs-group: news-bias-analyzer-logs
   ```

5. Consider using AWS Elastic Beanstalk for managed deployments, which includes health checks and auto-scaling

### 5. Backup Strategy

1. Set up automated database backups:
   - RDS automated backups (enabled by default for 7 days)
   - Consider setting up a cron job to export your database weekly:
     ```bash
     # Add a cron job to export the database weekly
     echo "0 0 * * 0 docker exec news-bias-analyzer_postgres_1 pg_dump -U postgres news_bias > /backup/db_backup_$(date +\%Y\%m\%d).sql" | crontab -
     ```

2. Set up application code backup:
   - Your code is already in GitHub, which serves as a backup

## Maintenance Tasks

### Regular Updates

1. Update your Docker images:
   ```bash
   # Pull latest images
   docker-compose pull
   # Restart services with new images
   docker-compose up -d
   ```

2. System updates:
   ```bash
   sudo yum update -y
   ```

### Monitoring Health

1. Check your application logs:
   ```bash
   docker-compose logs -f api
   ```

2. Check system health:
   ```bash
   htop
   df -h
   ```

## Troubleshooting

1. If your application can't connect to the database:
   - Check your `.env` file for correct database connection details
   - Verify that the security group allows traffic from your EC2 instance to RDS

2. If you're experiencing high CPU or memory usage:
   - Consider upgrading your EC2 instance type
   - Check for inefficient queries or processes using `docker stats`

## Security Best Practices

1. Keep your system and Docker images updated
2. Use strong passwords and rotate them regularly
3. Restrict access to your EC2 instance (limit SSH access)
4. Use security groups to control traffic
5. Enable CloudTrail for AWS API call monitoring

## Cost Optimization Tips

For a solo developer on a limited budget:

1. Use a single EC2 instance for all services (t3.small or t3.medium)
2. Consider using RDS in the same availability zone as your EC2 instance to avoid data transfer costs
3. Monitor your AWS costs using AWS Cost Explorer
4. Consider using Spot Instances for non-critical workloads
5. Turn off resources when not in use (development environments)