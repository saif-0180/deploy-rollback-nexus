
import os
import json
import uuid
import base64
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from functools import wraps

# Create a blueprint for deploy template routes
deploy_template_bp = Blueprint('deploy_template', __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple auth check - in production, implement proper JWT validation
        return f(*args, **kwargs)
    return decorated_function

def load_inventory():
    """Load inventory data from JSON file"""
    try:
        with open('/app/inventory/inventory.json', 'r') as f:
            inventory = json.load(f)
        logger.debug(f"Loaded inventory: {inventory}")
        return inventory
    except Exception as e:
        logger.error(f"Error loading inventory: {e}")
        return {"vms": [], "users": [], "systemd_services": [], "playbooks": [], "helm_upgrades": []}

def load_db_inventory():
    """Load database inventory from JSON file"""
    try:
        with open('/app/inventory/db_inventory.json', 'r') as f:
            db_inventory = json.load(f)
        logger.debug(f"Loaded DB inventory: {db_inventory}")
        return db_inventory
    except Exception as e:
        logger.error(f"Error loading DB inventory: {e}")
        return {"db_connections": [], "db_users": []}

def get_vm_ip(vm_name, inventory):
    """Get VM IP address from inventory"""
    for vm in inventory.get('vms', []):
        if vm['name'] == vm_name:
            return vm['ip']
    return None

def get_db_connection_info(db_connection, db_inventory):
    """Get database connection info from inventory"""
    for db in db_inventory.get('db_connections', []):
        if db['db_connection'] == db_connection:
            return db
    return None

def get_playbook_info(playbook_name, inventory):
    """Get playbook information from inventory"""
    for playbook in inventory.get('playbooks', []):
        if playbook['name'] == playbook_name:
            return playbook
    return None

def get_helm_command(deployment_type, inventory):
    """Get helm upgrade command from inventory"""
    for helm in inventory.get('helm_upgrades', []):
        if helm['pod_name'] == deployment_type:
            return helm['command']
    return None

# Template routes that will be added to app.py
@deploy_template_bp.route('/api/deploy/templates', methods=['GET'])
@require_auth
def list_templates():
    """List available deployment templates"""
    try:
        template_dir = '/app/deployment_templates'
        if not os.path.exists(template_dir):
            logger.warning(f"Template directory {template_dir} does not exist")
            return jsonify({"templates": []})
        
        templates = []
        for file in os.listdir(template_dir):
            if file.endswith('_template.json'):
                templates.append(file)
        
        logger.debug(f"Found templates: {templates}")
        return jsonify({"templates": templates})
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/deploy/templates/<template_name>', methods=['GET'])
@require_auth
def load_template(template_name):
    """Load a specific deployment template"""
    try:
        template_path = f'/app/deployment_templates/{template_name}'
        if not os.path.exists(template_path):
            return jsonify({"error": "Template not found"}), 404
        
        with open(template_path, 'r') as f:
            template = json.load(f)
        
        logger.debug(f"Loaded template {template_name}: {template}")
        return jsonify({"template": template})
    except Exception as e:
        logger.error(f"Error loading template {template_name}: {e}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/deploy/templates/execute', methods=['POST'])
@require_auth
def execute_template():
    """Execute a deployment template"""
    try:
        data = request.get_json()
        template_name = data.get('template_name')
        
        if not template_name:
            return jsonify({"error": "Template name is required"}), 400
        
        # Load template
        template_path = f'/app/deployment_templates/{template_name}'
        if not os.path.exists(template_path):
            return jsonify({"error": "Template not found"}), 404
        
        with open(template_path, 'r') as f:
            template = json.load(f)
        
        # Generate deployment ID
        deployment_id = str(uuid.uuid4())
        
        # Get user info (you'll need to implement this based on your auth system)
        logged_in_user = "system"  # Replace with actual user from session/token
        
        # Initialize deployments dict if it doesn't exist
        if not hasattr(current_app, 'deployments'):
            current_app.deployments = {}
        
        # Create deployment entry
        deployment_entry = {
            'id': deployment_id,
            'type': 'template_deployment',
            'status': 'running',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'template_name': template_name,
            'ft_number': template.get('metadata', {}).get('ft_number', 'unknown'),
            'total_steps': template.get('metadata', {}).get('total_steps', 0),
            'current_step': 0,
            'logs': [f"Starting template deployment: {template_name}"],
            'logged_in_user': logged_in_user
        }
        
        # Store deployment
        current_app.deployments[deployment_id] = deployment_entry
        
        # Start template execution in background
        # Note: In production, you'd want to use a proper task queue like Celery
        import threading
        thread = threading.Thread(target=execute_template_steps, args=(deployment_id, template))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started template deployment {deployment_id} for template {template_name}")
        return jsonify({"deployment_id": deployment_id, "message": "Template deployment started"})
        
    except Exception as e:
        logger.error(f"Error executing template: {e}")
        return jsonify({"error": str(e)}), 500

def execute_template_steps(deployment_id, template):
    """Execute template steps in order"""
    try:
        # Initialize deployments dict if it doesn't exist
        if not hasattr(current_app, 'deployments'):
            current_app.deployments = {}
            
        deployment = current_app.deployments.get(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return
        
        # Load inventories
        inventory = load_inventory()
        db_inventory = load_db_inventory()
        
        # Sort steps by order
        steps = sorted(template.get('steps', []), key=lambda x: x.get('order', 0))
        total_steps = len(steps)
        
        for i, step in enumerate(steps, 1):
            try:
                deployment['current_step'] = i
                deployment['logs'].append(f"Step {i}/{total_steps}: {step.get('description', 'Unknown step')}")
                
                success = execute_single_step(step, inventory, db_inventory, deployment_id)
                
                if not success:
                    deployment['status'] = 'failed'
                    deployment['logs'].append(f"Step {i} failed. Stopping deployment.")
                    break
                else:
                    deployment['logs'].append(f"Step {i} completed successfully.")
                    
            except Exception as e:
                logger.error(f"Error in step {i}: {e}")
                deployment['status'] = 'failed'
                deployment['logs'].append(f"Step {i} failed with error: {str(e)}")
                break
        
        # Mark as completed if all steps succeeded
        if deployment['status'] == 'running':
            deployment['status'] = 'success'
            deployment['logs'].append("Template deployment completed successfully!")
        
        logger.info(f"Template deployment {deployment_id} finished with status: {deployment['status']}")
        
    except Exception as e:
        logger.error(f"Error executing template steps for {deployment_id}: {e}")
        if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
            current_app.deployments[deployment_id]['status'] = 'failed'
            current_app.deployments[deployment_id]['logs'].append(f"Template execution failed: {str(e)}")

def execute_single_step(step, inventory, db_inventory, deployment_id):
    """Execute a single template step"""
    step_type = step.get('type')
    
    # Initialize deployments dict if it doesn't exist
    if not hasattr(current_app, 'deployments'):
        current_app.deployments = {}
        
    deployment = current_app.deployments.get(deployment_id)
    
    if not deployment:
        logger.error(f"Deployment {deployment_id} not found")
        return False
    
    try:
        if step_type == 'file_deployment':
            return execute_file_deployment_step(step, inventory, deployment)
        elif step_type == 'sql_deployment':
            return execute_sql_deployment_step(step, db_inventory, deployment)
        elif step_type == 'service_restart':
            return execute_service_restart_step(step, inventory, deployment)
        elif step_type == 'ansible_playbook':
            return execute_ansible_playbook_step(step, inventory, deployment)
        elif step_type == 'helm_upgrade':
            return execute_helm_upgrade_step(step, inventory, deployment)
        else:
            deployment['logs'].append(f"Unknown step type: {step_type}")
            return False
            
    except Exception as e:
        logger.error(f"Error executing step {step_type}: {e}")
        deployment['logs'].append(f"Error executing {step_type}: {str(e)}")
        return False

# ... keep existing code (all the execute_*_step functions remain the same)

def execute_file_deployment_step(step, inventory, deployment):
    """Execute file deployment step using ansible"""
    try:
        files = step.get('files', [])
        target_vms = step.get('targetVMs', [])
        target_user = step.get('targetUser', 'root')
        target_path = step.get('targetPath', '/tmp')
        
        if not files or not target_vms:
            deployment['logs'].append("Missing files or target VMs for file deployment")
            return False
        
        # Get VM IPs
        vm_ips = []
        for vm_name in target_vms:
            vm_ip = get_vm_ip(vm_name, inventory)
            if vm_ip:
                vm_ips.append(vm_ip)
            else:
                deployment['logs'].append(f"VM {vm_name} not found in inventory")
                return False
        
        # Execute file deployment using ansible (similar to your existing file operations)
        for vm_ip in vm_ips:
            for file_name in files:
                source_path = f"/app/fixfiles/{file_name}"
                
                if not os.path.exists(source_path):
                    deployment['logs'].append(f"Source file {source_path} not found")
                    return False
                
                # Use ansible to copy file
                ansible_command = [
                    'ansible', vm_ip, '-i', f'{vm_ip},',
                    '-m', 'copy',
                    '-a', f'src={source_path} dest={target_path}/{file_name} backup=yes',
                    '-u', target_user,
                    '--become'
                ]
                
                # Use the helper method from current_app
                result = current_app.run_ansible_command(ansible_command, deployment['logs'])
                if not result:
                    return False
                
                deployment['logs'].append(f"File {file_name} deployed to {vm_ip}:{target_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in file deployment step: {e}")
        deployment['logs'].append(f"File deployment failed: {str(e)}")
        return False

def execute_sql_deployment_step(step, db_inventory, deployment):
    """Execute SQL deployment step"""
    try:
        db_connection = step.get('dbConnection')
        db_user = step.get('dbUser')
        db_password_b64 = step.get('dbPassword')
        files = step.get('files', [])
        
        if not all([db_connection, db_user, db_password_b64, files]):
            deployment['logs'].append("Missing required SQL deployment parameters")
            return False
        
        # Decode password
        db_password = base64.b64decode(db_password_b64).decode('utf-8')
        
        # Get DB connection info
        db_info = get_db_connection_info(db_connection, db_inventory)
        if not db_info:
            deployment['logs'].append(f"Database connection {db_connection} not found")
            return False
        
        # Execute SQL files
        for sql_file in files:
            sql_path = f"/app/fixfiles/{sql_file}"
            
            if not os.path.exists(sql_path):
                deployment['logs'].append(f"SQL file {sql_path} not found")
                return False
            
            # Use psql to execute SQL file
            psql_command = [
                'psql',
                f"postgresql://{db_user}:{db_password}@{db_info['hostname']}:{db_info['port']}/{db_info['db_name']}",
                '-f', sql_path
            ]
            
            result = current_app.run_command_with_logging(psql_command, deployment['logs'])
            if not result:
                return False
            
            deployment['logs'].append(f"SQL file {sql_file} executed successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in SQL deployment step: {e}")
        deployment['logs'].append(f"SQL deployment failed: {str(e)}")
        return False

def execute_service_restart_step(step, inventory, deployment):
    """Execute systemctl service operation step"""
    try:
        service = step.get('service')
        operation = step.get('operation', 'status')
        target_vms = step.get('targetVMs', [])
        
        if not service or not target_vms:
            deployment['logs'].append("Missing service name or target VMs")
            return False
        
        # Get VM IPs
        vm_ips = []
        for vm_name in target_vms:
            vm_ip = get_vm_ip(vm_name, inventory)
            if vm_ip:
                vm_ips.append(vm_ip)
            else:
                deployment['logs'].append(f"VM {vm_name} not found in inventory")
                return False
        
        # Execute systemctl command on each VM
        for vm_ip in vm_ips:
            ansible_command = [
                'ansible', vm_ip, '-i', f'{vm_ip},',
                '-m', 'shell',
                '-a', f'systemctl {operation} {service}',
                '-u', 'root',
                '--become'
            ]
            
            result = current_app.run_ansible_command(ansible_command, deployment['logs'])
            if not result:
                return False
            
            deployment['logs'].append(f"Systemctl {operation} {service} executed on {vm_ip}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in service restart step: {e}")
        deployment['logs'].append(f"Service operation failed: {str(e)}")
        return False

def execute_ansible_playbook_step(step, inventory, deployment):
    """Execute ansible playbook step"""
    try:
        playbook_name = step.get('playbook')
        
        if not playbook_name:
            deployment['logs'].append("Missing playbook name")
            return False
        
        # Get playbook info from inventory
        playbook_info = get_playbook_info(playbook_name, inventory)
        if not playbook_info:
            deployment['logs'].append(f"Playbook {playbook_name} not found in inventory")
            return False
        
        # Build ansible-playbook command
        command = ['ansible-playbook', playbook_info['path']]
        
        if playbook_info.get('inventory'):
            command.extend(['-i', playbook_info['inventory']])
        
        if playbook_info.get('forks'):
            command.extend(['-f', str(playbook_info['forks'])])
        
        if playbook_info.get('extra_vars'):
            for extra_var in playbook_info['extra_vars']:
                command.extend(['-e', f'@{extra_var}'])
        
        if playbook_info.get('vault_password_file'):
            command.extend(['--vault-password-file', playbook_info['vault_password_file']])
        
        # Execute playbook
        result = current_app.run_command_with_logging(command, deployment['logs'])
        if not result:
            return False
        
        deployment['logs'].append(f"Ansible playbook {playbook_name} executed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in ansible playbook step: {e}")
        deployment['logs'].append(f"Ansible playbook failed: {str(e)}")
        return False

def execute_helm_upgrade_step(step, inventory, deployment):
    """Execute helm upgrade step"""
    try:
        deployment_type = step.get('helmDeploymentType')
        
        if not deployment_type:
            deployment['logs'].append("Missing helm deployment type")
            return False
        
        # Get helm command from inventory
        helm_command = get_helm_command(deployment_type, inventory)
        if not helm_command:
            deployment['logs'].append(f"Helm upgrade command for {deployment_type} not found")
            return False
        
        # Execute helm command
        command = helm_command.split()
        result = current_app.run_command_with_logging(command, deployment['logs'])
        if not result:
            return False
        
        deployment['logs'].append(f"Helm upgrade for {deployment_type} executed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in helm upgrade step: {e}")
        deployment['logs'].append(f"Helm upgrade failed: {str(e)}")
        return False
