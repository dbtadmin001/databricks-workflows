output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = local.cluster_name
}

output "delta_lake_bucket" {
  description = "Delta Lake S3 bucket"
  value       = module.s3.delta_lake_bucket_id
}

output "spark_logs_bucket" {
  description = "Spark logs S3 bucket"
  value       = module.s3.spark_logs_bucket_id
}

output "spark_job_role_arn" {
  description = "IAM role ARN for Spark jobs (IRSA)"
  value       = module.iam.spark_job_role_arn
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --name ${local.cluster_name} --region ${var.aws_region}"
}
