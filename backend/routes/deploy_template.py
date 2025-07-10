from flask import Blueprint, request, jsonify, current_app, session
import json
import os
import uuid
import threading
import time
from datetime import datetime
import subprocess
import logging
from routes.auth_routes import get_current_user
from app import app, deployments, save_deployment_history, deploy_file, systemd_operation


deploy_template_bp = Blueprint('deploy_template', __name__)

def log_message(deployment_id, message):
    if deployment_id in deployments:
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        deployments[deployment_id]['logs'].append(log_entry)
        current_app.logger.info(f"[{deployment_id}] {message}")

def execute_template_step(step, deployment_id, ft_number, current_user):
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False

    try:
        step_type = step.get('type')
        log_message(deployment_id, f"Executing step {step.get('order')}: {step.get('description')}")

        if step_type == 'file_deployment':
            files = step.get('files', [])
            target_vms = step.get('targetVMs', [])
            target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
            target_user = step.get('targetUser', 'abpwrk1')
            ft_source = step.get('ftNumber', ft_number)

            for file in files:
                for vm in target_vms:
                    with app.test_request_context(
                        '/api/deploy/file',
                        method='POST',
                        json={
                            'ft': ft_source,
                            'file': file,
                            'user': target_user,
                            'targetPath': target_path,
                            'vms': [vm],
                            'sudo': False,
                            'createBackup': True
                        }
                    ):
                        response = deploy_file()
                        if response.status_code != 200:
                            log_message(deployment_id, f"File deployment failed: {response.get_json()}")
                            return False

                        file_deploy_id = response.get_json().get('deploymentId')

                        timeout = 300
                        start_time = time.time()
                        while time.time() - start_time < timeout:
                            file_deploy = deployments.get(file_deploy_id)
                            if file_deploy and file_deploy['status'] in ['completed', 'failed']:
                                for log_entry in file_deploy['logs']:
                                    deployment['logs'].append(f"[FILE] {log_entry}")
                                del deployments[file_deploy_id]
                                return file_deploy['status'] == 'completed'
                            time.sleep(2)
                        log_message(deployment_id, f"File deployment timed out for file {file} on VM {vm}")
                        return False
            return True

        elif step_type == 'service_restart':
            service = step.get('service', 'docker.service')
            operation = step.get('operation', 'restart')
            target_vms = step.get('targetVMs', [])

            with app.test_request_context(
                f'/api/systemd/{operation}',
                method='POST',
                json={
                    'service': service,
                    'vms': target_vms,
                    'operation': operation
                }
            ):
                response = systemd_operation(operation)
                if response.status_code != 200:
                    log_message(deployment_id, f"Systemd operation failed: {response.get_json()}")
                    return False

                sys_deploy_id = response.get_json().get('deploymentId')

                timeout = 300
                start_time = time.time()
                while time.time() - start_time < timeout:
                    sys_deploy = deployments.get(sys_deploy_id)
                    if sys_deploy and sys_deploy['status'] in ['completed', 'failed']:
                        for log_entry in sys_deploy['logs']:
                            deployment['logs'].append(f"[SYSTEMD] {log_entry}")
                        del deployments[sys_deploy_id]
                        return sys_deploy['status'] == 'completed'
                    time.sleep(2)
                log_message(deployment_id, f"Systemd operation timed out after {timeout} seconds")
                return False

        else:
            log_message(deployment_id, f"Unsupported step type: {step_type}")
            return False

    except Exception as e:
        log_message(deployment_id, f"Exception in step {step.get('order')}: {str(e)}")
        current_app.logger.exception(str(e))
        return False

def run_template_deployment(deployment_id, template, ft_number):
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
        save_deployment_history()

    except Exception as e:
        deployment['status'] = 'failed'
        log_message(deployment_id, f"ERROR: {str(e)}")
        save_deployment_history()

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
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
            'template': template
        }

        save_deployment_history()

        current_app.logger.info(f"Template deployment initiated by {current_user['username']} with ID: {deployment_id}")

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
            'initiated_by': current_user['username']
        })

    except Exception as e:
        current_app.logger.error(f"Error getting deployment logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

