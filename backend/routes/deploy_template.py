
from flask import Blueprint, request, jsonify, current_app
import json
import os
import uuid
import threading
import time
from datetime import datetime
import subprocess
import logging
from routes.auth_routes import get_current_user

deploy_template_bp = Blueprint('deploy_template', __name__)

def execute_template_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute a single template step by calling the appropriate main app function"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        step_type = step.get('type')
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Executing step {step.get('order')}: {step.get('description')}"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")

        if step_type == 'file_deployment':
            # Import the actual function from main app
            from app import run_file_deployment
            
            files = step.get('files', [])
            target_vms = step.get('targetVMs', [])
            target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
            target_user = step.get('targetUser', 'abpwrk1')
            ft_source = step.get('ftNumber', ft_number)

            # Create individual deployments for each file to VM combination
            success = True
            for file in files:
                for vm in target_vms:
                    # Create a separate deployment entry for this file operation
                    file_deployment_id = str(uuid.uuid4())
                    current_timestamp = time.time()

                    file_deployment = {
                        'id': file_deployment_id,
                        'type': 'file',
                        'ft': ft_source,
                        'file': file,
                        'status': 'running',
                        'timestamp': current_timestamp,
                        'logs': [],
                        'orchestration_user': current_user['username'],
                        'user_role': current_user.get('role', 'unknown'),
                        'logged_in_user': current_user['username'],
                        'logged_in_user_info': current_user,
                        'vms': [vm],
                        'target_path': target_path,
                        'target_user': target_user
                    }

                    deployments[file_deployment_id] = file_deployment
                    
                    # Call the actual file deployment function from main app
                    result = run_file_deployment(file_deployment_id, ft_source, file, [vm], target_path, target_user, deployments, save_deployment_history)
                    
                    # Wait for completion and check status
                    timeout = 300
                    start_time = time.time()
                    while time.time() - start_time < timeout:
                        file_deploy = deployments.get(file_deployment_id)
                        if file_deploy and file_deploy['status'] in ['success', 'failed']:
                            # Copy logs to main deployment
                            for log in file_deploy.get('logs', []):
                                deployment['logs'].append(f"[FILE] {log}")
                            
                            if file_deploy['status'] == 'failed':
                                success = False
                            
                            # Clean up the temporary deployment
                            del deployments[file_deployment_id]
                            break
                        time.sleep(2)
                    else:
                        success = False
                        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] File deployment timeout for {file} to {vm}")

            save_deployment_history()
            return success

        elif step_type == 'sql_deployment':
            # Import the actual function from main app
            from app import run_sql_deployment
            
            sql_files = step.get('files', [])
            db_connection = step.get('dbConnection', 'default')
            db_user = step.get('dbUser', 'postgres')
            db_password = step.get('dbPassword', '')
            ft_source = step.get('ftNumber', ft_number)

            success = True
            for sql_file in sql_files:
                # Create a separate deployment entry for this SQL operation
                sql_deployment_id = str(uuid.uuid4())
                current_timestamp = time.time()

                sql_deployment = {
                    'id': sql_deployment_id,
                    'type': 'sql',
                    'ft': ft_source,
                    'file': sql_file,
                    'status': 'running',
                    'timestamp': current_timestamp,
                    'logs': [],
                    'orchestration_user': current_user['username'],
                    'user_role': current_user.get('role', 'unknown'),
                    'logged_in_user': current_user['username'],
                    'logged_in_user_info': current_user,
                    'db_connection': db_connection,
                    'db_user': db_user,
                    'db_password': db_password
                }

                deployments[sql_deployment_id] = sql_deployment
                
                # Call the actual SQL deployment function from main app
                result = run_sql_deployment(sql_deployment_id, ft_source, sql_file, db_connection, db_user, db_password, deployments, save_deployment_history)
                
                # Wait for completion and check status
                timeout = 300
                start_time = time.time()
                while time.time() - start_time < timeout:
                    sql_deploy = deployments.get(sql_deployment_id)
                    if sql_deploy and sql_deploy['status'] in ['success', 'failed']:
                        # Copy logs to main deployment
                        for log in sql_deploy.get('logs', []):
                            deployment['logs'].append(f"[SQL] {log}")
                        
                        if sql_deploy['status'] == 'failed':
                            success = False
                        
                        # Clean up the temporary deployment
                        del deployments[sql_deployment_id]
                        break
                    time.sleep(2)
                else:
                    success = False
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] SQL deployment timeout for {sql_file}")

            save_deployment_history()
            return success

        elif step_type == 'service_restart':
            # Import the actual function from main app
            from app import run_systemd_operation
            
            service = step.get('service', 'docker.service')
            operation = step.get('operation', 'restart')
            target_vms = step.get('targetVMs', ['batch1'])

            # Create a separate deployment entry for this systemd operation
            systemd_deployment_id = str(uuid.uuid4())
            current_timestamp = time.time()

            systemd_deployment = {
                'id': systemd_deployment_id,
                'type': 'systemd',
                'service': service,
                'operation': operation,
                'status': 'running',
                'timestamp': current_timestamp,
                'logs': [],
                'orchestration_user': current_user['username'],
                'user_role': current_user.get('role', 'unknown'),
                'logged_in_user': current_user['username'],
                'logged_in_user_info': current_user,
                'vms': target_vms
            }

            deployments[systemd_deployment_id] = systemd_deployment
            
            # Call the actual systemd operation function from main app
            result = run_systemd_operation(systemd_deployment_id, service, operation, target_vms, deployments, save_deployment_history)
            
            # Wait for completion and check status
            timeout = 300
            start_time = time.time()
            while time.time() - start_time < timeout:
                systemd_deploy = deployments.get(systemd_deployment_id)
                if systemd_deploy and systemd_deploy['status'] in ['success', 'failed']:
                    # Copy logs to main deployment
                    for log in systemd_deploy.get('logs', []):
                        deployment['logs'].append(f"[SYSTEMD] {log}")
                    
                    success = systemd_deploy['status'] == 'success'
                    
                    # Clean up the temporary deployment
                    del deployments[systemd_deployment_id]
                    save_deployment_history()
                    return success
                time.sleep(2)
            else:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Systemd operation timeout")
                save_deployment_history()
                return False

        elif step_type == 'ansible_playbook':
            playbook_name = step.get('playbook', '')
            
            # Load inventory to get playbook details
            try:
                with open('/app/inventory/inventory.json', 'r') as f:
                    inventory = json.load(f)
                
                playbook_info = None
                for pb in inventory.get('playbooks', []):
                    if pb['name'] == playbook_name:
                        playbook_info = pb
                        break
                
                if not playbook_info:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    log_entry = f"[{timestamp}] Playbook {playbook_name} not found in inventory"
                    deployment['logs'].append(log_entry)
                    return False

                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Running Ansible playbook: {playbook_name} on batch1 with infadm user"
                deployment['logs'].append(log_entry)

                # Build ansible-playbook command with all parameters from inventory
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

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                for line in result.stdout.split('\n'):
                    if line.strip():
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        log_entry = f"[{timestamp}] ANSIBLE: {line}"
                        deployment['logs'].append(log_entry)

                if result.stderr:
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            log_entry = f"[{timestamp}] ANSIBLE ERROR: {line}"
                            deployment['logs'].append(log_entry)

                return result.returncode == 0

            except Exception as e:
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Ansible Exception: {str(e)}"
                deployment['logs'].append(log_entry)
                return False

        elif step_type == 'helm_upgrade':
            helm_deployment_type = step.get('helmDeploymentType', '')
            
            # Load inventory to get helm command
            try:
                with open('/app/inventory/inventory.json', 'r') as f:
                    inventory = json.load(f)
                
                helm_command = None
                for upgrade in inventory.get('helm_upgrades', []):
                    if upgrade['pod_name'] == helm_deployment_type:
                        helm_command = upgrade['command']
                        break
                
                if not helm_command:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    log_entry = f"[{timestamp}] Helm deployment type {helm_deployment_type} not found in inventory"
                    deployment['logs'].append(log_entry)
                    return False

                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Running Helm upgrade: {helm_command} on batch1 with admin user"
                deployment['logs'].append(log_entry)

                cmd = [
                    'ansible', 'batch1',
                    '-i', '/app/inventory/inventory.json',
                    '--user', 'admin',
                    '-m', 'shell',
                    '-a', helm_command
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                for line in result.stdout.split('\n'):
                    if line.strip():
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        log_entry = f"[{timestamp}] HELM: {line}"
                        deployment['logs'].append(log_entry)

                if result.stderr:
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            log_entry = f"[{timestamp}] HELM ERROR: {line}"
                            deployment['logs'].append(log_entry)

                return result.returncode == 0

            except Exception as e:
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Helm Exception: {str(e)}"
                deployment['logs'].append(log_entry)
                return False

        else:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Unsupported step type: {step_type}"
            deployment['logs'].append(log_entry)
            return False

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Exception in step {step.get('order')}: {str(e)}"
        deployment['logs'].append(log_entry)
        current_app.logger.exception(str(e))
        return False

def run_template_deployment(deployment_id, template, ft_number):
    """Execute template deployment by running steps in order"""
    from app import deployments, save_deployment_history
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return

    try:
        deployment['status'] = 'running'
        current_user = deployment.get('logged_in_user_info', {'username': 'unknown'})

        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Starting template deployment for {ft_number}"
        deployment['logs'].append(log_entry)

        steps = template.get('steps', [])
        total_steps = len(steps)
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Total steps to execute: {total_steps}"
        deployment['logs'].append(log_entry)
        save_deployment_history()

        # Execute steps in order
        for step in sorted(steps, key=lambda x: x.get('order', 0)):
            if deployment['status'] != 'running':
                break

            success = execute_template_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
            if not success:
                deployment['status'] = 'failed'
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Template deployment failed at step {step.get('order')}: {step.get('description')}"
                deployment['logs'].append(log_entry)
                save_deployment_history()
                return

            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Step {step.get('order')} completed successfully: {step.get('description')}"
            deployment['logs'].append(log_entry)
            save_deployment_history()

        deployment['status'] = 'success'
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Template deployment completed successfully"
        deployment['logs'].append(log_entry)
        save_deployment_history()

    except Exception as e:
        deployment['status'] = 'failed'
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] ERROR: {str(e)}"
        deployment['logs'].append(log_entry)
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
