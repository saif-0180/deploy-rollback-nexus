#!/bin/bash
# SSH key setup
if [ -d "/app/ssh-keys" ]; then
  echo "Setting up SSH keys..."
  mkdir -p /root/.ssh
  cp /app/ssh-keys/* /root/.ssh/
  chmod 700 /root/.ssh
  chmod 600 /root/.ssh/*
  chown -R root:root /root/.ssh
  echo "SSH keys setup complete"
  
  # Display SSH key fingerprints for debugging
  if [ -f "/root/.ssh/id_rsa" ]; then
    echo "SSH key fingerprints:"
    ssh-keygen -l -f /root/.ssh/id_rsa
  fi
fi

# Ensure ansible directories exist with proper permissions
mkdir -p /tmp/ansible-ssh
chmod -R 777 /tmp/ansible-ssh
echo "Ansible SSH directory created with permissions 777"

# Ensure log directory exists with proper permissions
mkdir -p /app/logs
touch /app/logs/application.log
chmod -R 777 /app/logs
echo "Logs directory created with permissions 777"

# Create directories for inventory and output
mkdir -p /app/inventory
chmod -R 777 /app/inventory

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
cat > /etc/ansible/ansible.cfg << EOF
[defaults]
host_key_checking = False
timeout = 30
inventory = /app/inventory/inventory.ini
remote_user = infadm
log_path = /app/logs/ansible.log
become = True
become_method = sudo
become_user = infadm
private_key_file = /root/.ssh/id_rsa
control_path_dir = /tmp/ansible-ssh
forks = 10
yaml_valid_extensions = .yaml, .yml, .json

[privilege_escalation]
become = True
become_method = sudo
become_user = infadm

[ssh_connection]
pipelining = True
control_path = /tmp/ansible-ssh/%h-%p-%r
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
EOF

echo "Ansible configuration created at /etc/ansible/ansible.cfg"

# Fix for systemd templates
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

# Run the specified command
exec "$@"
