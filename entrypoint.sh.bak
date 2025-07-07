
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
fi

# Ensure ansible directories exist with proper permissions
mkdir -p /tmp/ansible-ssh
chmod -R 777 /tmp/ansible-ssh
echo "Ansible SSH directory created with permissions 777"

# Run the specified command
exec "$@"
