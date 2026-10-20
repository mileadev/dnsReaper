terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.16, < 6.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

variable "lambda_reserved_concurrency" {
  description = "Maximum concurrent executions of the scan Lambda. Caps cost and abuse."
  type        = number
  default     = 10
}


resource "aws_dynamodb_table" "results" {
  name         = "dnsreaper-results"
  billing_mode = "PAY_PER_REQUEST"

  attribute {
    name = "guid"
    type = "S"
  }
  hash_key = "guid"

  ttl {
    attribute_name = "expires"
    enabled        = true
  }
}

locals {
  # Validating should work without the secret. A plan fails through the
  # lifecycle precondition below when the key is missing.
  pd_api_key = fileexists("${path.module}/pdkey") ? trimspace(file("${path.module}/pdkey")) : ""

  # Hash every Python source file and the files that affect the Lambda image.
  # This makes a source change rebuild the package instead of reusing a stale zip.
  lambda_source_files = distinct(concat(
    tolist(fileset(path.root, "*.py")),
    [
      for f in fileset(path.root, "**/*.py") : f
      if !startswith(f, "tests/") &&
      !startswith(f, "dev/") &&
      !startswith(f, ".terraform/") &&
      !startswith(f, ".venv/") &&
      !startswith(f, "venv/") &&
      !startswith(f, "build/") &&
      !startswith(f, ".pytest_cache/") &&
      !startswith(f, "__pycache__/")
    ],
    [
      "requirements.txt",
      "lambda-requirements.txt",
      "Dockerfile",
      ".dockerignore",
    ]
  ))
  lambda_source_hash = sha1(join("", [
    for f in local.lambda_source_files : filesha1("${path.root}/${f}")
  ]))
  lambda_zip_path = "${path.root}/build/dnsreaper-${local.lambda_source_hash}.zip"
}

resource "null_resource" "build_venv" {
  triggers = {
    source_hash = local.lambda_source_hash
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -eu
      mkdir -p "${path.root}/build"
      image="dnsreaper-lambda-${local.lambda_source_hash}"
      if docker buildx version >/dev/null 2>&1; then
        docker buildx build --platform linux/amd64 --load -t "$image" "${path.root}" -f "${path.root}/Dockerfile" --target lambda
      else
        docker build -t "$image" "${path.root}" -f "${path.root}/Dockerfile" --target lambda
      fi
      architecture="$(docker image inspect "$image" --format '{{.Architecture}}')"
      if [ "$architecture" != "amd64" ]; then
        echo "Lambda package must be built for linux/amd64, got $architecture" >&2
        exit 1
      fi
      container_id="$(docker create "$image")"
      cleanup() {
        docker rm -fv "$container_id" >/dev/null 2>&1 || true
        docker rmi "$image" >/dev/null 2>&1 || true
      }
      trap cleanup EXIT
      docker cp "$container_id:/packaged_app.zip" "${local.lambda_zip_path}"
    EOT
  }
}

### Logs
resource "aws_cloudwatch_log_group" "logs" {
  name              = "/aws/lambda/dnsReaper-public-lambda"
  retention_in_days = 14
}

resource "aws_lambda_function" "serverless-dnsreaper" {
  depends_on    = [null_resource.build_venv]
  description   = "dnsReaper build ${local.lambda_source_hash}"
  filename      = local.lambda_zip_path
  function_name = "dnsReaper-public-lambda"
  role          = aws_iam_role.iam_for_lambda.arn
  handler       = "lambda.handler"
  runtime       = "python3.11"
  architectures = ["x86_64"]

  timeout                        = 30
  memory_size                    = 256
  reserved_concurrent_executions = var.lambda_reserved_concurrency

  lifecycle {
    precondition {
      condition     = local.pd_api_key != ""
      error_message = "Create pdkey with the ProjectDiscovery API key before planning."
    }
  }

  environment {
    variables = {
      PD_API_KEY        = local.pd_api_key
      DYNAMO_TABLE      = aws_dynamodb_table.results.name
      SCAN_DOMAIN_LIMIT = "2000"
    }
  }
}

output "lambda_function_name" {
  value = aws_lambda_function.serverless-dnsreaper.function_name
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.results.name
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "execution" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["${aws_cloudwatch_log_group.logs.arn}:*"]
  }

  statement {
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem"
    ]
    resources = [aws_dynamodb_table.results.arn]
  }

}

resource "aws_iam_role" "iam_for_lambda" {
  name               = "iam_for_lambda"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  inline_policy {
    name   = "execution_policy"
    policy = data.aws_iam_policy_document.execution.json
  }
}


