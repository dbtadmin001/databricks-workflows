output "cluster_role_arn" {
  description = "EKS cluster IAM role ARN"
  value       = aws_iam_role.cluster.arn
}

output "node_role_arn" {
  description = "EKS node IAM role ARN"
  value       = aws_iam_role.node.arn
}

output "spark_job_role_arn" {
  description = "Spark job IAM role ARN (IRSA)"
  value       = aws_iam_role.spark_job.arn
}

output "spark_job_role_name" {
  description = "Spark job IAM role name"
  value       = aws_iam_role.spark_job.name
}
