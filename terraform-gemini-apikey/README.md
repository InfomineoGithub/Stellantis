# terraform-gemini-apikey

Terraform module to provision a Gemini API Key for RagFlow on GCP.

## What it does
- Enables `apikeys.googleapis.com` in the GCP project
- Enables `generativelanguage.googleapis.com` (Gemini API)
- Creates a restricted API key scoped to Gemini only

## Prerequisites
- Terraform >= 1.0
- A GCP Service Account JSON key with the following roles:
  - `roles/serviceusage.serviceUsageAdmin`
  - `roles/apikeys.admin`

## Usage

1. Copy your service account JSON key to your machine:
```bash
cp /path/to/your-key.json ~/stellantis-key.json
chmod 600 ~/stellantis-key.json
```

2. Set the environment variable:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/stellantis-key.json
```

3. Deploy:
```bash
terraform init
terraform plan
terraform apply
```

4. Retrieve the API key:
```bash
terraform output -raw api_key_string
```

## Important
- Never commit your JSON key or `terraform.tfstate` to Git
- The `.gitignore` in this folder protects you from accidental commits
