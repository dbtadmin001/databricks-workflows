# AWS Orchestration Decision — Spark on Kubernetes

## Context

The `platforms/aws/` adapter needs to run the same PySpark transformations (`src/core/transformations/`) that run on Databricks. The transformations use standard PySpark APIs and produce Delta Lake tables.

## Requirements

1. **Platform parity** — Must run identical PySpark code without modification
2. **Cost-effective** — Optimize for intermittent/batch workloads (not 24/7)
3. **Open source** — Prefer vendor-agnostic solutions for portability
4. **Kubernetes-native** — Aligns with modern orchestration practices
5. **Reproducible** — Digest-pinned images, immutable infrastructure
6. **Manageable** — Clear separation of concerns (compute vs orchestration)

## Options Evaluated

### Option 1: EKS + Spark Operator (CHOSEN)

**Architecture**:
* Kubernetes cluster on AWS EKS
* [Spark-on-K8s Operator](https://github.com/kubeflow/spark-operator) manages SparkApplication CRDs
* Custom Docker image with PySpark + src/core code
* Store Delta tables in S3

**Pros**:
* ✅ **Fully open source** — No vendor lock-in beyond EKS itself
* ✅ **Standard Kubernetes** — Same patterns as any K8s workload
* ✅ **Cost control** — EKS nodes can autoscale to zero between jobs
* ✅ **Flexibility** — Control every aspect of Spark config and dependencies
* ✅ **Portability** — Same Spark Operator can run on GKE, AKS, on-prem K8s
* ✅ **Declarative** — SparkApplication manifests in Git, IaC-friendly
* ✅ **Observability** — Standard K8s tooling (kubectl, k9s, Prometheus, Grafana)

**Cons**:
* ⚠️ **More setup** — Need to provision EKS, install Spark Operator
* ⚠️ **Learning curve** — Team needs K8s knowledge
* ⚠️ **Self-managed** — Responsible for K8s upgrades, Spark Operator updates

**Why it fits our needs**:
* Aligns with **reproducibility** goal (digest-pinned images)
* Open source aligns with **portability** principle (no AWS lock-in)
* K8s is **industry standard** for container orchestration
* EKS autoscaling fits **batch workload** cost profile

---

### Option 2: EMR on EKS (REJECTED)

**Architecture**:
* AWS-managed Spark runtime on EKS
* Submit jobs via `emr-containers` API or StartJobRun
* EMR handles Spark image, dependencies, and tuning

**Pros**:
* ✅ **Less setup** — EMR manages Spark image and operator
* ✅ **AWS-optimized** — Tuned for S3, Glue Catalog, IAM
* ✅ **Managed runtime** — Automatic Spark version updates

**Cons**:
* ❌ **Vendor lock-in** — EMR-specific APIs, not portable to other clouds
* ❌ **Less control** — Can't fully customize Spark image or dependencies
* ❌ **Opaque** — Harder to debug EMR runtime vs custom image
* ❌ **Cost** — EMR adds ~20% surcharge on top of EKS compute

**Why we're rejecting it**:
* Violates **open source** and **portability** principles
* We already have Databricks for managed Spark; AWS is the "self-hosted" path
* EMR lock-in defeats the purpose of having platform-agnostic src/core logic

---

### Option 3: EMR Serverless (REJECTED)

**Architecture**:
* Fully serverless Spark (no clusters to manage)
* Submit jobs via EMR Serverless API
* Pay only for job execution time

**Pros**:
* ✅ **Zero cluster management** — No EKS, no K8s
* ✅ **True serverless** — Pay per second of job execution
* ✅ **Fast startup** — Pre-warmed Spark environments

**Cons**:
* ❌ **Highest vendor lock-in** — Completely AWS-proprietary
* ❌ **No Kubernetes** — Doesn't help us learn/standardize on K8s
* ❌ **Less control** — Can't customize runtime or dependencies deeply
* ❌ **Not K8s-native** — Separate orchestration paradigm

**Why we're rejecting it**:
* This project's goal includes **demonstrating Kubernetes orchestration**
* If we just wanted serverless Spark, we'd stay on Databricks
* Violates portability (can't run same setup on-prem or other clouds)

---

### Option 4: AWS Glue (REJECTED)

**Architecture**:
* Managed Spark service (not on K8s)
* Submit jobs via Glue API
* Glue Catalog for metadata

**Pros**:
* ✅ **Fully managed** — No infrastructure to maintain
* ✅ **Serverless pricing** — Pay per DPU-hour

**Cons**:
* ❌ **Glue-specific APIs** — Can't use standard PySpark decorators like `@dp.table`
* ❌ **Not Kubernetes** — Completely different paradigm from Databricks/on-prem
* ❌ **Limited flexibility** — Can't control Spark version or dependencies easily

**Why we're rejecting it**:
* Requires modifying `src/core/` logic to use Glue APIs (breaks platform parity)
* No K8s learning/standardization
* Too AWS-specific

---

## Decision: EKS + Spark Operator

**Rationale**:

1. **Aligns with project goals**:
   * Open source and portable (can run on any K8s)
   * Platform-agnostic src/core logic unchanged
   * K8s-native (standard orchestration patterns)

2. **Cost-effective for batch**:
   * Autoscale EKS node groups to zero between jobs
   * No EMR surcharge
   * Pay only for EC2 instances during job execution

3. **Reproducible and auditable**:
   * Custom Docker image with digest pinning
   * SparkApplication manifests in Git
   * Terraform IaC for cluster

4. **Industry standard**:
   * K8s is the de facto container orchestration platform
   * Spark Operator is mature (Kubeflow project, 3k+ stars)
   * Same patterns work on GKE, AKS, on-prem

5. **Learning investment**:
   * K8s knowledge is transferable across projects and clouds
   * EMR/Glue knowledge is AWS-specific

---

## Implementation Plan

### Phase 1: Infrastructure (Terraform)
* EKS cluster (1.28+)
* Managed node groups with autoscaling
* VPC, subnets, security groups
* IAM roles (IRSA for S3 access)
* S3 bucket for Delta Lake storage

### Phase 2: Spark Operator
* Install Spark Operator via Helm
* Configure RBAC and service accounts
* Set up webhook and CRD

### Phase 3: Job Containerization
* Dockerfile for PySpark jobs
  * Base: apache/spark:3.5.0-python3
  * Add: src/core transformations
  * Pin by digest
* Push to Amazon ECR
* Tag: {git_sha}, latest

### Phase 4: SparkApplication Manifests
* bronze_ingestion.yaml
* silver_enrichment.yaml
* gold_aggregations.yaml
* Use same src/core code as Databricks

### Phase 5: CI/CD
* GitHub Actions workflow
* Build and push Docker image
* Apply K8s manifests to EKS
* Run smoke tests

---

## Alternatives for Future Consideration

**If team wants less K8s operational overhead later**:
* Consider **EMR on EKS** after we've proven the pattern works
* Still K8s-based, so migration is straightforward
* Trade some portability for less operational burden

**If workload becomes 24/7 streaming**:
* EKS + Spark Operator still works (long-running streaming queries)
* May want dedicated node pools vs autoscaling
* Consider Databricks for production streaming (better ops)

---

## References

* [Spark-on-K8s Operator](https://github.com/kubeflow/spark-operator)
* [Running Spark on Kubernetes](https://spark.apache.org/docs/latest/running-on-kubernetes.html)
* [EKS Best Practices — Data on EKS](https://awslabs.github.io/data-on-eks/)
* [AWS EKS Pricing](https://aws.amazon.com/eks/pricing/)
* [EMR on EKS vs EKS + Spark Operator Comparison](https://stackoverflow.com/questions/66464516/what-is-the-difference-between-amazon-eks-and-amazon-emr-on-eks)
