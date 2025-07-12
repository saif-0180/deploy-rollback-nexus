
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
from routes.auth_routes import get_current_user

deploy_template_bp = Blueprint('deploy_template', __name__)

def execute_file_deployment_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute file deployment step using app.py's run_file_deployment function"""
    from app import run_file_deployment
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        files = step.get('files', [])
        target_vms = step.get('targetVMs', [])
        target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
        target_user = step.get('targetUser', 'abpwrk1')
        ft_source = step.get('ftNumber', ft_number)

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Starting file deployment: {', '.join(files)} to {', '.join(target_vms)}:{target_path}"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")
        save_deployment_history()

        # Use app.py's run_file_deployment function
        result = run_file_deployment(
            target_vms, 
            files, 
            ft_source, 
            target_path, 
            target_user, 
            current_user
        )

        # Append logs from the operation
        if isinstance(result, dict) and 'logs' in result:
            for log in result['logs']:
                deployment['logs'].append(log)
        
        success = isinstance(result, dict) and result.get('success', False)
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_log = f"[{timestamp}] File deployment {'SUCCESSFUL' if success else 'FAILED'}"
        deployment['logs'].append(status_log)
        save_deployment_history()

        return success

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] File deployment EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_sql_deployment_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute SQL deployment step using app.py's run_sql_deployment function"""
    from app import run_sql_deployment
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        sql_files = step.get('files', [])
        db_connection = step.get('dbConnection', 'app_db')
        db_user = step.get('dbUser', 'postgres')
        db_password_encoded = step.get('dbPassword', '')
        ft_source = step.get('ftNumber', ft_number)

        # Load db_inventory to get connection details
        try:
            with open('/app/inventory/db_inventory.json', 'r') as f:
                db_inventory = json.load(f)
        except Exception as e:
            timestamp = datetime.now().strftime('%H:%M:%S')
            deployment['logs'].append(f"[{timestamp}] ERROR loading db_inventory: {str(e)}")
            save_deployment_history()
            return False

        # Find database connection details
        db_info = None
        for db in db_inventory.get('db_connections', []):
            if db['db_connection'] == db_connection:
                db_info = db
                break

        if not db_info:
            timestamp = datetime.now().strftime('%H:%M:%S')
            deployment['logs'].append(f"[{timestamp}] Database connection {db_connection} not found in db_inventory")
            save_deployment_history()
            return False

        # Decode password
        try:
            db_password = base64.b64decode(db_password_encoded).decode('utf-8')
        except:
            db_password = db_password_encoded

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Starting SQL deployment: {', '.join(sql_files)} on {db_connection}"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")
        save_deployment_history()

        # Use app.py's run_sql_deployment function
        result = run_sql_deployment(
            sql_files,
            ft_source,
            db_info['hostname'],
            db_info['port'],
            db_info['db_name'],
            db_user,
            db_password,
            current_user
        )

        # Append logs from the operation
        if isinstance(result, dict) and 'logs' in result:
            for log in result['logs']:
                deployment['logs'].append(log)
        
        success = isinstance(result, dict) and result.get('success', False)
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_log = f"[{timestamp}] SQL deployment {'SUCCESSFUL' if success else 'FAILED'}"
        deployment['logs'].append(status_log)
        save_deployment_history()

        return success

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] SQL deployment EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_service_restart_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute systemd service operation step using app.py's run_systemd_operation function"""
    from app import run_systemd_operation
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        service = step.get('service', 'docker.service')
        operation = step.get('operation', 'restart')
        target_vms = step.get('targetVMs', ['batch1'])
        target_user = 'infadm'  # Use infadm for systemd operations

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Starting systemd operation: {operation} {service} on {', '.join(target_vms)}"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")
        save_deployment_history()

        # Use app.py's run_systemd_operation function
        result = run_systemd_operation(
            target_vms,
            service,
            operation,
            target_user,
            current_user
        )

        # Append logs from the operation
        if isinstance(result, dict) and 'logs' in result:
            for log in result['logs']:
                deployment['logs'].append(log)
        
        success = isinstance(result, dict) and result.get('success', False)
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_log = f"[{timestamp}] Systemd operation {'SUCCESSFUL' if success else 'FAILED'}"
        deployment['logs'].append(status_log)
        save_deployment_history()

        return success

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] Service restart EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_ansible_playbook_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute Ansible playbook step using inventory configuration"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        playbook_name = step.get('playbook', '')
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Loading inventory to find playbook: {playbook_name}"
        deployment['logs'].append(log_entry)
        save_deployment_history()
        
        # Load inventory to get playbook details
        try:
            with open('/app/inventory/inventory.json', 'r') as f:
                inventory = json.load(f)
        except Exception as e:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] ERROR loading inventory: {str(e)}"
            deployment['logs'].append(log_entry)
            save_deployment_history()
            return False
        
        playbook_info = None
        for pb in inventory.get('playbooks', []):
            if pb['name'] == playbook_name:
                playbook_info = pb
                break
        
        if not playbook_info:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Playbook {playbook_name} NOT FOUND in inventory"
            deployment['logs'].append(log_entry)
            save_deployment_history()
            return False

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Found playbook {playbook_name}, executing with ansible-playbook"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")
        save_deployment_history()

        # Build ansible-playbook command
        cmd = [
            'ansible-playbook',
            '-i', playbook_info['inventory'],
            playbook_info['path'],
            '--limit', 'batch1',
            '--user', 'infadm',
            '--forks', str(playbook_info.get('forks', 5))
        ]

        # Add extra vars files
        for extra_var in playbook_info.get('extra_vars', []):
            cmd.extend(['-e', f'@{extra_var}'])

        # Add vault password file if specified
        if playbook_info.get('vault_password_file'):
            cmd.extend(['--vault-password-file', playbook_info['vault_password_file']])

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Executing: {' '.join(cmd)}"
        deployment['logs'].append(log_entry)
        save_deployment_history()

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            for line in result.stdout.split('\n'):
                if line.strip():
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] ANSIBLE: {line}")

            if result.stderr:
                for line in result.stderr.split('\n'):
                    if line.strip():
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        deployment['logs'].append(f"[{timestamp}] ANSIBLE ERROR: {line}")

            success = result.returncode == 0
            timestamp = datetime.now().strftime('%H:%M:%S')
            status_log = f"[{timestamp}] Ansible playbook {playbook_name} {'SUCCESSFUL' if success else 'FAILED'}"
            deployment['logs'].append(status_log)
            save_deployment_history()

            return success

        except subprocess.TimeoutExpired:
            timestamp = datetime.now().strftime('%H:%M:%S')
            deployment['logs'].append(f"[{timestamp}] Ansible playbook TIMEOUT: {playbook_name}")
            save_deployment_history()
            return False

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] Ansible playbook EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_helm_upgrade_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute Helm upgrade step using inventory configuration"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        helm_deployment_type = step.get('helmDeploymentType', '')
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Loading inventory to find helm upgrade: {helm_deployment_type}"
        deployment['logs'].append(log_entry)
        save_deployment_history()
        
        # Load inventory to get helm command
        try:
            with open('/app/inventory/inventory.json', 'r') as f:
                inventory = json.load(f)
        except Exception as e:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] ERROR loading inventory: {str(e)}"
            deployment['logs'].append(log_entry)
            save_deployment_history()
            return False
        
        helm_command = None
        for upgrade in inventory.get('helm_upgrades', []):
            if upgrade['pod_name'] == helm_deployment_type:
                helm_command = upgrade['command']
                break
        
        if not helm_command:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Helm deployment type {helm_deployment_type} NOT FOUND in inventory"
            deployment['logs'].append(log_entry)
            save_deployment_history()
            return False

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Found helm command: {helm_command}, executing with ansible"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")
        save_deployment_history()

        cmd = [
            'ansible', 'batch1',
            '-i', '/app/inventory/inventory.json',
            '--user', 'admin',
            '-m', 'shell',
            '-a', helm_command
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            for line in result.stdout.split('\n'):
                if line.strip():
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] HELM: {line}")

            if result.stderr:
                for line in result.stderr.split('\n'):
                    if line.strip():
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        deployment['logs'].append(f"[{timestamp}] HELM ERROR: {line}")

            success = result.returncode == 0
            timestamp = datetime.now().strftime('%H:%M:%S')
            status_log = f"[{timestamp}] Helm upgrade {helm_deployment_type} {'SUCCESSFUL' if success else 'FAILED'}"
            deployment['logs'].append(status_log)
            save_deployment_history()

            return success

        except subprocess.TimeoutExpired:
            timestamp = datetime.now().strftime('%H:%M:%S')
            deployment['logs'].append(f"[{timestamp}] Helm upgrade TIMEOUT: {helm_deployment_type}")
            save_deployment_history()
            return False

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] Helm upgrade EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_template_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute a single template step"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        step_type = step.get('type')
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] === EXECUTING STEP {step.get('order')}: {step.get('description')} ==="
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")
        save_deployment_history()

        if step_type == 'file_deployment':
            return execute_file_deployment_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'sql_deployment':
            return execute_sql_deployment_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'service_restart':
            return execute_service_restart_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'ansible_playbook':
            return execute_ansible_playbook_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'helm_upgrade':
            return execute_helm_upgrade_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        else:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] ERROR: Unsupported step type: {step_type}"
            deployment['logs'].append(log_entry)
            save_deployment_history()
            return False

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] CRITICAL EXCEPTION in step {step.get('order')}: {str(e)}"
        deployment['logs'].append(log_entry)
        current_app.logger.exception(str(e))
        save_deployment_history()
        return False

def run_template_deployment(deployment_id, template, ft_number):
    """Execute template deployment by running steps in order"""
    from app import deployments, save_deployment_history
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        current_app.logger.error(f"Deployment {deployment_id} not found in deployments dictionary")
        return

    try:
        deployment['status'] = 'running'
        current_user = deployment.get('logged_in_user_info', {'username': 'unknown'})

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] ======= STARTING TEMPLATE DEPLOYMENT FOR {ft_number} ======="
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")

        steps = template.get('steps', [])
        total_steps = len(steps)
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Total steps to execute: {total_steps}"
        deployment['logs'].append(log_entry)
        save_deployment_history()

        # Execute steps in order
        for step in sorted(steps, key=lambda x: x.get('order', 0)):
            if deployment['status'] != 'running':
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Deployment status changed to {deployment['status']}, stopping execution"
                deployment['logs'].append(log_entry)
                break

            success = execute_template_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
            if not success:
                deployment['status'] = 'failed'
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] ======= TEMPLATE DEPLOYMENT FAILED AT STEP {step.get('order')}: {step.get('description')} ======="
                deployment['logs'].append(log_entry)
                save_deployment_history()
                return

            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] === STEP {step.get('order')} COMPLETED SUCCESSFULLY: {step.get('description')} ==="
            deployment['logs'].append(log_entry)
            save_deployment_history()

        deployment['status'] = 'success'
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] ======= TEMPLATE DEPLOYMENT COMPLETED SUCCESSFULLY ======="
        deployment['logs'].append(log_entry)
        save_deployment_history()

    except Exception as e:
        deployment['status'] = 'failed'
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] ======= CRITICAL ERROR IN TEMPLATE DEPLOYMENT: {str(e)} ======="
        deployment['logs'].append(log_entry)
        current_app.logger.exception(f"Template deployment error: {str(e)}")
        save_deployment_history()

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
    """Start template deployment"""
    from app import deployments, save_deployment_history
    
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Authentication required'}), 401

        data = request.get_json()
        ft_number = data.get('ft_number')
        template = data.get('template')

        if not ft_number or not template:
            return jsonify({'error': 'Missing ft_number or template'}), 400

        # Log the incoming request for debugging
        current_app.logger.info(f"Template deployment request received - FT: {ft_number}, User: {current_user['username']}")
        current_app.logger.info(f"Template metadata: {template.get('metadata', {})}")
        current_app.logger.info(f"Template steps: {len(template.get('steps', []))}")

        deployment_id = str(uuid.uuid4())
        current_timestamp = time.time()

        # Create template deployment entry that will appear in Deployment History
        deployments[deployment_id] = {
            'id': deployment_id,
            'type': 'template_deployment',
            'ft': ft_number,
            'status': 'running',
            'timestamp': current_timestamp,
            'logs': [],
            'orchestration_user': current_user['username'],
            'user_role': current_user.get('role', 'unknown'),
            'logged_in_user': current_user['username'],
            'logged_in_user_info': current_user,
            'template': template,
            'total_steps': len(template.get('steps', []))
        }

        save_deployment_history()
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
    """Get template deployment logs"""
    from app import deployments
    
    try:
        deployment = deployments.get(deployment_id)
        if not deployment:
            current_app.logger.warning(f"Deployment {deployment_id} not found. Available deployments: {list(deployments.keys())}")
            return jsonify({'error': 'Deployment not found'}), 404

        current_user = deployment.get('logged_in_user_info', {'username': 'unknown'})

        return jsonify({
            'logs': deployment['logs'],
            'status': deployment['status'],
            'ft_number': deployment.get('ft', ''),
            'started_at': datetime.fromtimestamp(deployment.get('timestamp', time.time())).isoformat(),
            'initiated_by': current_user['username'],
            'total_steps': deployment.get('total_steps', 0)
        })

    except Exception as e:
        current_app.logger.error(f"Error getting deployment logs: {str(e)}")
        return jsonify({'error': str(e)}), 500
