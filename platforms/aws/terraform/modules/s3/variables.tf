variable "delta_lake_bucket_name" {
  description = "Name of the S3 bucket for Delta Lake storage"
  type        = string
}

variable "spark_logs_bucket_name" {
  description = "Name of the S3 bucket for Spark event logs"
  type        = string
}

variable "enable_versioning" {
  description = "Enable S3 versioning for Delta Lake bucket"
  type        = bool
  default     = true
}

variable "enable_lifecycle_policy" {
  description = "Enable lifecycle policy for cost optimization"
  type        = bool
  default     = true
}

variable "spark_logs_retention_days" {
  description = "Number of days to retain Spark event logs"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
