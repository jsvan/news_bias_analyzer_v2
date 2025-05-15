# Monitoring and Logging Guide for News Bias Analyzer

As a solo developer with limited resources, this guide provides simple but effective methods to monitor your News Bias Analyzer application.

## Simple Monitoring Solutions

### 1. CloudWatch Basic Monitoring (Free Tier Compatible)

AWS CloudWatch offers basic monitoring for EC2 instances at no additional cost. This includes:

- CPU utilization
- Disk I/O
- Network I/O

**Setup Instructions:**

1. The `setup-monitoring.sh` script in the `docker` directory sets up basic CloudWatch monitoring.
2. It also creates a simple dashboard for visualizing metrics.
3. To set it up on your EC2 instance:

```bash
cd ~/news-bias-analyzer/docker
chmod +x setup-monitoring.sh
./setup-monitoring.sh
```

### 2. Health Check Script

A simple health check script is included that:
- Pings your API endpoint every 5 minutes
- Logs the results
- Attempts to restart the container if it's unresponsive
- Sends an alert via Slack (if configured)

**Customizing the Health Check:**

Edit the `health-check.sh` script to customize:
- The API endpoint to check
- The Slack webhook URL for notifications
- The restart behavior

### 3. Log Management

#### Docker Logs

Docker logs are configured with rotation to prevent disk space issues:

```bash
# View logs for a specific service
docker-compose -f docker-compose.prod.yml logs api

# Follow logs in real-time
docker-compose -f docker-compose.prod.yml logs -f api

# View logs from the last hour
docker-compose -f docker-compose.prod.yml logs --since 1h api
```

#### System Monitoring Tools

These simple command-line tools can help monitor your system:

```bash
# Monitor system resources in real-time
htop

# Check disk space
df -h

# Monitor active network connections
netstat -tuln

# View active Docker containers and their resource usage
docker stats
```

### 4. Notification Setup

#### Slack Notifications

1. Create a Slack workspace if you don't have one
2. Create a new channel for alerts (e.g., #news-bias-alerts)
3. Add a new Incoming Webhook integration
4. Copy the webhook URL to your health check script

#### Email Alerts

For critical errors, you can set up email alerts using a simple script:

```bash
# Add to your crontab
0 * * * * /bin/bash -c 'if ! curl -s http://localhost:8000/health | grep -q "ok"; then echo "API is down!" | mail -s "ALERT: News Bias Analyzer API Down" your-email@example.com; fi'
```

## Database Monitoring

### PostgreSQL Monitoring

1. Check database size:
```bash
docker exec news-bias-analyzer_postgres_1 psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('news_bias'));"
```

2. Check active connections:
```bash
docker exec news-bias-analyzer_postgres_1 psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

3. Identify slow queries:
```bash
docker exec news-bias-analyzer_postgres_1 psql -U postgres -c "SELECT query, calls, total_time, rows, 100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent FROM pg_stat_statements ORDER BY total_time DESC LIMIT 5;"
```

## Application Monitoring

### Backend API Monitoring

1. Check API status:
```bash
curl http://localhost:8000/health
```

2. Monitor error rates:
```bash
# Count error logs in the last hour
docker-compose -f docker-compose.prod.yml logs --since 1h api | grep -i error | wc -l
```

### Frontend Dashboard Monitoring

1. Check if the frontend is serving properly:
```bash
curl -I http://localhost
```

## Backup Procedures

### Database Backup

1. Manual backup:
```bash
docker exec news-bias-analyzer_postgres_1 pg_dump -U postgres news_bias > backup-$(date +%Y%m%d).sql
```

2. Set up automated daily backups:
```bash
# Add to crontab
0 3 * * * docker exec news-bias-analyzer_postgres_1 pg_dump -U postgres news_bias | gzip > /backups/news_bias_$(date +\%Y\%m\%d).sql.gz
```

### Application Backup

Your code should be in version control (GitHub), but you can also back up your configuration:

```bash
# Backup your environment variables
cp .env .env.backup-$(date +%Y%m%d)

# Backup your docker-compose configuration
cp docker-compose.prod.yml docker-compose.prod.yml.backup-$(date +%Y%m%d)
```

## Cost-Effective Alternative Monitoring Services

If you want more comprehensive monitoring without significant cost:

1. **Datadog** - Has a free tier that includes:
   - 5 hosts
   - 1-day metric retention
   - Basic dashboards

2. **New Relic** - Free tier includes:
   - 100 GB/month of data ingest
   - 1 full-access user
   - 8-day data retention

3. **Grafana Cloud** - Free tier includes:
   - 3 users
   - 10K series metrics
   - 14-day retention

## Setting Up Grafana Cloud (Simple Option)

Grafana Cloud is a good option for a solo developer because:
- It's free for basic usage
- It's easy to set up
- It can monitor both your infrastructure and application

**Setup Steps:**

1. Sign up for a free Grafana Cloud account at https://grafana.com/auth/sign-up/create-user
2. Install the Grafana agent on your EC2 instance:

```bash
wget -q -O - https://apt.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install grafana-agent
```

3. Configure the agent using the credentials from your Grafana Cloud account:

```bash
sudo grafana-agent -config.file=/etc/grafana-agent.yaml
```

4. Access your Grafana dashboard to view metrics

## Troubleshooting Common Issues

### High CPU Usage

If you notice high CPU usage:

1. Identify the problematic container:
```bash
docker stats
```

2. Check for potential issues:
```bash
# Check logs for the container
docker-compose -f docker-compose.prod.yml logs worker

# Connect to the container and check processes
docker exec -it news-bias-analyzer_worker_1 ps aux
```

### Memory Issues

If your application is running out of memory:

1. Check memory usage:
```bash
free -h
```

2. Adjust container memory limits in docker-compose.prod.yml:
```yaml
services:
  api:
    # ... other configuration
    deploy:
      resources:
        limits:
          memory: 512M
```

### Database Connection Issues

If services can't connect to the database:

1. Check if PostgreSQL is running:
```bash
docker ps | grep postgres
```

2. Verify connection parameters:
```bash
docker exec news-bias-analyzer_api_1 env | grep DATABASE_URL
```

3. Test the connection directly:
```bash
docker exec news-bias-analyzer_api_1 python -c "import psycopg2; conn = psycopg2.connect('postgresql://postgres:postgres@postgres:5432/news_bias'); print('Connection successful')"
```

## Conclusion

This monitoring setup provides a good balance between effectiveness and simplicity for a solo developer. As your application grows, you may want to consider more sophisticated monitoring solutions, but this setup should serve you well in the early stages.