
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

def execute_file_deployment_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute file deployment with backup creation"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        files = step.get('files', [])
        target_vms = step.get('targetVMs', [])
        target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
        target_user = step.get('targetUser', 'abpwrk1')
        ft_source = step.get('ftNumber', ft_number)

        success = True
        for file in files:
            for vm in target_vms:
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Starting file deployment: {file} to {vm}:{target_path}"
                deployment['logs'].append(log_entry)
                current_app.logger.info(f"[{deployment_id}] {log_entry}")

                # Create backup first
                backup_cmd = [
                    'ansible', vm,
                    '-i', '/app/inventory/inventory.json',
                    '--user', target_user,
                    '-m', 'shell',
                    '-a', f'if [ -f {target_path}/{file} ]; then cp {target_path}/{file} {target_path}/{file}.bak.$(date +%Y%m%d_%H%M%S); echo "Backup created for {file}"; else echo "No existing file {file} to backup"; fi'
                ]

                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Creating backup of existing file {file} on {vm}"
                deployment['logs'].append(log_entry)
                
                try:
                    backup_result = subprocess.run(backup_cmd, capture_output=True, text=True, timeout=60)
                    for line in backup_result.stdout.split('\n'):
                        if line.strip():
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            deployment['logs'].append(f"[{timestamp}] BACKUP: {line}")
                    
                    if backup_result.stderr:
                        for line in backup_result.stderr.split('\n'):
                            if line.strip():
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                deployment['logs'].append(f"[{timestamp}] BACKUP WARN: {line}")
                except Exception as e:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] BACKUP ERROR: {str(e)}")

                # Copy file
                copy_cmd = [
                    'ansible', vm,
                    '-i', '/app/inventory/inventory.json',
                    '--user', target_user,
                    '-m', 'copy',
                    '-a', f'src=/app/fixfiles/AllFts/{ft_source}/{file} dest={target_path}/{file} backup=yes'
                ]

                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Copying {file} from /app/fixfiles/AllFts/{ft_source}/ to {vm}:{target_path}"
                deployment['logs'].append(log_entry)

                try:
                    copy_result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=300)
                    
                    for line in copy_result.stdout.split('\n'):
                        if line.strip():
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            deployment['logs'].append(f"[{timestamp}] COPY: {line}")
                    
                    if copy_result.stderr:
                        for line in copy_result.stderr.split('\n'):
                            if line.strip():
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                deployment['logs'].append(f"[{timestamp}] COPY ERROR: {line}")
                    
                    if copy_result.returncode != 0:
                        success = False
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        deployment['logs'].append(f"[{timestamp}] File copy FAILED for {file} to {vm} - Return code: {copy_result.returncode}")
                    else:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        deployment['logs'].append(f"[{timestamp}] Successfully copied {file} to {vm}:{target_path}")

                except subprocess.TimeoutExpired:
                    success = False
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] File copy TIMEOUT for {file} to {vm}")
                except Exception as e:
                    success = False
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] File copy EXCEPTION: {str(e)}")

        save_deployment_history()
        return success

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] File deployment EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_sql_deployment_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute SQL deployment"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        sql_files = step.get('files', [])
        db_connection = step.get('dbConnection', 'default')
        db_user = step.get('dbUser', 'postgres')
        db_password_encoded = step.get('dbPassword', '')
        ft_source = step.get('ftNumber', ft_number)

        # Decode password
        try:
            db_password = base64.b64decode(db_password_encoded).decode('utf-8')
        except:
            db_password = db_password_encoded

        success = True
        for sql_file in sql_files:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Starting SQL deployment: {sql_file} on {db_connection}"
            deployment['logs'].append(log_entry)
            current_app.logger.info(f"[{deployment_id}] {log_entry}")

            sql_cmd = [
                'ansible', 'batch1',
                '-i', '/app/inventory/inventory.json',
                '--user', 'infadm',
                '-m', 'shell',
                '-a', f'cd /app/fixfiles/AllFts/{ft_source} && PGPASSWORD="{db_password}" psql -h localhost -U {db_user} -d {db_connection} -f {sql_file}'
            ]

            try:
                sql_result = subprocess.run(sql_cmd, capture_output=True, text=True, timeout=300)
                
                for line in sql_result.stdout.split('\n'):
                    if line.strip():
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        deployment['logs'].append(f"[{timestamp}] SQL: {line}")
                
                if sql_result.stderr:
                    for line in sql_result.stderr.split('\n'):
                        if line.strip():
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            deployment['logs'].append(f"[{timestamp}] SQL ERROR: {line}")
                
                if sql_result.returncode != 0:
                    success = False
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] SQL execution FAILED for {sql_file} - Return code: {sql_result.returncode}")
                else:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] Successfully executed SQL file {sql_file}")

            except subprocess.TimeoutExpired:
                success = False
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] SQL execution TIMEOUT for {sql_file}")
            except Exception as e:
                success = False
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] SQL execution EXCEPTION: {str(e)}")

        save_deployment_history()
        return success

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] SQL deployment EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_service_restart_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute systemd service operation"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        service = step.get('service', 'docker.service')
        operation = step.get('operation', 'restart')
        target_vms = step.get('targetVMs', ['batch1'])

        success = True
        for vm in target_vms:
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Starting systemd operation: {operation} {service} on {vm}"
            deployment['logs'].append(log_entry)
            current_app.logger.info(f"[{deployment_id}] {log_entry}")

            if operation == 'status':
                systemd_cmd = [
                    'ansible', vm,
                    '-i', '/app/inventory/inventory.json',
                    '--user', 'infadm',
                    '--become',
                    '-m', 'shell',
                    '-a', f'systemctl status {service}'
                ]
            else:
                systemd_cmd = [
                    'ansible', vm,
                    '-i', '/app/inventory/inventory.json',
                    '--user', 'infadm',
                    '--become',
                    '-m', 'systemd',
                    '-a', f'name={service} state={"started" if operation == "start" else "stopped" if operation == "stop" else "restarted"}'
                ]

            try:
                systemd_result = subprocess.run(systemd_cmd, capture_output=True, text=True, timeout=120)
                
                for line in systemd_result.stdout.split('\n'):
                    if line.strip():
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        deployment['logs'].append(f"[{timestamp}] SYSTEMD: {line}")
                
                if systemd_result.stderr:
                    for line in systemd_result.stderr.split('\n'):
                        if line.strip():
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            deployment['logs'].append(f"[{timestamp}] SYSTEMD ERROR: {line}")
                
                if systemd_result.returncode != 0 and operation != 'status':
                    success = False
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] Systemd operation FAILED: {operation} {service} on {vm} - Return code: {systemd_result.returncode}")
                else:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    deployment['logs'].append(f"[{timestamp}] Successfully executed {operation} on {service} at {vm}")

            except subprocess.TimeoutExpired:
                success = False
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] Systemd operation TIMEOUT: {operation} {service} on {vm}")
            except Exception as e:
                success = False
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] Systemd operation EXCEPTION: {str(e)}")

        save_deployment_history()
        return success

    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        deployment['logs'].append(f"[{timestamp}] Service restart EXCEPTION: {str(e)}")
        save_deployment_history()
        return False

def execute_ansible_playbook_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute Ansible playbook"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        playbook_name = step.get('playbook', '')
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Loading inventory to find playbook: {playbook_name}"
        deployment['logs'].append(log_entry)
        
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
        log_entry = f"[{timestamp}] Found playbook {playbook_name}, executing on batch1 with infadm user"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")

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
        log_entry = f"[{timestamp}] Executing command: {' '.join(cmd)}"
        deployment['logs'].append(log_entry)

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
            if success:
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] Ansible playbook {playbook_name} completed SUCCESSFULLY")
            else:
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] Ansible playbook {playbook_name} FAILED - Return code: {result.returncode}")

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

def execute_helm_upgrade_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history):
    """Execute Helm upgrade"""
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        helm_deployment_type = step.get('helmDeploymentType', '')
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Loading inventory to find helm upgrade: {helm_deployment_type}"
        deployment['logs'].append(log_entry)
        
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
        log_entry = f"[{timestamp}] Found helm command: {helm_command}, executing on batch1 with admin user"
        deployment['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {log_entry}")

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
            if success:
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] Helm upgrade {helm_deployment_type} completed SUCCESSFULLY")
            else:
                timestamp = datetime.now().strftime('%H:%M:%S')
                deployment['logs'].append(f"[{timestamp}] Helm upgrade {helm_deployment_type} FAILED - Return code: {result.returncode}")

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
            return execute_file_deployment_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'sql_deployment':
            return execute_sql_deployment_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'service_restart':
            return execute_service_restart_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'ansible_playbook':
            return execute_ansible_playbook_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
        elif step_type == 'helm_upgrade':
            return execute_helm_upgrade_fresh(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
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
        
        # Log the template structure for debugging
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] Template metadata: {template.get('metadata', {})}"
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
        current_app.logger.info(f"Template content: {json.dumps(template, indent=2)}")

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
        current_app.logger.info(f"Deployment added to deployments dictionary. Current deployments count: {len(deployments)}")

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
