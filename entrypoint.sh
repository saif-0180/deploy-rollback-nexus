#!/bin/bash

# Get the current user's home directory
USER_HOME=${HOME:-/home/users/infadm}
CURRENT_USER=$(whoami)

echo "Running as user: $CURRENT_USER with home: $USER_HOME"

# SSH key setup for the current user
if [ -d "/app/ssh-keys" ] && [ "$(ls -A /app/ssh-keys 2>/dev/null)" ]; then
  echo "Setting up SSH keys..."
  mkdir -p "$USER_HOME/.ssh"
  
  # Copy SSH keys
  cp /app/ssh-keys/* "$USER_HOME/.ssh/" 2>/dev/null || echo "Warning: Could not copy some SSH keys"
  
  # Set proper permissions
  chmod 700 "$USER_HOME/.ssh" 2>/dev/null || echo "Warning: Could not set SSH directory permissions"
  chmod 600 "$USER_HOME/.ssh"/* 2>/dev/null || echo "Warning: Could not set SSH key permissions"
  
  echo "SSH keys setup complete"
  
  # Display SSH key fingerprints for debugging
  if [ -f "$USER_HOME/.ssh/id_rsa" ]; then
    echo "SSH key fingerprints:"
    ssh-keygen -l -f "$USER_HOME/.ssh/id_rsa" 2>/dev/null || echo "Could not read SSH key fingerprint"
  fi
else
  echo "No SSH keys found or directory is empty"
fi

# Ensure ansible directories exist with proper permissions
echo "Setting up Ansible SSH control directory..."
mkdir -p /tmp/ansible-ssh
# Only try to set permissions if we can
if [ -w /tmp/ansible-ssh ]; then
  chmod 755 /tmp/ansible-ssh 2>/dev/null || echo "Could not set ansible-ssh permissions"
  echo "Ansible SSH directory created"
else
  echo "Warning: /tmp/ansible-ssh may not be writable"
fi

# Ensure log directory exists with proper permissions
echo "Setting up logs directory..."
mkdir -p /app/logs
touch /app/logs/application.log 2>/dev/null || echo "Warning: Could not create application.log"
echo "Logs directory setup complete"

# Create directories for inventory and output
mkdir -p /app/inventory
echo "Inventory directory created"

# Fix common YAML issues in Ansible templates
fix_yaml_file() {
  local file="$1"
  if [ -f "$file" ]; then
    # Replace problematic YAML syntax
    sed -i 's/when: "True" | bool/when: true/g' "$file"
    sed -i 's/when: "False" | bool/when: false/g' "$file"
    sed -i "s/when: 'status' != 'status'/when: operation != 'status'/g" "$file"
    echo "Fixed YAML syntax in $file"
  fi
}

# Create a fixed version of ansible.cfg
echo "Creating Ansible configuration..."
sudo tee /etc/ansible/ansible.cfg > /dev/null << EOF
[defaults]
host_key_checking = False
timeout = 30
inventory = /app/inventory/inventory.ini
remote_user = infadm
log_path = /app/logs/ansible.log
become = True
become_method = sudo
become_user = infadm
private_key_file = $USER_HOME/.ssh/id_rsa
control_path_dir = /tmp/ansible-ssh
forks = 10
yaml_valid_extensions = .yaml, .yml, .json

[privilege_escalation]
become = True
become_method = sudo
become_user= infadm
become_ask_pass = False

[ssh_connection]
pipelining = True
control_path = /tmp/ansible-ssh/%h-%p-%r
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
EOF
echo "Ansible configuration created at /etc/ansible/ansible.cfg"

# Fix for systemd templates
echo "Creating systemd template..."
mkdir -p /tmp/templates
cat > /tmp/templates/systemd_template.yml << EOF
---
- name: Manage systemd service on VMs
  hosts: all
  gather_facts: no
  become: {{ sudo }}
  become_user: {{ user }}
  tasks:
    - name: Get service {{ service }} status
      systemd:
        name: "{{ service }}"
        state: "{{ operation if operation != 'status' else omit }}"
      register: service_status
      when: operation in ['status', 'start', 'stop', 'restart']
    - name: Display service status
      debug:
        var: service_status
EOF
echo "Systemd template created"

# Hook for patching ansible playbooks before execution
# Set up a directory watcher to fix YAML issues in ansible playbooks
echo "Starting YAML fix watcher in background..."
while true; do
  for file in /tmp/shell_command_*.yml /tmp/systemd_*.yml; do
    if [[ -f "$file" && -s "$file" && ! -f "${file}.fixed" ]]; then
      fix_yaml_file "$file"
      touch "${file}.fixed"
      echo "Fixed YAML in $file"
    fi
  done
  sleep 1
done &

echo "Entrypoint setup complete. Starting application..."

# Run the specified command
exec "$@"
