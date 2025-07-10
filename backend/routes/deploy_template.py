
from flask import Blueprint, request, jsonify, current_app, session
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

def get_current_user():
    """Get current authenticated user from session"""
    return session.get('user')

def log_message(deployment_id, message):
    """Add a log message to the deployment using main app's system"""
    # Import here to avoid circular imports
    from app import deployments
    
    if deployment_id in deployments:
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        deployments[deployment_id]['logs'].append(log_entry)
        
        # Also log to application logger for debugging
        current_app.logger.info(f"[{deployment_id}] {message}")

def execute_template_step(step, deployment_id, ft_number, current_user):
    """Execute a template step using the main app's deployment system"""
    from app import deployments, run_file_deployment, run_sql_deployment, process_systemd_operation, run_shell_deployment
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        step_type = step.get('type')
        log_message(deployment_id, f"Executing step {step.get('order')}: {step.get('description')}")
        
        if step_type == 'file_deployment':
            # Convert template step to file deployment format
            files = step.get('files', [])
            target_vms = step.get('targetVMs', [])
            target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
            target_user = step.get('targetUser', 'abpwrk1')
            ft_source = step.get('ftNumber', ft_number)
            
            for file in files:
                for vm in target_vms:
                    # Use main app's file deployment function
                    deployment_data = {
                        'ft': ft_source,
                        'file': file,
                        'targetPath': target_path,
                        'targetUser': target_user,
                        'vms': [vm]
                    }
                    success = run_file_deployment(deployment_id, deployment_data, current_user)
                    if not success:
                        return False
            return True
            
        elif step_type == 'sql_deployment':
            # Convert template step to SQL deployment format
            files = step.get('files', [])
            db_connection = step.get('dbConnection')
            db_user = step.get('dbUser')
            db_password_encoded = step.get('dbPassword', '')
            ft_source = step.get('ftNumber', ft_number)
            
            for sql_file in files:
                deployment_data = {
                    'ft': ft_source,
                    'file': sql_file,
                    'dbConnection': db_connection,
                    'dbUser': db_user,
                    'dbPassword': db_password_encoded
                }
                success = run_sql_deployment(deployment_id, deployment_data, current_user)
                if not success:
                    return False
            return True
            
        elif step_type == 'service_restart':
            # Convert template step to systemd operation format
            service = step.get('service', 'docker.service')
            operation = step.get('operation', 'restart')
            target_vms = step.get('targetVMs', [])
            
            deployment_data = {
                'service': service,
                'operation': operation,
                'vms': target_vms
            }
            return process_systemd_operation(deployment_id, deployment_data, current_user)
            
        elif step_type == 'ansible_playbook':
            # Execute Ansible playbook using shell command
            playbook_name = step.get('playbook')
            
            # Load inventory to get playbook details
            inventory_path = '/app/inventory/inventory.json'
            with open(inventory_path, 'r') as f:
                inventory = json.load(f)
            
            playbook_details = next(
                (pb for pb in inventory.get('playbooks', []) 
                 if pb['name'] == playbook_name), None
            )
            
            if not playbook_details:
                log_message(deployment_id, f"ERROR: Playbook '{playbook_name}' not found")
                return False
            
            playbook_path = playbook_details['path']
            inventory_file = playbook_details['inventory']
            extra_vars = playbook_details.get('extra_vars', [])
            
            # Build command
            cmd = f"ansible-playbook {playbook_path} -i {inventory_file} -f 10"
            for var in extra_vars:
                cmd += f" -e {var}"
            cmd += " -vvv"
            
            deployment_data = {
                'command': cmd,
                'vms': ['localhost']  # Ansible runs from control node
            }
            return run_shell_deployment(deployment_id, deployment_data, current_user)
            
        elif step_type == 'helm_upgrade':
            # Execute Helm upgrade using shell command
            pod_name = step.get('pod')
            
            # Load inventory to get helm upgrade details
            inventory_path = '/app/inventory/inventory.json'
            with open(inventory_path, 'r') as f:
                inventory = json.load(f)
            
            helm_details = next(
                (helm for helm in inventory.get('helm_upgrades', []) 
                 if helm['pod'] == pod_name), None
            )
            
            if not helm_details:
                log_message(deployment_id, f"ERROR: Helm upgrade for pod '{pod_name}' not found")
                return False
            
            command = helm_details['command']
            deployment_data = {
                'command': command,
                'vms': ['localhost']  # Helm runs from control node
            }
            return run_shell_deployment(deployment_id, deployment_data, current_user)
            
        else:
            log_message(deployment_id, f"ERROR: Unknown step type: {step_type}")
            return False
            
    except Exception as e:
        log_message(deployment_id, f"ERROR in step {step.get('order')}: {str(e)}")
        return False

def run_template_deployment(deployment_id, template, ft_number):
    """Run the template deployment using main app's system"""
    from app import deployments, save_deployment_history
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return
    
    try:
        deployment['status'] = 'running'
        current_user = deployment.get('logged_in_user_info', {'username': 'unknown'})
        
        log_message(deployment_id, f"Starting template deployment for {ft_number}")
        
        steps = template.get('steps', [])
        total_steps = len(steps)
        
        log_message(deployment_id, f"Total steps to execute: {total_steps}")
        
        # Execute steps in order
        for step in sorted(steps, key=lambda x: x.get('order', 0)):
            if deployment['status'] != 'running':
                break
                
            success = execute_template_step(step, deployment_id, ft_number, current_user)
            if not success:
                deployment['status'] = 'failed'
                log_message(deployment_id, f"Deployment failed at step {step.get('order')}")
                save_deployment_history()
                return
        
        deployment['status'] = 'success'
        log_message(deployment_id, f"Template deployment completed successfully")
        
        # Save logs to deployment history
        save_deployment_history()
        
    except Exception as e:
        deployment['status'] = 'failed'
        log_message(deployment_id, f"ERROR: {str(e)}")
        save_deployment_history()

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
    """Start a template deployment using main app's deployment system"""
    try:
        from app import deployments
        
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json()
        ft_number = data.get('ft_number')
        template = data.get('template')
        
        if not ft_number or not template:
            return jsonify({'error': 'Missing ft_number or template'}), 400
        
        # Generate deployment ID
        deployment_id = str(uuid.uuid4())
        
        # Initialize deployment tracking in main deployments dictionary
        deployments[deployment_id] = {
            'id': deployment_id,
            'type': 'template_deployment',
            'ft': ft_number,
            'status': 'running',
            'timestamp': time.time(),
            'logs': [],
            'orchestration_user': current_user['username'],
            'user_role': current_user.get('role', 'unknown'),
            'logged_in_user': current_user['username'],
            'logged_in_user_info': current_user,
            'template': template
        }
        
        current_app.logger.info(f"Template deployment initiated by {current_user['username']} with ID: {deployment_id}")
        
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
            'status': 'running',
            'initiatedBy': current_user['username']
        })
        
    except Exception as e:
        current_app.logger.error(f"Error starting template deployment: {str(e)}")
        return jsonify({'error': str(e)}), 500

@deploy_template_bp.route('/api/deploy/template/<deployment_id>/logs', methods=['GET'])
def get_deployment_logs(deployment_id):
    """Get logs for a template deployment using main app's system"""
    try:
        from app import deployments
        
        deployment = deployments.get(deployment_id)
        
        if not deployment:
            return jsonify({'error': 'Deployment not found'}), 404
        
        current_user = deployment.get('logged_in_user_info', {'username': 'unknown'})
        
        return jsonify({
            'logs': deployment['logs'],
            'status': deployment['status'],
            'ft_number': deployment.get('ft', ''),
            'started_at': datetime.fromtimestamp(deployment.get('timestamp', time.time())).isoformat(),
            'initiated_by': current_user['username']
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting deployment logs: {str(e)}")
        return jsonify({'error': str(e)}), 500
