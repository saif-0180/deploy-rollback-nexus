
# =============================================================================
# DEPLOY TEMPLATE FUNCTIONALITY - ADD ALL THIS CODE TO YOUR app.py
# =============================================================================

import os
import json
import uuid
import base64
import subprocess
from datetime import datetime, timezone
from flask import request, jsonify
import logging

# Add this logger configuration near the top of your app.py
deploy_template_logger = logging.getLogger('deploy_template')
deploy_template_logger.setLevel(logging.DEBUG)

# =============================================================================
# HELPER FUNCTIONS - Add these functions to your app.py
# =============================================================================

def load_inventory():
    """Load inventory data from JSON files"""
    try:
        with open('/app/inventory/inventory.json', 'r') as f:
            inventory = json.load(f)
        with open('/app/inventory/db_inventory.json', 'r') as f:
            db_inventory = json.load(f)
        return inventory, db_inventory
    except Exception as e:
        deploy_template_logger.error(f"Error loading inventory: {str(e)}")
        return None, None

def get_vm_ip(vm_name, inventory):
    """Get VM IP from inventory"""
    for vm in inventory.get('vms', []):
        if vm['name'] == vm_name:
            return vm['ip']
    return None

def get_db_connection_details(db_connection, db_inventory):
    """Get database connection details from inventory"""
    for conn in db_inventory.get('db_connections', []):
        if conn['db_connection'] == db_connection:
            return conn
    return None

def get_playbook_details(playbook_name, inventory):
    """Get playbook details from inventory"""
    for playbook in inventory.get('playbooks', []):
        if playbook['name'] == playbook_name:
            return playbook
    return None

def get_helm_command(helm_type, inventory):
    """Get helm command from inventory"""
    for helm in inventory.get('helm_upgrades', []):
        if helm['pod_name'] == helm_type:
            return helm['command']
    return None

def run_ansible_command(command, logs):
    """Run ansible command and capture output"""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend(result.stderr.split('\n'))
        
        if result.returncode == 0:
            logs.append(f"Command executed successfully: {' '.join(command)}")
            return True
        else:
            logs.append(f"Command failed with return code {result.returncode}: {' '.join(command)}")
            return False
            
    except subprocess.TimeoutExpired:
        logs.append(f"Command timed out: {' '.join(command)}")
        return False
    except Exception as e:
        logs.append(f"Error executing command: {str(e)}")
        return False

def run_command_with_logging(command, logs):
    """Run command and capture output with logging"""
    try:
        logs.append(f"Executing command: {' '.join(command)}")
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    logs.append(f"STDOUT: {line}")
        
        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip():
                    logs.append(f"STDERR: {line}")
        
        if result.returncode == 0:
            logs.append(f"Command completed successfully")
            return True
        else:
            logs.append(f"Command failed with return code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        logs.append(f"Command timed out after 10 minutes")
        return False
    except Exception as e:
        logs.append(f"Error executing command: {str(e)}")
        return False

def execute_file_deployment_step(step, inventory, deployment_id):
    """Execute file deployment step using ansible"""
    logs = []
    success = True
    
    try:
        logs.append(f"=== Executing File Deployment Step {step['order']} ===")
        logs.append(f"Description: {step['description']}")
        
        # Get target VMs and their IPs
        target_hosts = []
        for vm_name in step.get('targetVMs', []):
            vm_ip = get_vm_ip(vm_name, inventory)
            if vm_ip:
                target_hosts.append(vm_ip)
                logs.append(f"Target VM {vm_name}: {vm_ip}")
            else:
                logs.append(f"Warning: VM {vm_name} not found in inventory")
        
        if not target_hosts:
            logs.append("Error: No valid target VMs found")
            return False, logs
        
        # Process each file
        for file_name in step.get('files', []):
            logs.append(f"Deploying file: {file_name}")
            
            source_path = f"/app/fixfiles/{file_name}"
            target_path = step.get('targetPath', '/tmp')
            target_user = step.get('targetUser', 'root')
            
            if not os.path.exists(source_path):
                logs.append(f"Error: Source file {source_path} not found")
                success = False
                continue
            
            # Create ansible command for file copy
            for host in target_hosts:
                ansible_cmd = [
                    'ansible', host,
                    '-i', f'{host},',
                    '-m', 'copy',
                    '-a', f'src={source_path} dest={target_path}/{file_name} owner={target_user} mode=0644',
                    '-u', target_user,
                    '--ssh-common-args=-o StrictHostKeyChecking=no'
                ]
                
                logs.append(f"Copying {file_name} to {host}:{target_path}")
                if not run_ansible_command(ansible_cmd, logs):
                    success = False
        
        logs.append(f"=== File Deployment Step {step['order']} {'Completed Successfully' if success else 'Failed'} ===")
        
    except Exception as e:
        logs.append(f"Error in file deployment step: {str(e)}")
        success = False
    
    return success, logs

def execute_sql_deployment_step(step, db_inventory, deployment_id):
    """Execute SQL deployment step"""
    logs = []
    success = True
    
    try:
        logs.append(f"=== Executing SQL Deployment Step {step['order']} ===")
        logs.append(f"Description: {step['description']}")
        
        # Get database connection details
        db_conn_name = step.get('dbConnection')
        db_details = get_db_connection_details(db_conn_name, db_inventory)
        
        if not db_details:
            logs.append(f"Error: Database connection {db_conn_name} not found")
            return False, logs
        
        # Decode password
        db_password = base64.b64decode(step.get('dbPassword', '')).decode('utf-8')
        db_user = step.get('dbUser')
        
        logs.append(f"Database: {db_details['hostname']}:{db_details['port']}/{db_details['db_name']}")
        logs.append(f"User: {db_user}")
        
        # Process SQL files
        for file_name in step.get('files', []):
            sql_file_path = f"/app/fixfiles/{file_name}"
            
            if not os.path.exists(sql_file_path):
                logs.append(f"Error: SQL file {sql_file_path} not found")
                success = False
                continue
            
            logs.append(f"Executing SQL file: {file_name}")
            
            # Create psql command
            psql_cmd = [
                'psql',
                '-h', db_details['hostname'],
                '-p', db_details['port'],
                '-d', db_details['db_name'],
                '-U', db_user,
                '-f', sql_file_path,
                '-v', 'ON_ERROR_STOP=1'
            ]
            
            # Set password environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            try:
                result = subprocess.run(psql_cmd, capture_output=True, text=True, env=env, timeout=300)
                
                if result.stdout:
                    logs.extend(result.stdout.split('\n'))
                if result.stderr:
                    logs.extend(result.stderr.split('\n'))
                
                if result.returncode == 0:
                    logs.append(f"SQL file {file_name} executed successfully")
                else:
                    logs.append(f"SQL file {file_name} failed with return code {result.returncode}")
                    success = False
                    
            except subprocess.TimeoutExpired:
                logs.append(f"SQL execution timed out for file {file_name}")
                success = False
            except Exception as e:
                logs.append(f"Error executing SQL file {file_name}: {str(e)}")
                success = False
        
        logs.append(f"=== SQL Deployment Step {step['order']} {'Completed Successfully' if success else 'Failed'} ===")
        
    except Exception as e:
        logs.append(f"Error in SQL deployment step: {str(e)}")
        success = False
    
    return success, logs

def execute_service_restart_step(step, inventory, deployment_id):
    """Execute service restart step using systemctl"""
    logs = []
    success = True
    
    try:
        logs.append(f"=== Executing Service Restart Step {step['order']} ===")
        logs.append(f"Description: {step['description']}")
        
        service_name = step.get('service')
        operation = step.get('operation', 'status')
        
        logs.append(f"Service: {service_name}")
        logs.append(f"Operation: {operation}")
        
        # Get target VMs
        target_hosts = []
        for vm_name in step.get('targetVMs', []):
            vm_ip = get_vm_ip(vm_name, inventory)
            if vm_ip:
                target_hosts.append(vm_ip)
                logs.append(f"Target VM {vm_name}: {vm_ip}")
        
        if not target_hosts:
            logs.append("Error: No valid target VMs found")
            return False, logs
        
        # Execute systemctl command on each host
        for host in target_hosts:
            logs.append(f"Executing systemctl {operation} {service_name} on {host}")
            
            ansible_cmd = [
                'ansible', host,
                '-i', f'{host},',
                '-m', 'shell',
                '-a', f'systemctl {operation} {service_name}',
                '-u', 'root',
                '--ssh-common-args=-o StrictHostKeyChecking=no'
            ]
            
            if not run_ansible_command(ansible_cmd, logs):
                success = False
        
        logs.append(f"=== Service Restart Step {step['order']} {'Completed Successfully' if success else 'Failed'} ===")
        
    except Exception as e:
        logs.append(f"Error in service restart step: {str(e)}")
        success = False
    
    return success, logs

def execute_ansible_playbook_step(step, inventory, deployment_id):
    """Execute ansible playbook step"""
    logs = []
    success = True
    
    try:
        logs.append(f"=== Executing Ansible Playbook Step {step['order']} ===")
        logs.append(f"Description: {step['description']}")
        
        playbook_name = step.get('playbook')
        playbook_details = get_playbook_details(playbook_name, inventory)
        
        if not playbook_details:
            logs.append(f"Error: Playbook {playbook_name} not found in inventory")
            return False, logs
        
        logs.append(f"Playbook: {playbook_details['name']}")
        logs.append(f"Path: {playbook_details['path']}")
        
        # Build ansible-playbook command
        ansible_cmd = [
            'ansible-playbook',
            playbook_details['path'],
            '-i', playbook_details['inventory'],
            '-f', str(playbook_details.get('forks', 10))
        ]
        
        # Add extra vars
        for extra_var_file in playbook_details.get('extra_vars', []):
            ansible_cmd.extend(['-e', f'@{extra_var_file}'])
        
        # Add vault password file if present
        if playbook_details.get('vault_password_file'):
            ansible_cmd.extend(['--vault-password-file', playbook_details['vault_password_file']])
        
        logs.append(f"Executing playbook command: {' '.join(ansible_cmd)}")
        
        if not run_command_with_logging(ansible_cmd, logs):
            success = False
        
        logs.append(f"=== Ansible Playbook Step {step['order']} {'Completed Successfully' if success else 'Failed'} ===")
        
    except Exception as e:
        logs.append(f"Error in ansible playbook step: {str(e)}")
        success = False
    
    return success, logs

def execute_helm_upgrade_step(step, inventory, deployment_id):
    """Execute helm upgrade step"""
    logs = []
    success = True
    
    try:
        logs.append(f"=== Executing Helm Upgrade Step {step['order']} ===")
        logs.append(f"Description: {step['description']}")
        
        helm_type = step.get('helmDeploymentType')
        helm_command = get_helm_command(helm_type, inventory)
        
        if not helm_command:
            logs.append(f"Error: Helm command for {helm_type} not found in inventory")
            return False, logs
        
        logs.append(f"Helm deployment type: {helm_type}")
        logs.append(f"Command: {helm_command}")
        
        # Execute helm command using shell
        shell_cmd = ['bash', '-c', helm_command]
        
        if not run_command_with_logging(shell_cmd, logs):
            success = False
        
        logs.append(f"=== Helm Upgrade Step {step['order']} {'Completed Successfully' if success else 'Failed'} ===")
        
    except Exception as e:
        logs.append(f"Error in helm upgrade step: {str(e)}")
        success = False
    
    return success, logs

def execute_template_step(step, inventory, db_inventory, deployment_id):
    """Execute a single template step based on its type"""
    step_type = step.get('type')
    
    if step_type == 'file_deployment':
        return execute_file_deployment_step(step, inventory, deployment_id)
    elif step_type == 'sql_deployment':
        return execute_sql_deployment_step(step, db_inventory, deployment_id)
    elif step_type == 'service_restart':
        return execute_service_restart_step(step, inventory, deployment_id)
    elif step_type == 'ansible_playbook':
        return execute_ansible_playbook_step(step, inventory, deployment_id)
    elif step_type == 'helm_upgrade':
        return execute_helm_upgrade_step(step, inventory, deployment_id)
    else:
        return False, [f"Unknown step type: {step_type}"]

# =============================================================================
# FLASK ROUTES - Add these routes to your app.py
# =============================================================================

@app.route('/api/deploy/templates', methods=['GET'])
def get_templates():
    """Get list of available deployment templates"""
    try:
        template_dir = '/app/deployment_templates'
        if not os.path.exists(template_dir):
            deploy_template_logger.warning(f"Template directory {template_dir} does not exist")
            return jsonify({'templates': []})
        
        templates = []
        for filename in os.listdir(template_dir):
            if filename.endswith('_template.json'):
                templates.append(filename)
        
        deploy_template_logger.debug(f"Found templates: {templates}")
        return jsonify({'templates': templates})
        
    except Exception as e:
        deploy_template_logger.error(f"Error listing templates: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/deploy/templates/<template_name>', methods=['GET'])
def get_template(template_name):
    """Get specific deployment template"""
    try:
        template_path = f'/app/deployment_templates/{template_name}'
        
        if not os.path.exists(template_path):
            return jsonify({'error': 'Template not found'}), 404
        
        with open(template_path, 'r') as f:
            template_data = json.load(f)
        
        deploy_template_logger.debug(f"Loaded template {template_name}: {template_data}")
        return jsonify({'template': template_data})
        
    except Exception as e:
        deploy_template_logger.error(f"Error loading template {template_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/deploy/templates/execute', methods=['POST'])
def execute_template():
    """Execute a deployment template"""
    try:
        data = request.get_json()
        template_name = data.get('template_name')
        
        if not template_name:
            return jsonify({'error': 'Template name is required'}), 400
        
        # Load template
        template_path = f'/app/deployment_templates/{template_name}'
        if not os.path.exists(template_path):
            return jsonify({'error': 'Template not found'}), 404
        
        with open(template_path, 'r') as f:
            template_data = json.load(f)
        
        # Load inventory
        inventory, db_inventory = load_inventory()
        if not inventory or not db_inventory:
            return jsonify({'error': 'Failed to load inventory'}), 500
        
        # Generate deployment ID
        deployment_id = str(uuid.uuid4())
        
        # Initialize deployment tracking
        if not hasattr(app, 'deployments'):
            app.deployments = {}
        
        app.deployments[deployment_id] = {
            'type': 'template_deployment',
            'status': 'running',
            'logs': [],
            'template_name': template_name,
            'ft_number': template_data.get('metadata', {}).get('ft_number', 'unknown'),
            'start_time': datetime.now(timezone.utc).isoformat(),
            'steps_total': len(template_data.get('steps', [])),
            'steps_completed': 0
        }
        
        deploy_template_logger.info(f"Starting template deployment {deployment_id} for {template_name}")
        
        # Execute template in background thread
        def execute_template_background():
            try:
                steps = template_data.get('steps', [])
                dependencies = template_data.get('dependencies', [])
                
                # Sort steps by order
                steps.sort(key=lambda x: x.get('order', 0))
                
                overall_success = True
                
                for step in steps:
                    step_order = step.get('order')
                    step_type = step.get('type')
                    
                    app.deployments[deployment_id]['logs'].append(f"\n=== Starting Step {step_order}: {step_type} ===")
                    app.deployments[deployment_id]['logs'].append(f"Description: {step.get('description', 'N/A')}")
                    
                    # Execute the step
                    success, step_logs = execute_template_step(step, inventory, db_inventory, deployment_id)
                    
                    # Add step logs to deployment logs
                    app.deployments[deployment_id]['logs'].extend(step_logs)
                    
                    # Update progress
                    app.deployments[deployment_id]['steps_completed'] += 1
                    
                    if not success:
                        overall_success = False
                        app.deployments[deployment_id]['logs'].append(f"Step {step_order} failed - stopping template execution")
                        break
                    
                    app.deployments[deployment_id]['logs'].append(f"Step {step_order} completed successfully")
                
                # Update final status
                final_status = 'success' if overall_success else 'failed'
                app.deployments[deployment_id]['status'] = final_status
                app.deployments[deployment_id]['end_time'] = datetime.now(timezone.utc).isoformat()
                
                app.deployments[deployment_id]['logs'].append(f"\n=== Template Deployment {final_status.upper()} ===")
                
                deploy_template_logger.info(f"Template deployment {deployment_id} completed with status: {final_status}")
                
            except Exception as e:
                deploy_template_logger.error(f"Error in template execution background thread: {str(e)}")
                app.deployments[deployment_id]['status'] = 'failed'
                app.deployments[deployment_id]['logs'].append(f"Template execution failed: {str(e)}")
                app.deployments[deployment_id]['end_time'] = datetime.now(timezone.utc).isoformat()
        
        # Start background execution
        import threading
        thread = threading.Thread(target=execute_template_background)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'deployment_id': deployment_id,
            'status': 'started',
            'template_name': template_name
        })
        
    except Exception as e:
        deploy_template_logger.error(f"Error executing template: {str(e)}")
        return jsonify({'error': str(e)}), 500

# =============================================================================
# END OF DEPLOY TEMPLATE CODE TO ADD TO app.py
# =============================================================================
