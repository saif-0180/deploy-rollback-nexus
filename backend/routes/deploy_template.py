
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

deploy_template_bp = Blueprint('deploy_template', __name__)

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
            return execute_file_deployment(step, deployment_id, ft_number)
        elif step_type == 'sql_deployment':
            return execute_sql_deployment(step, deployment_id, ft_number)
        elif step_type == 'service_restart':
            return execute_service_restart(step, deployment_id)
        elif step_type == 'ansible_playbook':
            return execute_ansible_playbook(step, deployment_id)
        elif step_type == 'helm_upgrade':
            return execute_helm_upgrade(step, deployment_id)
        else:
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Unknown step type: {step_type}")
            return False
            
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in step {step.get('order')}: {str(e)}")
        return False

def execute_file_deployment(step, deployment_id, ft_number):
    """Execute file deployment step"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        files = step.get('files', [])
        target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
        target_user = step.get('targetUser', 'abpwrk1')
        target_vms = step.get('targetVMs', [])
        ft_source = step.get('ftNumber', ft_number)
        
        for vm in target_vms:
            for file in files:
                source_file = os.path.join('/app/fixfiles', 'AllFts', ft_source, file)
                
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Copying {file} from FT {ft_source} to {vm}:{target_path}")
                
                if not os.path.exists(source_file):
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Source file not found: {source_file}")
                    return False
                
                # Construct SCP command
                cmd = [
                    'scp', '-o', 'StrictHostKeyChecking=no', 
                    source_file, 
                    f"{target_user}@{vm}:{target_path}/{file}"
                ]
                
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Command: {' '.join(cmd)}")
                
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=300
                    )
                    
                    if result.returncode == 0:
                        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully copied {file} to {vm}")
                        
                        # Set ownership if needed
                        if target_user != 'root':
                            chown_cmd = [
                                'ssh', '-o', 'StrictHostKeyChecking=no',
                                f"root@{vm}",
                                f"chown {target_user}:{target_user} {target_path}/{file}"
                            ]
                            subprocess.run(chown_cmd, capture_output=True, text=True, timeout=60)
                            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Set ownership of {file} to {target_user}")
                    else:
                        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR copying {file} to {vm}: {result.stderr}")
                        return False
                        
                except subprocess.TimeoutExpired:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: File copy timed out for {file}")
                    return False
                except Exception as e:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
                    return False
        
        return True
        
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in file deployment: {str(e)}")
        return False

def execute_sql_deployment(step, deployment_id, ft_number):
    """Execute SQL deployment step"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        files = step.get('files', [])
        db_connection = step.get('dbConnection')
        db_user = step.get('dbUser')
        db_password_encoded = step.get('dbPassword', '')
        ft_source = step.get('ftNumber', ft_number)
        
        # Load db_inventory to get actual connection details
        db_inventory_path = '/app/inventory/db_inventory.json'
        if not os.path.exists(db_inventory_path):
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: DB inventory file not found")
            return False
        
        with open(db_inventory_path, 'r') as f:
            db_inventory = json.load(f)
        
        # Find the connection details
        connection_details = next(
            (conn for conn in db_inventory.get('db_connections', []) 
             if conn['db_connection'] == db_connection), None
        )
        
        if not connection_details:
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: DB connection '{db_connection}' not found in inventory")
            return False
        
        hostname = connection_details['hostname']
        port = connection_details['port']
        db_name = connection_details['db_name']
        
        # Decode base64 password
        db_password = base64.b64decode(db_password_encoded).decode('utf-8') if db_password_encoded else ''
        
        for sql_file in files:
            source_file = os.path.join('/app/fixfiles', 'AllFts', ft_source, sql_file)
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing SQL file: {sql_file}")
            
            if not os.path.exists(source_file):
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: SQL file not found: {source_file}")
                return False
            
            # Check if psql is available
            psql_check = subprocess.run(["which", "psql"], capture_output=True, text=True)
            if psql_check.returncode != 0:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: psql command not found")
                return False
            
            cmd = ["psql", "-h", hostname, "-p", port, "-d", db_name, "-U", db_user, "-f", source_file]
            env = os.environ.copy()
            
            if db_password:
                env["PGPASSWORD"] = db_password
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Command: psql -h {hostname} -p {port} -d {db_name} -U {db_user} -f {sql_file}")
            
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    env=env,
                    timeout=300
                )
                
                # Process output
                all_output = ""
                if result.stdout:
                    all_output += result.stdout
                if result.stderr:
                    all_output += result.stderr
                
                if all_output:
                    for line in all_output.strip().split('\n'):
                        line_stripped = line.strip()
                        if line_stripped:
                            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {line_stripped}")
                
                if result.returncode == 0:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed SQL file: {sql_file}")
                else:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: SQL execution failed for {sql_file}")
                    return False
                    
            except subprocess.TimeoutExpired:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: SQL execution timed out for {sql_file}")
                return False
            except Exception as e:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
                return False
        
        return True
        
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in SQL deployment: {str(e)}")
        return False

def execute_service_restart(step, deployment_id):
    """Execute service restart step"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        service = step.get('service', 'docker.service')
        operation = step.get('operation', 'restart')
        target_vms = step.get('targetVMs', [])
        
        for vm in target_vms:
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Performing {operation} on {service} on {vm}")
            
            cmd = [
                'ssh', '-o', 'StrictHostKeyChecking=no',
                f"root@{vm}",
                f"systemctl {operation} {service}"
            ]
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Command: {' '.join(cmd)}")
            
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=120
                )
                
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {line.strip()}")
                
                if result.stderr:
                    for line in result.stderr.strip().split('\n'):
                        if line.strip():
                            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {line.strip()}")
                
                if result.returncode == 0:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully performed {operation} on {service} on {vm}")
                else:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Service operation failed on {vm}")
                    return False
                    
            except subprocess.TimeoutExpired:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Service operation timed out on {vm}")
                return False
            except Exception as e:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
                return False
        
        return True
        
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in service restart: {str(e)}")
        return False

def execute_ansible_playbook(step, deployment_id):
    """Execute Ansible playbook step"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        playbook_name = step.get('playbook', '')
        
        # Load inventory to get playbook details
        inventory_path = '/app/inventory/inventory.json'
        if not os.path.exists(inventory_path):
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Inventory file not found")
            return False
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        # Find the playbook details
        playbook_details = next(
            (pb for pb in inventory.get('playbooks', []) 
             if pb['name'] == playbook_name), None
        )
        
        if not playbook_details:
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Playbook '{playbook_name}' not found in inventory")
            return False
        
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
        
        try:
            # Use Popen for real-time output
            process = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {output.strip()}")
            
            rc = process.poll()
            
            if rc == 0:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed Ansible playbook: {playbook_name}")
                return True
            else:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Ansible playbook failed with return code: {rc}")
                return False
                
        except Exception as e:
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
            return False
        
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in Ansible playbook execution: {str(e)}")
        return False

def execute_helm_upgrade(step, deployment_id):
    """Execute Helm upgrade step"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        deployment_type = step.get('helmDeploymentType', '')
        
        # Load inventory to get helm upgrade details
        inventory_path = '/app/inventory/inventory.json'
        if not os.path.exists(inventory_path):
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Inventory file not found")
            return False
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        # Find the helm upgrade details
        helm_details = next(
            (helm for helm in inventory.get('helm_upgrades', []) 
             if helm['pod_name'] == deployment_type), None
        )
        
        if not helm_details:
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Helm deployment type '{deployment_type}' not found in inventory")
            return False
        
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Performing Helm upgrade for: {deployment_type}")
        
        # Execute on batch1 VM as admin user
        cmd = [
            'ssh', '-o', 'StrictHostKeyChecking=no',
            'admin@batch1',
            helm_details['command']
        ]
        
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Command: {' '.join(cmd)}")
        
        try:
            # Use Popen for real-time output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output in real-time
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {output.strip()}")
            
            rc = process.poll()
            
            if rc == 0:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully performed Helm upgrade for: {deployment_type}")
                return True
            else:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Helm upgrade failed with return code: {rc}")
                return False
                
        except Exception as e:
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
            return False
        
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in Helm upgrade: {str(e)}")
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
                save_deployment_logs(deployment_id, deployment, ft_number)
                return
        
        deployment['status'] = 'success'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Template deployment completed successfully")
        
        # Save logs to deployment history
        save_deployment_logs(deployment_id, deployment, ft_number)
        
    except Exception as e:
        deployment['status'] = 'failed'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
        save_deployment_logs(deployment_id, deployment, ft_number)

def save_deployment_logs(deployment_id, deployment, ft_number):
    """Save deployment logs to deployment history"""
    try:
        # Import here to avoid circular imports
        from app import deployments, save_deployment_history
        
        # Add to main deployments dictionary for history display
        deployments[deployment_id] = {
            'id': deployment_id,
            'type': 'template_deployment',
            'ft': ft_number,
            'status': deployment['status'],
            'timestamp': time.time(),
            'logs': deployment['logs'],
            'orchestration_user': 'infadm'
        }
        
        # Save to file
        save_deployment_history()
        
        # Also save to separate template deployment logs directory
        logs_dir = '/app/logs/deployment_templates'
        os.makedirs(logs_dir, exist_ok=True)
        
        log_entry = {
            'deployment_id': deployment_id,
            'ft_number': ft_number,
            'operation': 'template_deployment',
            'timestamp': deployment['started_at'],
            'status': deployment['status'],
            'logs': deployment['logs'],
            'orchestration_user': 'infadm'
        }
        
        log_file = os.path.join(logs_dir, f"{deployment_id}.json")
        with open(log_file, 'w') as f:
            json.dump(log_entry, f, indent=2)
            
    except Exception as e:
        print(f"Failed to save deployment logs: {str(e)}")

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
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

@deploy_template_bp.route('/api/deploy/template/<deployment_id>/logs', methods=['GET'])
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

# Inventory API endpoints that were referenced in the template generator
@deploy_template_bp.route('/api/playbooks', methods=['GET'])
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

@deploy_template_bp.route('/api/helm-upgrades', methods=['GET'])
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

@deploy_template_bp.route('/api/db-inventory', methods=['GET'])
def get_db_inventory():
    """Get database inventory"""
    try:
        db_inventory_path = '/app/inventory/db_inventory.json'
        
        if not os.path.exists(db_inventory_path):
            return jsonify({'db_connections': [], 'db_users': []})
        
        with open(db_inventory_path, 'r') as f:
            db_inventory = json.load(f)
        
        return jsonify(db_inventory)
        
    except Exception e:
        return jsonify({'error': str(e)}), 500
