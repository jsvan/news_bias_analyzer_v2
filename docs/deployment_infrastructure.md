# News Bias Analyzer - Deployment Infrastructure

This document provides an overview of the deployment infrastructure for the News Bias Analyzer project.

## Overview

The News Bias Analyzer is deployed using:

1. **Docker containers** for all services
2. **AWS** for cloud infrastructure
3. **GitHub Actions** for CI/CD
4. **CloudWatch** for monitoring and logging

## Docker Configuration

All services are containerized using Docker. Each service has its own Dockerfile:

- `api.Dockerfile`: FastAPI backend API service
- `frontend.Dockerfile`: React dashboard frontend
- `worker.Dockerfile`: Celery worker for background tasks
- `scraper.Dockerfile`: Web scraper for collecting news articles
- `scheduler.Dockerfile`: Celery beat scheduler for periodic tasks
- `flower.Dockerfile`: Celery monitoring dashboard

The services are orchestrated using Docker Compose:
- `docker-compose.yml`: For local development
- `docker-compose.prod.yml`: For production deployment

## AWS Infrastructure

The application is deployed on AWS using the following services:

- **EC2**: Compute instances for running Docker containers
- **RDS**: PostgreSQL database
- **ElastiCache**: Redis for caching and task queues
- **ECR**: Container registry for Docker images
- **S3**: Storage for assets and backups
- **CloudWatch**: Monitoring and logging
- **CloudFormation/Terraform**: Infrastructure as code

### Terraform Configuration

The `terraform` directory contains all the infrastructure as code:

- `main.tf`: Main Terraform configuration
- `variables.tf`: Variable definitions

## CI/CD Pipeline

Continuous Integration and Deployment is handled by GitHub Actions:

1. **Build**: Runs tests, builds Docker images
2. **Push**: Pushes Docker images to Amazon ECR
3. **Deploy**: Deploys the application to AWS

The workflow is defined in `.github/workflows/ci-cd.yml`.

## Monitoring and Logging

### CloudWatch Setup

Monitoring and logging are handled by CloudWatch:

- **Logs**: All container logs are forwarded to CloudWatch Logs
- **Metrics**: System and application metrics are collected
- **Alarms**: Alerts are set up for critical metrics
- **Dashboard**: Custom dashboard for visualizing metrics

### Health Checks

Health checks are performed regularly to ensure services are running correctly:

- API endpoint monitoring
- Database connection checks
- Redis connection checks

## Local Development

For local development:

1. Clone the repository
2. Copy `.env-example` to `.env` and update values
3. Use the helper script:

```bash
# Start all services
./docker/local-dev.sh up

# View logs
./docker/local-dev.sh logs

# Start specific services
./docker/local-dev.sh up api frontend

# Stop all services
./docker/local-dev.sh down
```

## Deployment Guide

For detailed deployment instructions, see:

- [AWS Deployment Guide](aws_deployment.md): Step-by-step guide for AWS deployment
- [Monitoring Guide](monitoring_guide.md): Setting up monitoring and logging

## Security Considerations

The deployment infrastructure is designed with security in mind:

1. **Database**: Isolated in private subnet with access only from application
2. **Secrets**: Managed through environment variables and AWS Secrets Manager
3. **Network**: Security groups limit access to services
4. **HTTPS**: SSL/TLS encryption for all external communication

## Backup and Recovery

Backup procedures are implemented for:

1. **Database**: Automated daily backups using RDS snapshots
2. **Application Data**: Stored in S3 with versioning enabled
3. **Configuration**: Tracked in version control

## For Solo Developers

For solo developers on a budget:

1. Use a single EC2 instance (t3.small or t3.medium) for all services
2. Use RDS in the same availability zone to avoid data transfer costs
3. Monitor AWS costs using Cost Explorer
4. Consider using EC2 Spot Instances for non-critical workloads
5. Turn off development resources when not in use

## Future Scaling Considerations

As the project grows, consider these scaling options:

1. **ECS/EKS**: Move from single EC2 to container orchestration
2. **Load Balancing**: Add Application Load Balancer for high availability
3. **Auto Scaling**: Set up auto-scaling groups for dynamic capacity
4. **CDN**: Use CloudFront for frontend content delivery
5. **Multi-AZ**: Deploy across multiple availability zones for resilience