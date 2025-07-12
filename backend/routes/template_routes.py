
from flask import Blueprint, request, jsonify, current_app
import json
import os
import uuid
import threading
import time
from datetime import datetime
import subprocess
import logging
import base64

template_bp = Blueprint('template', __name__)

# Store active deployments
active_deployments = {}

def execute_deployment_step(step, deployment_id, ft_number, orchestration_user='infadm'):
    """Execute a single deployment step"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        step_type = step.get('type')
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing step {step.get('order')}: {step.get('description')}")
        
        if step_type == 'file_deployment':
            # Execute file deployment
            files = step.get('files', [])
            target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
            target_user = step.get('targetUser', 'abpwrk1')
            target_vms = step.get('targetVMs', [])
            ft_number = step.get('ftNumber', '')
            
            for vm in target_vms:
                for file in files:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Copying {file} from FT {ft_number} to {vm}:{target_path} as {target_user}")
                    # Add your actual file copy logic here
                    time.sleep(2)  # Simulate processing time
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully copied {file} to {vm}")
        
        elif step_type == 'sql_deployment':
            # Execute SQL deployment with environment-specific values
            files = step.get('files', [])
            db_connection = step.get('dbConnection')
            db_user = step.get('dbUser')
            db_password_encoded = step.get('dbPassword', '')
            
            # Load db_inventory to get actual connection details
            db_inventory_path = '/app/inventory/db_inventory.json'
            if os.path.exists(db_inventory_path):
                with open(db_inventory_path, 'r') as f:
                    db_inventory = json.load(f)
                
                # Find the connection details
                connection_details = next(
                    (conn for conn in db_inventory.get('db_connections', []) 
                     if conn['db_connection'] == db_connection), None
                )
                
                if connection_details:
                    hostname = connection_details['hostname']
                    port = connection_details['port']
                    db_name = connection_details['db_name']
                    
                    # Decode base64 password
                    db_password = base64.b64decode(db_password_encoded).decode('utf-8') if db_password_encoded else ''
                    
                    for sql_file in files:
                        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing SQL file: {sql_file}")
                        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Command: psql -h {hostname} -p {port} -d {db_name} -U {db_user} -f {sql_file}")
                        # Add your actual SQL execution logic here
                        time.sleep(3)  # Simulate processing time
                        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed SQL file: {sql_file}")
        
        elif step_type == 'service_restart':
            # Execute service restart
            service = step.get('service', 'docker.service')
            operation = step.get('operation', 'restart')
            target_vms = step.get('targetVMs', [])
            
            for vm in target_vms:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Performing {operation} on {service} on {vm}")
                # Add your actual service operation logic here
                time.sleep(2)  # Simulate processing time
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully performed {operation} on {service} on {vm}")
        
        elif step_type == 'ansible_playbook':
            # Execute Ansible playbook with environment-specific values
            playbook_name = step.get('playbook', '')
            
            # Load inventory to get playbook details
            inventory_path = '/app/inventory/inventory.json'
            if os.path.exists(inventory_path):
                with open(inventory_path, 'r') as f:
                    inventory = json.load(f)
                
                # Find the playbook details
                playbook_details = next(
                    (pb for pb in inventory.get('playbooks', []) 
                     if pb['name'] == playbook_name), None
                )
                
                if playbook_details:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Running Ansible playbook: {playbook_name}")
                    
                    # Construct the ansible-playbook command
                    cmd_parts = [
                        'ansible-playbook',
                        playbook_details['path'],
                        '-i', playbook_details['inventory'],
                        '-f', str(playbook_details['forks']),
                        '-e', f"env_type={playbook_details['env_type']}"
                    ]
                    
                    # Add extra vars
                    for extra_var in playbook_details.get('extra_vars', []):
                        cmd_parts.extend(['-e', f"@{extra_var}"])
                    
                    # Add vault password file
                    if playbook_details.get('vault_password_file'):
                        cmd_parts.extend(['--vault-password-file', playbook_details['vault_password_file']])
                    
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Command: {' '.join(cmd_parts)}")
                    
                    # Add your actual Ansible playbook execution logic here
                    time.sleep(60)  # Simulate long running playbook (1 minute for demo)
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed Ansible playbook: {playbook_name}")
        
        elif step_type == 'helm_upgrade':
            # Execute Helm upgrade with environment-specific values
            deployment_type = step.get('helmDeploymentType', '')
            
            # Load inventory to get helm upgrade details
            inventory_path = '/app/inventory/inventory.json'
            if os.path.exists(inventory_path):
                with open(inventory_path, 'r') as f:
                    inventory = json.load(f)
                
                # Find the helm upgrade details
                helm_details = next(
                    (helm for helm in inventory.get('helm_upgrades', []) 
                     if helm['pod_name'] == deployment_type), None
                )
                
                if helm_details:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Performing Helm upgrade for: {deployment_type}")
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Command: {helm_details['command']}")
                    # Add your actual Helm upgrade logic here
                    time.sleep(5)  # Simulate processing time
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully performed Helm upgrade for: {deployment_type}")
        
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Step {step.get('order')} completed successfully")
        return True
        
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in step {step.get('order')}: {str(e)}")
        return False

def run_template_deployment(deployment_id, template, ft_number):
    """Run the template deployment in a separate thread"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return
    
    try:
        deployment['status'] = 'running'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting template deployment for {ft_number}")
        
        steps = template.get('steps', [])
        total_steps = len(steps)
        
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Total steps to execute: {total_steps}")
        
        # Execute steps in order
        for step in sorted(steps, key=lambda x: x.get('order', 0)):
            if deployment['status'] != 'running':
                break
                
            success = execute_deployment_step(step, deployment_id, ft_number)
            if not success:
                deployment['status'] = 'failed'
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Deployment failed at step {step.get('order')}")
                return
        
        deployment['status'] = 'success'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Template deployment completed successfully")
        
    except Exception as e:
        deployment['status'] = 'failed'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")

@template_bp.route('/api/templates/save', methods=['POST'])
def save_template():
    """Save a generated template to the deployment templates directory"""
    try:
        data = request.get_json()
        ft_number = data.get('ft_number')
        template = data.get('template')
        
        if not ft_number or not template:
            return jsonify({'error': 'Missing ft_number or template'}), 400
        
        # Create deployment templates directory if it doesn't exist
        templates_dir = '/app/deployment_templates'
        os.makedirs(templates_dir, exist_ok=True)
        
        # Save template to file with FT number in filename
        template_file = os.path.join(templates_dir, f'{ft_number}_template.json')
        with open(template_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        return jsonify({'message': 'Template saved successfully', 'path': template_file})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/templates/list', methods=['GET'])
def list_templates():
    """List all available templates from deployment templates directory"""
    try:
        templates = []
        templates_dir = '/app/deployment_templates'
        
        if os.path.exists(templates_dir):
            for file in os.listdir(templates_dir):
                if file.endswith('_template.json'):
                    ft_number = file.replace('_template.json', '')
                    templates.append(ft_number)
        
        return jsonify(templates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/templates/<ft_number>', methods=['GET'])
def get_template(ft_number):
    """Get a specific template from deployment templates directory"""
    try:
        template_file = os.path.join('/app/deployment_templates', f'{ft_number}_template.json')
        
        if not os.path.exists(template_file):
            return jsonify({'error': 'Template not found'}), 404
        
        with open(template_file, 'r') as f:
            template = json.load(f)
        
        return jsonify(template)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
    """Start a template deployment"""
    try:
        data = request.get_json()
        ft_number = data.get('ft_number')
        template = data.get('template')
        
        if not ft_number or not template:
            return jsonify({'error': 'Missing ft_number or template'}), 400
        
        # Generate deployment ID
        deployment_id = str(uuid.uuid4())
        
        # Initialize deployment tracking
        active_deployments[deployment_id] = {
            'id': deployment_id,
            'ft_number': ft_number,
            'status': 'running',
            'logs': [],
            'started_at': datetime.now().isoformat(),
            'template': template
        }
        
        # Start deployment in background thread
        deployment_thread = threading.Thread(
            target=run_template_deployment,
            args=(deployment_id, template, ft_number)
        )
        deployment_thread.daemon = True
        deployment_thread.start()
        
        return jsonify({
            'deploymentId': deployment_id,
            'message': 'Template deployment started',
            'status': 'running'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/deploy/template/<deployment_id>/logs', methods=['GET'])
def get_deployment_logs(deployment_id):
    """Get logs for a template deployment"""
    try:
        deployment = active_deployments.get(deployment_id)
        
        if not deployment:
            return jsonify({'error': 'Deployment not found'}), 404
        
        return jsonify({
            'logs': deployment['logs'],
            'status': deployment['status'],
            'ft_number': deployment['ft_number'],
            'started_at': deployment['started_at']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/users', methods=['GET'])
def get_users():
    """Get users from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify(['infadm', 'abpwrk1', 'root'])  # Default users
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        users = inventory.get('users', ['infadm', 'abpwrk1', 'root'])
        return jsonify(users)
        
    except Exception as e:
        return jsonify(['infadm', 'abpwrk1', 'root'])  # Fallback to default users

@template_bp.route('/api/playbooks', methods=['GET'])
def get_playbooks():
    """Get playbooks from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify({'playbooks': []})
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        return jsonify({'playbooks': inventory.get('playbooks', [])})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/helm-upgrades', methods=['GET'])
def get_helm_upgrades():
    """Get helm upgrades from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify({'helm_upgrades': []})
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        return jsonify({'helm_upgrades': inventory.get('helm_upgrades', [])})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/db-inventory', methods=['GET'])
def get_db_inventory():
    """Get database inventory"""
    try:
        db_inventory_path = '/app/inventory/db_inventory.json'
        
        if not os.path.exists(db_inventory_path):
            return jsonify({'db_connections': [], 'db_users': []})
        
        with open(db_inventory_path, 'r') as f:
            db_inventory = json.load(f)
        
        return jsonify(db_inventory)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
