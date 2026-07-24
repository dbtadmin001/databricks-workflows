# AWS K8s Deployment for POS Inventory Analytics

## Overview
Kubernetes manifests for deploying pos_inventory_analytics on AWS EKS with Spark Operator.

## Prerequisites
- EKS cluster with Spark Operator installed
- Delta Lake storage configured (S3)
- Service account with S3 access

## Manifests
- `bronze/` - Bronze layer ingestion jobs
- `silver/` - Silver layer transformation jobs  
- `gold/` - Gold layer aggregation jobs

## Deployment
```bash
kubectl apply -f bronze/
kubectl apply -f silver/
kubectl apply -f gold/
```

## Configuration
Edit each manifest to set:
- S3 paths for data sources
- Spark resource allocations
- Schedule (via CronJob if needed)
