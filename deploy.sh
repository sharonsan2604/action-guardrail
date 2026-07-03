#!/bin/bash

# ==============================================================================
# SentinelAI (Action Guardrail) - Automated AWS EC2 Deployment Script
# Preparation for Aivar Innovations - CIT AI Engineers Task
# ==============================================================================

# Exit immediately if any command fails
set -e

# Configuration
EC2_IP="YOUR_EC2_PUBLIC_IP"
KEY_PATH="guardrail-key.pem"
PROJECT_DIR="action-guardrail"

echo "======================================================================"
echo "🚀 STARTING SENTINELAI DEPLOYMENT PREPARATION"
echo "======================================================================"
echo "This script prepares and packages the application for deployment."
echo "Ensure you have launch permission for your t2.micro EC2 Instance."
echo "======================================================================"

# Step 1: Check SSH Key
if [ ! -f "$KEY_PATH" ]; then
    echo "⚠️ Warning: SSH Key '$KEY_PATH' not found in current directory."
    echo "Please download it from AWS Console and place it here before running."
fi

# Step 2: Print connection instructions
echo ""
echo "Step A: Copy files to EC2 Instance..."
echo "Command to run manually:"
echo "----------------------------------------------------------------------"
echo "scp -i $KEY_PATH -r ../$PROJECT_DIR ubuntu@$EC2_IP:~/"
echo "----------------------------------------------------------------------"

echo ""
echo "Step B: Connect via SSH and run initialization..."
echo "Command to run manually to log in:"
echo "----------------------------------------------------------------------"
echo "ssh -i $KEY_PATH ubuntu@$EC2_IP"
echo "----------------------------------------------------------------------"

# Script content to execute on the remote machine
echo ""
echo "Step C: Script execution payload on EC2 Server:"
echo "----------------------------------------------------------------------"
cat << 'EOF'
#!/bin/bash
echo "--- Updating system packages ---"
sudo apt-get update -y

echo "--- Installing Git, Docker & Docker Compose ---"
sudo apt-get install -y docker.io docker-compose git

echo "--- Starting Docker service ---"
sudo systemctl start docker
sudo systemctl enable docker

echo "--- Adding 'ubuntu' user to docker group (requires logout/login) ---"
sudo usermod -aG docker ubuntu

echo "--- Navigating to project directory ---"
cd ~/action-guardrail

echo "--- Building and orchestrating containers ---"
# Make sure .env is created and configured correctly first
if [ ! -f ".env" ]; then
    echo "⚠️ .env file not found. Creating a template .env. Please configure GEMINI_API_KEY!"
    cp .env.example .env
fi

sudo docker-compose down
sudo docker-compose up -d --build

echo "--- Checking service health status ---"
sleep 5
curl -f http://localhost:8000/health || echo "❌ Healthcheck failed. Inspect logs with: docker-compose logs"

echo "🎉 Deployment Process Completed Successfully!"
echo "Backend endpoint documentation is live at: http://<EC2_IP>:8000/docs"
echo "React Web Dashboard is live at: http://<EC2_IP>:8501"
EOF
echo "----------------------------------------------------------------------"
echo ""
echo "======================================================================"
echo "SentinelAI Deployment Script Completed."
echo "======================================================================"
