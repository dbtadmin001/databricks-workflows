# EKS Cluster for Spark-on-K8s
# This module creates an EKS cluster with autoscaling node groups for running Spark jobs.

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
  }
}

resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = var.cluster_role_arn
  version  = var.kubernetes_version
  
  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.public_access_cidrs
  }
  
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  
  tags = merge(
    var.tags,
    {
      Name = var.cluster_name
    }
  )
}

resource "aws_eks_node_group" "spark_workers" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "spark-workers"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids
  
  scaling_config {
    desired_size = var.desired_nodes
    max_size     = var.max_nodes
    min_size     = var.min_nodes
  }
  
  instance_types = var.instance_types
  capacity_type  = var.capacity_type  # ON_DEMAND or SPOT
  
  tags = merge(
    var.tags,
    {
      Name = "spark-workers"
    }
  )
  
  # Ensure node group updates are graceful
  lifecycle {
    create_before_destroy = true
  }
}

# IRSA (IAM Roles for Service Accounts) OIDC provider
resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.aws_iam_openid_connect_provider_thumbprint.eks.thumbprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
  
  tags = var.tags
}

data "aws_iam_openid_connect_provider_thumbprint" "eks" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}
