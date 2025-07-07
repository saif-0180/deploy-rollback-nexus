
# Fix Deployment Orchestrator

A web-based tool for managing and deploying fixes across multiple virtual machines. This tool helps automate file deployments, SQL updates, and systemd service management with a user-friendly interface.

## Features

- **File Operations**: Copy, move, and backup files across multiple VMs
- **SQL Operations**: Execute SQL files on databases
- **Systemctl Operations**: Manage systemd services (start, stop, restart, status)
- **Deployment History**: Track all deployment operations with logs
- **Real-time Logging**: View deployment progress in real-time

## Architecture

- **Frontend**: React with Tailwind CSS
- **Backend**: Flask Python API
- **Orchestration**: Ansible for automated deployment tasks
- **Container**: Docker & Kubernetes ready

## Prerequisites

- Node.js 16+ and npm for frontend development
- Python 3.9+ for backend development
- Ansible for deployment orchestration
- Docker and Kubernetes for containerized deployment

## Directory Structure

```
fix-files/
├── AllFts/
│   ├── ft-1977/
│   │   └── gimdg_classes.jar
│   ├── ft-1978/
│   │   └── config.sql
│   └── ft-1979/
│       └── ADJ1_IMDG_refresh.sh
```

## Local Development

### Frontend

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

### Backend

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Start Flask server
python backend/app.py
```

## Deployment with Docker

```bash
# Build Docker image
docker build -t fix-deployment-orchestrator .

# Run container
docker run -p 5000:5000 -v /path/to/fixfiles:/app/fixfiles fix-deployment-orchestrator
```

## Kubernetes Deployment

See the [Kubernetes README](kubernetes/README.md) for detailed instructions.

## Configuration

### Inventory Setup

The application uses an inventory file to manage VMs, users, and services. You can configure this through the UI or by editing the inventory.json file:

```json
{
  "vms": [
    {"name": "batch1", "type": "batch", "ip": "192.168.1.10"},
    {"name": "batch2", "type": "batch", "ip": "192.168.1.11"},
    {"name": "imdg1", "type": "imdg", "ip": "192.168.1.20"}
  ],
  "users": ["infadm", "abpwrk1"],
  "db_users": ["postgres", "dbadmin"],
  "systemd_services": ["hazelcast", "kafka", "zookeeper"]
}
```

## Best Practices

1. **Security Considerations**:
   - Use SSH keys instead of passwords
   - Implement role-based access control
   - Encrypt sensitive data (passwords, etc.)

2. **Backup Strategy**:
   - Always backup files before deployment
   - Keep a history of SQL operations
   - Create snapshots of critical VMs before significant changes

3. **Testing**:
   - Test deployments in a staging environment first
   - Create validation steps for critical deployments
   - Set up automated tests for deployment processes

4. **Monitoring**:
   - Monitor service health post-deployment
   - Set up alerts for failed deployments
   - Track deployment metrics over time

## Future Enhancements

1. User authentication and multi-user support
2. Role-based access control
3. Scheduled deployments
4. Automated testing integration
5. Enhanced monitoring and alerting
6. Rollback capabilities for failed deployments
7. Custom deployment templates

## License

This project is licensed under the MIT License - see the LICENSE file for details.
