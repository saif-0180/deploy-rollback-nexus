
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
            files = step.get('files', [])
            target_vms = step.get('targetVMs', [])
            target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
            target_user = step.get('targetUser', 'abpwrk1')
            ft_source = step.get('ftNumber', ft_number)

            # Create file deployment using main app structure
            file_deployment_id = str(uuid.uuid4())
            current_timestamp = time.time()

            deployments[file_deployment_id] = {
                'id': file_deployment_id,
                'type': 'file_deployment',
                'ft': ft_source,
                'status': 'running',
                'timestamp': current_timestamp,
                'logs': [],
                'orchestration_user': current_user['username'],
                'user_role': current_user.get('role', 'unknown'),
                'logged_in_user': current_user['username'],
                'logged_in_user_info': current_user,
                'files': files,
                'target_vms': target_vms,
                'target_path': target_path,
                'target_user': target_user
            }

            # Execute file deployment
            def run_file_deployment():
                file_deployment = deployments.get(file_deployment_id)
                if not file_deployment:
                    return

                try:
                    file_deployment['status'] = 'running'
                    
                    for file in files:
                        for vm in target_vms:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            log_entry = f"[{timestamp}] Deploying {file} to {vm}:{target_path}"
                            file_deployment['logs'].append(log_entry)
                            deployment['logs'].append(f"[FILE] {log_entry}")

                            # Create Ansible playbook for file deployment
                            playbook_content = f"""---
- hosts: {vm}
  become: true
  vars:
    ft_number: "{ft_source}"
    target_file: "{file}"
    target_path: "{target_path}"
    target_user: "{target_user}"
  tasks:
    - name: Create backup directory
      file:
        path: "/home/{{{{ target_user }}}}/backups/{{{{ ft_number }}}}"
        state: directory
        owner: "{{{{ target_user }}}}"
        group: "{{{{ target_user }}}}"
        mode: '0755'

    - name: Backup existing file if it exists
      copy:
        src: "{{{{ target_path }}}}/{{{{ target_file }}}}"
        dest: "/home/{{{{ target_user }}}}/backups/{{{{ ft_number }}}}/{{{{ target_file }}}}.{{{{ ansible_date_time.epoch }}}}"
        remote_src: yes
      ignore_errors: yes

    - name: Deploy file
      copy:
        src: "/home/{{{{ target_user }}}}/ft/{{{{ ft_number }}}}/{{{{ target_file }}}}"
        dest: "{{{{ target_path }}}}/{{{{ target_file }}}}"
        owner: "{{{{ target_user }}}}"
        group: "{{{{ target_user }}}}"
        mode: '0644'
        backup: yes
"""

                            playbook_file = f"/tmp/deploy_{file_deployment_id}_{vm}_{file}.yml"
                            try:
                                with open(playbook_file, 'w') as f:
                                    f.write(playbook_content)

                                cmd = [
                                    'ansible-playbook', 
                                    '-i', '/app/inventory/inventory.json',
                                    playbook_file,
                                    '--limit', vm
                                ]

                                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                                
                                for line in result.stdout.split('\n'):
                                    if line.strip():
                                        timestamp = datetime.now().strftime('%H:%M:%S')
                                        log_entry = f"[{timestamp}] {line}"
                                        file_deployment['logs'].append(log_entry)
                                        deployment['logs'].append(f"[FILE] {log_entry}")

                                if result.stderr:
                                    for line in result.stderr.split('\n'):
                                        if line.strip():
                                            timestamp = datetime.now().strftime('%H:%M:%S')
                                            log_entry = f"[{timestamp}] ERROR: {line}"
                                            file_deployment['logs'].append(log_entry)
                                            deployment['logs'].append(f"[FILE] {log_entry}")

                                os.remove(playbook_file)

                                if result.returncode != 0:
                                    file_deployment['status'] = 'failed'
                                    deployment['status'] = 'failed'
                                    save_deployment_history()
                                    return

                            except Exception as e:
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                log_entry = f"[{timestamp}] Exception: {str(e)}"
                                file_deployment['logs'].append(log_entry)
                                deployment['logs'].append(f"[FILE] {log_entry}")
                                file_deployment['status'] = 'failed'
                                deployment['status'] = 'failed'
                                save_deployment_history()
                                return

                    file_deployment['status'] = 'completed'
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    log_entry = f"[{timestamp}] File deployment completed successfully"
                    file_deployment['logs'].append(log_entry)
                    deployment['logs'].append(f"[FILE] {log_entry}")
                    save_deployment_history()

                except Exception as e:
                    file_deployment['status'] = 'failed'
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    log_entry = f"[{timestamp}] ERROR: {str(e)}"
                    file_deployment['logs'].append(log_entry)
                    deployment['logs'].append(f"[FILE] {log_entry}")
                    save_deployment_history()

            file_thread = threading.Thread(target=run_file_deployment)
            file_thread.daemon = True
            file_thread.start()

            # Wait for file deployment to complete
            timeout = 300
            start_time = time.time()
            while time.time() - start_time < timeout:
                file_deploy = deployments.get(file_deployment_id)
                if file_deploy and file_deploy['status'] in ['completed', 'failed']:
                    success = file_deploy['status'] == 'completed'
                    del deployments[file_deployment_id]
                    return success
                time.sleep(2)

            return False

        elif step_type == 'service_restart':
            service = step.get('service', 'docker.service')
            operation = step.get('operation', 'restart')
            target_vms = step.get('targetVMs', [])

            # Create systemd deployment using main app structure
            systemd_deployment_id = str(uuid.uuid4())
            current_timestamp = time.time()

            deployments[systemd_deployment_id] = {
                'id': systemd_deployment_id,
                'type': 'systemd_operation',
                'service': service,
                'operation': operation,
                'status': 'running',
                'timestamp': current_timestamp,
                'logs': [],
                'orchestration_user': current_user['username'],
                'user_role': current_user.get('role', 'unknown'),
                'logged_in_user': current_user['username'],
                'logged_in_user_info': current_user,
                'target_vms': target_vms
            }

            def run_systemd_operation():
                systemd_deployment = deployments.get(systemd_deployment_id)
                if not systemd_deployment:
                    return

                try:
                    systemd_deployment['status'] = 'running'
                    
                    for vm in target_vms:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        log_entry = f"[{timestamp}] Executing {operation} on {service} for {vm}"
                        systemd_deployment['logs'].append(log_entry)
                        deployment['logs'].append(f"[SYSTEMD] {log_entry}")

                        playbook_content = f"""---
- hosts: {vm}
  become: true
  tasks:
    - name: {operation.capitalize()} {service}
      systemd:
        name: {service}
        state: {"restarted" if operation == "restart" else "started" if operation == "start" else "stopped"}
      register: systemd_result

    - name: Show service status
      systemd:
        name: {service}
      register: service_status

    - name: Display results
      debug:
        msg: "Service {{{{ service_status.status.ActiveState }}}} - {{{{ service_status.status.SubState }}}}"
"""

                        playbook_file = f"/tmp/systemd_{systemd_deployment_id}_{vm}.yml"
                        try:
                            with open(playbook_file, 'w') as f:
                                f.write(playbook_content)

                            cmd = [
                                'ansible-playbook', 
                                '-i', '/app/inventory/inventory.json',
                                playbook_file,
                                '--limit', vm
                            ]

                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                            
                            for line in result.stdout.split('\n'):
                                if line.strip():
                                    timestamp = datetime.now().strftime('%H:%M:%S')
                                    log_entry = f"[{timestamp}] {line}"
                                    systemd_deployment['logs'].append(log_entry)
                                    deployment['logs'].append(f"[SYSTEMD] {log_entry}")

                            if result.stderr:
                                for line in result.stderr.split('\n'):
                                    if line.strip():
                                        timestamp = datetime.now().strftime('%H:%M:%S')
                                        log_entry = f"[{timestamp}] ERROR: {line}"
                                        systemd_deployment['logs'].append(log_entry)
                                        deployment['logs'].append(f"[SYSTEMD] {log_entry}")

                            os.remove(playbook_file)

                            if result.returncode != 0:
                                systemd_deployment['status'] = 'failed'
                                deployment['status'] = 'failed'
                                save_deployment_history()
                                return

                        except Exception as e:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            log_entry = f"[{timestamp}] Exception: {str(e)}"
                            systemd_deployment['logs'].append(log_entry)
                            deployment['logs'].append(f"[SYSTEMD] {log_entry}")
                            systemd_deployment['status'] = 'failed'
                            deployment['status'] = 'failed'
                            save_deployment_history()
                            return

                    systemd_deployment['status'] = 'completed'
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    log_entry = f"[{timestamp}] Systemd operation completed successfully"
                    systemd_deployment['logs'].append(log_entry)
                    deployment['logs'].append(f"[SYSTEMD] {log_entry}")
                    save_deployment_history()

                except Exception as e:
                    systemd_deployment['status'] = 'failed'
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    log_entry = f"[{timestamp}] ERROR: {str(e)}"
                    systemd_deployment['logs'].append(log_entry)
                    deployment['logs'].append(f"[SYSTEMD] {log_entry}")
                    save_deployment_history()

            systemd_thread = threading.Thread(target=run_systemd_operation)
            systemd_thread.daemon = True
            systemd_thread.start()

            # Wait for systemd operation to complete
            timeout = 300
            start_time = time.time()
            while time.time() - start_time < timeout:
                systemd_deploy = deployments.get(systemd_deployment_id)
                if systemd_deploy and systemd_deploy['status'] in ['completed', 'failed']:
                    success = systemd_deploy['status'] == 'completed'
                    del deployments[systemd_deployment_id]
                    return success
                time.sleep(2)

            return False

        elif step_type == 'sql_deployment':
            sql_files = step.get('sqlFiles', [])
            database = step.get('database', 'default')

            for sql_file in sql_files:
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Executing SQL file: {sql_file} on database: {database}"
                deployment['logs'].append(log_entry)

                try:
                    cmd = ['psql', '-h', 'localhost', '-U', 'postgres', '-d', database, '-f', f'/app/sql/{sql_file}']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            log_entry = f"[{timestamp}] SQL: {line}"
                            deployment['logs'].append(log_entry)

                    if result.stderr:
                        for line in result.stderr.split('\n'):
                            if line.strip():
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                log_entry = f"[{timestamp}] SQL ERROR: {line}"
                                deployment['logs'].append(log_entry)

                    if result.returncode != 0:
                        return False

                except Exception as e:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    log_entry = f"[{timestamp}] SQL Exception: {str(e)}"
                    deployment['logs'].append(log_entry)
                    return False

            return True

        elif step_type == 'ansible_playbook':
            playbook_file = step.get('playbookFile', '')
            target_vms = step.get('targetVMs', ['batch1'])

            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Running Ansible playbook: {playbook_file} on {target_vms} with infadm user"
            deployment['logs'].append(log_entry)

            try:
                for vm in target_vms:
                    cmd = [
                        'ansible-playbook', 
                        '-i', '/app/inventory/inventory.json',
                        f'/app/playbooks/{playbook_file}',
                        '--limit', vm,
                        '--user', 'infadm'
                    ]

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

                    if result.returncode != 0:
                        return False

                return True

            except Exception as e:
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Ansible Exception: {str(e)}"
                deployment['logs'].append(log_entry)
                return False

        elif step_type == 'helm_upgrade':
            chart_name = step.get('chartName', '')
            release_name = step.get('releaseName', '')
            namespace = step.get('namespace', 'default')

            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = f"[{timestamp}] Running Helm upgrade: {release_name} with chart {chart_name} on batch1 with admin user"
            deployment['logs'].append(log_entry)

            try:
                cmd = [
                    'ansible', 'batch1',
                    '-i', '/app/inventory/inventory.json',
                    '--user', 'admin',
                    '-m', 'shell',
                    '-a', f'helm upgrade {release_name} {chart_name} --namespace {namespace}'
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

        for step in sorted(steps, key=lambda x: x.get('order', 0)):
            if deployment['status'] != 'running':
                break

            success = execute_template_step(step, deployment_id, ft_number, current_user, deployments, save_deployment_history)
            if not success:
                deployment['status'] = 'failed'
                timestamp = datetime.now().strftime('%H:%M:%S')
                log_entry = f"[{timestamp}] Template deployment failed at step {step.get('order')}"
                deployment['logs'].append(log_entry)
                save_deployment_history()
                return

        deployment['status'] = 'completed'
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
            'initiated_by': current_user['username']
        })

    except Exception as e:
        current_app.logger.error(f"Error getting deployment logs: {str(e)}")
        return jsonify({'error': str(e)}), 500
