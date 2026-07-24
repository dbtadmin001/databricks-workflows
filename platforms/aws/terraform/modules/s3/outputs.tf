output "delta_lake_bucket_id" {
  description = "Delta Lake S3 bucket ID"
  value       = aws_s3_bucket.delta_lake.id
}

output "delta_lake_bucket_arn" {
  description = "Delta Lake S3 bucket ARN"
  value       = aws_s3_bucket.delta_lake.arn
}

output "spark_logs_bucket_id" {
  description = "Spark logs S3 bucket ID"
  value       = aws_s3_bucket.spark_logs.id
}

output "spark_logs_bucket_arn" {
  description = "Spark logs S3 bucket ARN"
  value       = aws_s3_bucket.spark_logs.arn
}
