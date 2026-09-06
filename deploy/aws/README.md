# AWS Deployment Guide: Document Intelligence Platform Backend

This directory contains production deployment configurations for running the FastAPI backend on AWS.

---

## Architecture Overview

The platform uses a hybrid RAG architecture:
- **Local CPU Inference**: Sentence-Transformers (`nomic-embed-text-v1.5`), CrossEncoder (`bge-reranker-base`), LibreOffice conversion.
- **Local Persistent Storage**: SQLite registry (`registry.db`), FAISS vector indexes (`storage/vector_stores`), raw uploads (`storage/uploads`).
- **Cloud LLM Synthesis**: Outbound HTTPS requests to Google Gemini / OpenAI API.

Because FAISS vector indexes and SQLite are filesystem-backed, the hosting environment **must maintain a persistent volume** across restarts.

---

## Option 1: EC2 / Lightsail Deployment (Recommended)

**Estimated Cost**: ~\$15 – \$25 / month (e.g., `t4g.medium` or `t3.medium` with 40 GB gp3 storage).

### Step 1: Launch an AWS EC2 Instance
1. Go to AWS Console > **EC2** > **Launch Instance**.
2. **Name**: `pdf-rag-backend-prod`.
3. **AMI**: Ubuntu Server 24.04 LTS (or 22.04 LTS).
4. **Architecture**:
   - `arm64` (Graviton) -> Select instance type **`t4g.medium`** (2 vCPU, 4 GB RAM, best price/performance)
   - OR `x86_64` -> Select instance type **`t3.medium`** (2 vCPU, 4 GB RAM)
5. **Key Pair**: Select or generate your `.pem` SSH key.
6. **Storage**: Configure **40 GB gp3** SSD (needed for Docker layers, model caches, and uploaded documents).
7. **Network Settings / Security Group**:
   - Allow **SSH (22)** from your IP address.
   - Allow **HTTP (80)** from anywhere (`0.0.0.0/0`).
   - Allow **HTTPS (443)** from anywhere (`0.0.0.0/0`).
8. Click **Launch Instance**.
9. *(Recommended)*: Allocate and associate an **Elastic IP** so the server's public IP remains static.

---

### Step 2: Provision the Server
SSH into your newly created EC2 instance:
```bash
ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
```

Clone the repository:
```bash
git clone https://github.com/<YOUR_USER>/pdf-rag-summarizer.git
cd pdf-rag-summarizer
```

Run the automated provisioning script:
```bash
chmod +x deploy/aws/setup-instance.sh
./deploy/aws/setup-instance.sh
```
*This script installs Docker, Docker Compose, sets up a 4GB swap space to guarantee model stability against OOM errors, enables the UFW firewall, and prepares the storage directory.*

Apply docker group permissions without logging out:
```bash
newgrp docker
```

---

### Step 3: Configure Environment Variables
Copy the template and edit with your credentials:
```bash
cp deploy/aws/.env.production.example .env
nano .env
```
Fill in:
- `GEMINI_API_KEY`: Your Gemini API key.
- `DOMAIN_NAME`: Your domain (e.g., `api.example.com`) or leave `:80` if using raw IP.

---

### Step 4: Build and Start Services
Launch both the backend and Caddy reverse proxy:
```bash
docker compose -f deploy/aws/docker-compose.prod.yml up -d --build
```

Monitor the initial build and model pre-caching:
```bash
docker compose -f deploy/aws/docker-compose.prod.yml logs -f
```

---

### Step 5: Verify Deployment
Verify the health check endpoint:
```bash
curl -i http://localhost/api/health
# or externally:
curl -i https://<YOUR_DOMAIN_OR_IP>/api/health
```
Expected response:
```json
{"status":"ok","app":"Document Intelligence Platform API","version":"1.0.0"}
```

---

## Option 2: AWS ECS Fargate + Amazon EFS (Serverless Container)

**Estimated Cost**: ~\$45 – \$70 / month (ALB + Fargate 1 vCPU/4GB + EFS).

### Step 1: Create Amazon ECR Repository
```bash
aws ecr create-repository --repository-name pdf-rag-backend --region us-east-1
```

Build and push your container image:
```bash
docker build -f backend/Dockerfile -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/pdf-rag-backend:latest backend/
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/pdf-rag-backend:latest
```

### Step 2: Create Amazon EFS File System
1. Create an EFS File System in the same VPC as your ECS Cluster.
2. Create an **Access Point**:
   - Path: `/storage`
   - POSIX User ID: `1000`, Group ID: `1000`
3. Configure Security Group on EFS Mount Targets to allow inbound port 2049 from the ECS Task Security Group.

### Step 3: Register Task Definition & Service
1. Store `GEMINI_API_KEY` in AWS SSM Parameter Store:
   ```bash
   aws ssm put-parameter --name "/pdf-rag/GEMINI_API_KEY" --type "SecureString" --value "AIzaSy..."
   ```
2. Update placeholders in `deploy/aws/ecs-task-definition.json`:
   - Replace `<AWS_ACCOUNT_ID>`, `<AWS_REGION>`, `<EFS_FILE_SYSTEM_ID>`, and `<EFS_ACCESS_POINT_ID>`.
3. Register the task:
   ```bash
   aws ecs register-task-definition --cli-input-json file://deploy/aws/ecs-task-definition.json
   ```
4. Create an ECS Service with an **Application Load Balancer (ALB)** targeting container port `8000` on health check `/api/health`.

---

## Maintenance & Operations

### Viewing Logs
```bash
docker compose -f deploy/aws/docker-compose.prod.yml logs -f backend
```

### Updating to Latest Version
```bash
git pull origin main
docker compose -f deploy/aws/docker-compose.prod.yml up -d --build
```

### Backing Up Vector Indexes and Registry
To back up the persistent vector stores and database to AWS S3:
```bash
aws s3 sync backend/storage s3://<YOUR_BACKUP_BUCKET>/storage-backup/ --delete
```
You can set this up as a daily cron job:
```bash
0 2 * * * aws s3 sync /home/ubuntu/pdf-rag-summarizer/backend/storage s3://<YOUR_BACKUP_BUCKET>/storage-backup/
```
