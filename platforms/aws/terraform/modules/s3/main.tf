# S3 buckets for Delta Lake storage and Spark event logs

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Delta Lake storage bucket
resource "aws_s3_bucket" "delta_lake" {
  bucket = var.delta_lake_bucket_name
  
  tags = merge(
    var.tags,
    {
      Name    = var.delta_lake_bucket_name
      Purpose = "Delta Lake storage"
    }
  )
}

resource "aws_s3_bucket_versioning" "delta_lake" {
  bucket = aws_s3_bucket.delta_lake.id
  
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "delta_lake" {
  bucket = aws_s3_bucket.delta_lake.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "delta_lake" {
  bucket = aws_s3_bucket.delta_lake.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle policy for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "delta_lake" {
  count  = var.enable_lifecycle_policy ? 1 : 0
  bucket = aws_s3_bucket.delta_lake.id
  
  rule {
    id     = "transition-to-ia"
    status = "Enabled"
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
  }
  
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# Spark event logs bucket
resource "aws_s3_bucket" "spark_logs" {
  bucket = var.spark_logs_bucket_name
  
  tags = merge(
    var.tags,
    {
      Name    = var.spark_logs_bucket_name
      Purpose = "Spark event logs"
    }
  )
}

resource "aws_s3_bucket_server_side_encryption_configuration" "spark_logs" {
  bucket = aws_s3_bucket.spark_logs.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "spark_logs" {
  bucket = aws_s3_bucket.spark_logs.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle policy for Spark logs (expire after 30 days)
resource "aws_s3_bucket_lifecycle_configuration" "spark_logs" {
  bucket = aws_s3_bucket.spark_logs.id
  
  rule {
    id     = "expire-logs"
    status = "Enabled"
    
    expiration {
      days = var.spark_logs_retention_days
    }
  }
}
