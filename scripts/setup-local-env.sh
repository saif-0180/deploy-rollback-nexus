
#!/bin/bash
# Script to set up local environment for testing

# Check if running as root
#if [ "$(id -u)" -ne 0 ]; then
#  echo "Please run as root or with sudo"
#  exit 1
#fi

# Set variables
CONTAINER_NAME="fix-deployment-orchestrator2"
SSH_KEY_DIR="/home/infadm/ssh-keys"

# Create SSH key directory
mkdir -p "$SSH_KEY_DIR"
sudo chmod 700 "$SSH_KEY_DIR"

# Generate SSH keys if they don't exist
if [ ! -f "$SSH_KEY_DIR/id_rsa" ]; then
  echo "Generating SSH keys..."
  sudo ssh-keygen -t rsa -b 4096 -f "$SSH_KEY_DIR/id_rsa" -N ""
  echo "SSH keys generated"
else
  echo "SSH keys already exist"
fi

# Create SSH config file
cat > "$SSH_KEY_DIR/config" <<EOF
Host batch1 airflow imdg1 
  User infadm
  IdentityFile ~/.ssh/id_rsa
  StrictHostKeyChecking no
EOF

# Set proper permissions
sudo chmod 600 "$SSH_KEY_DIR/id_rsa"
sudo chmod 644 "$SSH_KEY_DIR/id_rsa.pub"
sudo chmod 644 "$SSH_KEY_DIR/config"

# Create ansible.cfg
mkdir -p "/home/infadm/ansible"
cat > "/home/infadm/ansible/ansible.cfg" <<EOF
[defaults]
host_key_checking = False
timeout = 30
inventory = /home/infadm/fixflow-deploy-orchestrator/inventory/inventory.json
remote_user = infadm
log_path = /home/infadm/logs/ansible.log
become = True
become_method = sudo
become_user = infadm

[privilege_escalation]
become = True
become_method = sudo
become_user = infadm

[ssh_connection]
pipelining = True
control_path = /home/infadm/ansible-ssh-%%h-%%p-%%r
EOF

# Create logs directory
mkdir -p /app/logs
sudo chmod 755 /app/logs

echo "Local environment setup complete."
echo "To use this with Docker:"
echo "docker run -d -p 5000:5000 \\"
echo "  -v $SSH_KEY_DIR:/root/.ssh \\"
echo "  -v /etc/ansible:/etc/ansible \\"
echo "  -v /app/logs:/app/logs \\"
echo "  -v /home/infadm/fixfiles:/app/fixfiles  \\"
echo "  -v /home/infadm/fixflow-deploy-orchestrator/inventory:/app/inventory \\"
echo "  --name $CONTAINER_NAME \\"
echo "  $CONTAINER_NAME:latest"

echo ""
echo "Make sure to copy your SSH public key to the target hosts:"
echo "For local testing on the same machine (batch1):"
echo "mkdir -p ~/.ssh"
echo "cat $SSH_KEY_DIR/id_rsa.pub >> ~/.ssh/authorized_keys"
echo "chmod 600 ~/.ssh/authorized_keys"
