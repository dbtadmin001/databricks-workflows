# Production environment for POS Retail on AWS EKS

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Configure backend:
    # terraform init \
    #   -backend-config="bucket=<YOUR_TERRAFORM_STATE_BUCKET>" \
    #   -backend-config="key=pos-retail/prod/terraform.tfstate" \
    #   -backend-config="region=us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "pos-retail"
      Environment = "prod"
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  cluster_name = "pos-retail-prod"
  
  tags = {
    Project     = "pos-retail"
    Environment = "prod"
  }
}

module "vpc" {
  source = "../../modules/vpc"
  
  vpc_name             = "pos-retail-prod-vpc"
  vpc_cidr             = "10.2.0.0/16"
  cluster_name         = local.cluster_name
  public_subnet_count  = 3  # Multi-AZ for prod
  private_subnet_count = 3
  enable_nat_gateway   = true
  nat_gateway_count    = 3  # One per AZ for HA
  
  tags = local.tags
}

module "s3" {
  source = "../../modules/s3"
  
  delta_lake_bucket_name  = "pos-retail-prod-delta-lake"
  spark_logs_bucket_name  = "pos-retail-prod-spark-logs"
  enable_versioning       = true
  enable_lifecycle_policy = true
  spark_logs_retention_days = 90  # Longer retention for prod
  
  tags = local.tags
}

module "eks" {
  source = "../../modules/eks"
  
  cluster_name         = local.cluster_name
  kubernetes_version   = "1.28"
  subnet_ids           = module.vpc.private_subnet_ids
  cluster_role_arn     = module.iam.cluster_role_arn
  node_role_arn        = module.iam.node_role_arn
  
  # Production uses ON_DEMAND instances for reliability
  instance_types       = ["m5.2xlarge"]
  capacity_type        = "ON_DEMAND"
  
  desired_nodes        = 3
  min_nodes            = 2  # Always keep minimum capacity
  max_nodes            = 20
  
  public_access_cidrs  = var.eks_public_access_cidrs
  
  tags = local.tags
}

module "iam" {
  source = "../../modules/iam"
  
  cluster_name      = local.cluster_name
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.cluster_endpoint
  
  s3_bucket_arns = [
    module.s3.delta_lake_bucket_arn,
    module.s3.spark_logs_bucket_arn
  ]
  
  tags = local.tags
}
