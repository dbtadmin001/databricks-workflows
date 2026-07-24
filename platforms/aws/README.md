# AWS Platform Adapter — Spark on Kubernetes

**Run the same PySpark transformations from `src/core/` on AWS EKS with Spark Operator.**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ src/core/transformations/  (Shared PySpark Logic)           │
│   ├── bronze/  → Ingestion                                  │
│   ├── silver/  → Enrichment + DQ                            │
│   └── gold/    → Aggregations                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
          Containerized in Docker image
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ AWS EKS + Spark Operator                                     │
│   ├── SparkApplication CRDs (K8s manifests)                 │
│   ├── Autoscaling node groups (m5.xlarge SPOT)              │
│   └── IRSA for S3 access                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
            Delta Lake tables in S3
```

## Why EKS + Spark Operator?

See [AWS_ORCHESTRATION_DECISION.md](AWS_ORCHESTRATION_DECISION.md) for the full evaluation.

**TL;DR**:
* ✅ Open source and portable (not AWS-locked)
* ✅ K8s-native (standard orchestration)
* ✅ Cost-effective (autoscale to zero between jobs)
* ✅ Reproducible (digest-pinned images)
* ❌ Rejected EMR on EKS, EMR Serverless, AWS Glue (vendor lock-in, less control)

## Directory Structure

```
platforms/aws/
├── AWS_ORCHESTRATION_DECISION.md    Orchestration choice rationale
├── README.md                          This file
├── docker/
│   └── Dockerfile                     PySpark job image (digest-pinned)
├── k8s/
│   ├── spark-operator/                Helm values for Spark Operator
│   ├── manifests/                     SparkApplication CRDs
│   │   ├── bronze/                    Bronze ingestion jobs
│   │   ├── silver/                    Silver enrichment jobs
│   │   └── gold/                      Gold aggregation jobs
│   └── config/                        K8s config (namespaces, RBAC, secrets)
├── terraform/
│   ├── modules/                       Reusable Terraform modules
│   │   ├── eks/                       EKS cluster
│   │   ├── vpc/                       VPC networking
│   │   ├── iam/                       IAM roles (cluster, nodes, IRSA)
│   │   └── s3/                        S3 buckets for Delta Lake
│   └── environments/                  Environment-specific configs
│       ├── dev/                       Development environment
│       ├── test/                      Test environment
│       └── prod/                      Production environment
└── scripts/                           Deployment and utility scripts
```

## Prerequisites

* **AWS CLI** configured with credentials
* **kubectl** (Kubernetes CLI)
* **Terraform** >= 1.5.0
* **Helm** (Kubernetes package manager)
* **Docker** (for building images)

## Setup — Step by Step

### 1. Provision Infrastructure (Terraform)

```bash
cd platforms/aws/terraform/environments/dev

# Initialize Terraform
terraform init

# Review plan
terraform plan -out=tfplan

# Apply
terraform apply tfplan
```

This creates:
* EKS cluster (Kubernetes 1.28)
* VPC with public/private subnets
* IAM roles (cluster, nodes, IRSA for S3)
* S3 bucket for Delta Lake storage
* S3 bucket for Spark event logs

### 2. Configure kubectl

```bash
# Update kubeconfig to point to EKS cluster
aws eks update-kubeconfig --name pos-retail-dev --region us-east-1

# Verify connection
kubectl get nodes
```

### 3. Install Spark Operator

```bash
# Add Spark Operator Helm repo
helm repo add spark-operator https://kubeflow.github.io/spark-operator
helm repo update

# Install Spark Operator
helm install spark-operator spark-operator/spark-operator \
  --namespace spark-operator \
  --create-namespace \
  --set webhook.enable=true \
  --set metrics.enable=true

# Verify installation
kubectl get pods -n spark-operator
```

### 4. Create Spark Jobs Namespace

```bash
kubectl create namespace spark-jobs

# Create service account with S3 access (IRSA)
kubectl apply -f k8s/config/spark-service-account.yaml
```

### 5. Build and Push Docker Image

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ECR_REGISTRY>

# Build image
docker build -f docker/Dockerfile -t pos-retail-spark:$(git rev-parse --short HEAD) ../..

# Tag for ECR
docker tag pos-retail-spark:$(git rev-parse --short HEAD) <ECR_REGISTRY>/pos-retail-spark:$(git rev-parse --short HEAD)
docker tag pos-retail-spark:$(git rev-parse --short HEAD) <ECR_REGISTRY>/pos-retail-spark:latest

# Push
docker push <ECR_REGISTRY>/pos-retail-spark:$(git rev-parse --short HEAD)
docker push <ECR_REGISTRY>/pos-retail-spark:latest
```

### 6. Deploy Spark Jobs

```bash
# Update manifests with current image SHA
export GIT_SHA=$(git rev-parse --short HEAD)
export ECR_REGISTRY="<YOUR_ECR_REGISTRY>"

for file in k8s/manifests/*/*.yaml; do
  sed -i "s|<GIT_SHA>|$GIT_SHA|g" $file
  sed -i "s|<ECR_REGISTRY>|$ECR_REGISTRY|g" $file
done

# Apply manifests
kubectl apply -f k8s/manifests/bronze/
kubectl apply -f k8s/manifests/silver/
kubectl apply -f k8s/manifests/gold/

# Watch job status
kubectl get sparkapplications -n spark-jobs -w
```

## Running Jobs

### Trigger a Job Manually

```bash
# Bronze ingestion
kubectl apply -f k8s/manifests/bronze/pos-retail-bronze.yaml

# Watch logs
kubectl logs -f -n spark-jobs <POD_NAME> -c spark-kubernetes-driver
```

### Job Dependencies

Jobs must run in order:
1. **Bronze** — Ingest raw data from source → S3
2. **Silver** — Enrich + apply DQ rules → S3
3. **Gold** — Aggregate metrics → S3

Use a workflow orchestrator (Argo Workflows, Airflow) for dependencies in production.

## Monitoring

### View Running Jobs

```bash
kubectl get sparkapplications -n spark-jobs
```

### Check Spark UI

```bash
# Port-forward to Spark driver UI
kubectl port-forward -n spark-jobs <DRIVER_POD> 4040:4040

# Open http://localhost:4040 in browser
```

### View Logs

```bash
# Driver logs
kubectl logs -n spark-jobs <DRIVER_POD> -c spark-kubernetes-driver

# Executor logs
kubectl logs -n spark-jobs <EXECUTOR_POD> -c spark-kubernetes-executor
```

## Cost Optimization

### Autoscaling

Node groups scale to zero when no jobs are running:
* **Min nodes**: 0
* **Desired nodes**: 2 (when jobs run)
* **Max nodes**: 10

### Spot Instances

Node groups use SPOT capacity by default (70% cheaper than on-demand).

**Trade-off**: Jobs may be interrupted if AWS reclaims capacity.

**Mitigation**: Spark checkpointing + retry policy in SparkApplication manifests.

### Shutdown Cluster

```bash
cd platforms/aws/terraform/environments/dev
terraform destroy
```

## Troubleshooting

### Problem: SparkApplication stuck in "Pending"

**Cause**: No nodes available or insufficient resources.

**Solution**:
```bash
# Check node status
kubectl get nodes

# Check pod events
kubectl describe pod -n spark-jobs <POD_NAME>

# Scale node group manually
kubectl scale deployment -n kube-system cluster-autoscaler --replicas=1
```

### Problem: "Access Denied" errors on S3

**Cause**: IRSA not configured correctly.

**Solution**:
```bash
# Verify service account annotations
kubectl describe sa spark-job-sa -n spark-jobs

# Check IAM role trust policy
aws iam get-role --role-name SparkJobRole
```

### Problem: Image pull errors

**Cause**: ECR authentication expired or image doesn't exist.

**Solution**:
```bash
# Re-authenticate with ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ECR_REGISTRY>

# Verify image exists
aws ecr describe-images --repository-name pos-retail-spark
```

## CI/CD Integration

See `.github/workflows/deploy-aws.yml` (to be created) for automated deployments.

**Workflow**:
1. Build Docker image with Git SHA tag
2. Push to ECR
3. Update K8s manifests with new image SHA
4. Apply manifests to EKS

## Comparison with Databricks

| Feature | Databricks | AWS EKS + Spark |
|---------|-----------|-----------------|
| **Cost** | $$ (DBUs + compute) | $ (compute only) |
| **Setup** | Managed (5 min) | Self-managed (1-2 hours) |
| **Spark Version** | Databricks Runtime | Open source Spark 3.5 |
| **Notebooks** | Built-in | Not included (use Jupyter separately) |
| **Monitoring** | Built-in UI | K8s tooling + Spark History Server |
| **Portability** | Databricks-only | Runs on any K8s (GKE, AKS, on-prem) |

**When to use EKS**:
* Cost-sensitive batch workloads
* Need K8s standardization
* Want open source stack

**When to use Databricks**:
* Interactive analysis (notebooks)
* Streaming workloads
* Prefer managed platform

## Future Enhancements

* [ ] Argo Workflows for job orchestration
* [ ] Prometheus + Grafana for monitoring
* [ ] Spark History Server for past job analysis
* [ ] Multi-region deployment
* [ ] Auto-tuning Spark configs based on job size

## Related Documentation

* [AWS_ORCHESTRATION_DECISION.md](AWS_ORCHESTRATION_DECISION.md) — Why EKS + Spark Operator?
* [../../DOCKER_DIGEST_PINNING.md](../../DOCKER_DIGEST_PINNING.md) — Image pinning best practices
* [../../src/core/transformations/README.md](../../src/core/transformations/README.md) — Platform-agnostic logic
* [Spark Operator Docs](https://github.com/kubeflow/spark-operator/tree/master/docs)
* [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
