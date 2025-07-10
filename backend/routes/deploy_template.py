
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
import hashlib

deploy_template_bp = Blueprint('deploy_template', __name__)

def get_current_user():
    """Get current authenticated user from session"""
    return session.get('user')

def log_message(deployment_id, message):
    """Add a log message to the deployment"""
    # Import here to avoid circular imports
    from app import deployments
    
    if deployment_id in deployments:
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        deployments[deployment_id]['logs'].append(log_entry)
        
        # Also log to application logger for debugging
        current_app.logger.info(f"[{deployment_id}] {message}")

def execute_file_deployment_step(step, deployment_id, ft_number, current_user):
    """Execute file deployment step with real Ansible execution"""
    # Import here to avoid circular imports
    from app import deployments
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        files = step.get('files', [])
        target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
        target_user = step.get('targetUser', 'abpwrk1')
        target_vms = step.get('targetVMs', [])
        ft_source = step.get('ftNumber', ft_number)
        
        log_message(deployment_id, f"Starting file deployment for FT {ft_source}")
        log_message(deployment_id, f"Files: {', '.join(files)}")
        log_message(deployment_id, f"Target VMs: {', '.join(target_vms)}")
        log_message(deployment_id, f"Target user: {target_user}")
        log_message(deployment_id, f"Target path: {target_path}")
        
        # Generate Ansible playbook for file deployment
        playbook_file = f"/tmp/file_deploy_{deployment_id}.yml"
        inventory_file = f"/tmp/inventory_{deployment_id}"
        
        # Load inventory to get VM details
        inventory_path = '/app/inventory/inventory.json'
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        # Create inventory file
        with open(inventory_file, 'w') as f:
            f.write("[file_targets]\n")
            for vm_name in target_vms:
                vm = next((v for v in inventory["vms"] if v["name"] == vm_name), None)
                if vm:
                    f.write(f"{vm_name} ansible_host={vm['ip']} ansible_user=infadm ansible_ssh_private_key_file=/home/users/infadm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'\n")
        
        # Create Ansible playbook
        with open(playbook_file, 'w') as f:
            f.write(f"""---
- name: Deploy files for FT {ft_source} (by {current_user['username']})
  hosts: file_targets
  gather_facts: true
  become: true
  vars:
    target_path: "{target_path}"
    target_user: "{target_user}"
    ft_source: "{ft_source}"
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      register: ping_result
      
    - name: Log connection test
      ansible.builtin.debug:
        msg: "Connection successful to {{{{ inventory_hostname }}}}"
        
    - name: Ensure target directory exists
      ansible.builtin.file:
        path: "{{{{ target_path }}}}"
        state: directory
        owner: "{{{{ target_user }}}}"
        group: aimsys
        mode: '0755'
""")
            
            for file in files:
                source_file = os.path.join('/app/fixfiles', 'AllFts', ft_source, file)
                f.write(f"""
    - name: Copy {file} to target
      ansible.builtin.copy:
        src: "{source_file}"
        dest: "{{{{ target_path }}}}/{file}"
        owner: "{{{{ target_user }}}}"
        group: aimsys
        mode: '0644'
        backup: yes
      register: copy_result_{file.replace('.', '_').replace('-', '_')}
      
    - name: Log copy result for {file}
      ansible.builtin.debug:
        msg: "File {file} copied successfully"
""")
        
        # Execute Ansible playbook
        return execute_ansible_playbook_file(playbook_file, inventory_file, deployment_id)
        
    except Exception as e:
        log_message(deployment_id, f"ERROR in file deployment: {str(e)}")
        return False

def execute_sql_deployment_step(step, deployment_id, ft_number, current_user):
    """Execute SQL deployment step"""
    # Import here to avoid circular imports
    from app import deployments
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        files = step.get('files', [])
        db_connection = step.get('dbConnection')
        db_user = step.get('dbUser')
        db_password_encoded = step.get('dbPassword', '')
        ft_source = step.get('ftNumber', ft_number)
        
        log_message(deployment_id, f"Starting SQL deployment for FT {ft_source}")
        log_message(deployment_id, f"Database connection: {db_connection}")
        log_message(deployment_id, f"Database user: {db_user}")
        log_message(deployment_id, f"SQL files: {', '.join(files)}")
        
        # Load db_inventory to get connection details
        db_inventory_path = '/app/inventory/db_inventory.json'
        with open(db_inventory_path, 'r') as f:
            db_inventory = json.load(f)
        
        connection_details = next(
            (conn for conn in db_inventory.get('db_connections', []) 
             if conn['db_connection'] == db_connection), None
        )
        
        if not connection_details:
            log_message(deployment_id, f"ERROR: DB connection '{db_connection}' not found")
            return False
        
        hostname = connection_details['hostname']
        port = connection_details['port']
        db_name = connection_details['db_name']
        db_password = base64.b64decode(db_password_encoded).decode('utf-8') if db_password_encoded else ''
        
        log_message(deployment_id, f"Connecting to database: {hostname}:{port}/{db_name}")
        
        # Generate Ansible playbook for SQL execution
        playbook_file = f"/tmp/sql_deploy_{deployment_id}.yml"
        inventory_file = f"/tmp/inventory_{deployment_id}"
        
        # Create localhost inventory for SQL execution
        with open(inventory_file, 'w') as f:
            f.write("[sql_targets]\n")
            f.write("localhost ansible_connection=local\n")
        
        # Create Ansible playbook
        with open(playbook_file, 'w') as f:
            f.write(f"""---
- name: Execute SQL files for FT {ft_source} (by {current_user['username']})
  hosts: sql_targets
  gather_facts: false
  vars:
    db_hostname: "{hostname}"
    db_port: "{port}"
    db_name: "{db_name}"
    db_user: "{db_user}"
    db_password: "{db_password}"
    ft_source: "{ft_source}"
  tasks:
    - name: Test database connection
      ansible.builtin.shell: |
        export PGPASSWORD="{{{{ db_password }}}}"
        psql -h "{{{{ db_hostname }}}}" -p "{{{{ db_port }}}}" -d "{{{{ db_name }}}}" -U "{{{{ db_user }}}}" -c "SELECT version();"
      register: db_test
      environment:
        PGPASSWORD: "{{{{ db_password }}}}"
        
    - name: Log database connection test
      ansible.builtin.debug:
        msg: "Database connection successful"
""")
            
            for sql_file in files:
                source_file = os.path.join('/app/fixfiles', 'AllFts', ft_source, sql_file)
                f.write(f"""
    - name: Execute SQL file {sql_file}
      ansible.builtin.shell: |
        export PGPASSWORD="{{{{ db_password }}}}"
        psql -h "{{{{ db_hostname }}}}" -p "{{{{ db_port }}}}" -d "{{{{ db_name }}}}" -U "{{{{ db_user }}}}" -f "{source_file}"
      register: sql_result_{sql_file.replace('.', '_').replace('-', '_')}
      environment:
        PGPASSWORD: "{{{{ db_password }}}}"
        
    - name: Log SQL execution result for {sql_file}
      ansible.builtin.debug:
        msg: "SQL file {sql_file} executed successfully"
      when: sql_result_{sql_file.replace('.', '_').replace('-', '_')}.rc == 0
""")
        
        # Execute Ansible playbook
        return execute_ansible_playbook_file(playbook_file, inventory_file, deployment_id)
        
    except Exception as e:
        log_message(deployment_id, f"ERROR in SQL deployment: {str(e)}")
        return False

def execute_service_restart_step(step, deployment_id, current_user):
    """Execute service restart step"""
    # Import here to avoid circular imports
    from app import deployments
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        service = step.get('service', 'docker.service')
        operation = step.get('operation', 'restart')
        target_vms = step.get('targetVMs', [])
        
        log_message(deployment_id, f"Starting service {operation} for {service}")
        log_message(deployment_id, f"Target VMs: {', '.join(target_vms)}")
        
        # Generate Ansible playbook
        playbook_file = f"/tmp/service_{deployment_id}.yml"
        inventory_file = f"/tmp/inventory_{deployment_id}"
        
        # Load inventory to get VM details
        inventory_path = '/app/inventory/inventory.json'
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        # Create inventory file
        with open(inventory_file, 'w') as f:
            f.write("[service_targets]\n")
            for vm_name in target_vms:
                vm = next((v for v in inventory["vms"] if v["name"] == vm_name), None)
                if vm:
                    f.write(f"{vm_name} ansible_host={vm['ip']} ansible_user=infadm ansible_ssh_private_key_file=/home/users/infadm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'\n")
        
        # Create Ansible playbook
        with open(playbook_file, 'w') as f:
            f.write(f"""---
- name: Service {operation} operation (by {current_user['username']})
  hosts: service_targets
  gather_facts: false
  become: true
  vars:
    service_name: "{service}"
    service_operation: "{operation}"
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      
    - name: Get service status before operation
      ansible.builtin.systemd:
        name: "{{{{ service_name }}}}"
      register: service_status_before
      
    - name: Log service status before operation
      ansible.builtin.debug:
        msg: "Service {{{{ service_name }}}} status: {{{{ service_status_before.status.ActiveState | default('unknown') }}}}"
        
    - name: Execute service {operation}
      ansible.builtin.systemd:
        name: "{{{{ service_name }}}}"
        state: "{{{{ 'started' if service_operation == 'start' else 'stopped' if service_operation == 'stop' else 'restarted' if service_operation == 'restart' else service_operation }}}}"
      register: service_result
      when: service_operation in ['start', 'stop', 'restart']
      
    - name: Get service status after operation
      ansible.builtin.systemd:
        name: "{{{{ service_name }}}}"
      register: service_status_after
      
    - name: Log service operation result
      ansible.builtin.debug:
        msg: "Service {{{{ service_name }}}} {{{{ service_operation }}}} completed. Status: {{{{ service_status_after.status.ActiveState | default('unknown') }}}}"
""")
        
        # Execute Ansible playbook
        return execute_ansible_playbook_file(playbook_file, inventory_file, deployment_id)
        
    except Exception as e:
        log_message(deployment_id, f"ERROR in service operation: {str(e)}")
        return False

def execute_ansible_playbook_step(step, deployment_id, current_user):
    """Execute Ansible playbook step"""
    # Import here to avoid circular imports
    from app import deployments
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        playbook_name = step.get('playbook')
        
        log_message(deployment_id, f"Starting Ansible playbook: {playbook_name}")
        
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
        
        log_message(deployment_id, f"Executing playbook: {playbook_path}")
        log_message(deployment_id, f"Using inventory: {inventory_file}")
        
        # Build command
        cmd = ["ansible-playbook", playbook_path, "-i", inventory_file, "-f", "10"]
        
        # Add extra variables
        for var in extra_vars:
            cmd.extend(["-e", var])
        
        cmd.extend(["-vvv"])  # Verbose output
        
        log_message(deployment_id, f"Command: {' '.join(cmd)}")
        
        # Execute command and capture real-time output
        return execute_command_with_live_output(cmd, deployment_id)
        
    except Exception as e:
        log_message(deployment_id, f"ERROR in Ansible playbook execution: {str(e)}")
        return False

def execute_helm_upgrade_step(step, deployment_id, current_user):
    """Execute Helm upgrade step"""
    # Import here to avoid circular imports
    from app import deployments
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        pod_name = step.get('pod')
        
        log_message(deployment_id, f"Starting Helm upgrade for pod: {pod_name}")
        
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
        log_message(deployment_id, f"Executing: {command}")
        
        # Execute command
        cmd = ["bash", "-c", command]
        return execute_command_with_live_output(cmd, deployment_id)
        
    except Exception as e:
        log_message(deployment_id, f"ERROR in Helm upgrade: {str(e)}")
        return False

def execute_command_with_live_output(cmd, deployment_id):
    """Execute a command and capture live output"""
    try:
        # Set up environment
        env_vars = os.environ.copy()
        
        # Use Popen for real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env_vars,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Clean up the output and log it
                clean_output = output.strip()
                if clean_output:  # Only log non-empty lines
                    log_message(deployment_id, clean_output)
        
        rc = process.poll()
        
        if rc == 0:
            log_message(deployment_id, "Command executed successfully")
            return True
        else:
            log_message(deployment_id, f"Command failed with return code: {rc}")
            return False
            
    except Exception as e:
        log_message(deployment_id, f"ERROR executing command: {str(e)}")
        return False

def execute_ansible_playbook_file(playbook_file, inventory_file, deployment_id):
    """Execute an Ansible playbook file and capture detailed output"""
    try:
        # Ensure control path directory exists
        os.makedirs('/tmp/ansible-ssh', exist_ok=True)
        
        # Set up environment
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_CONFIG"] = "/etc/ansible/ansible.cfg"
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        env_vars["ANSIBLE_SSH_CONTROL_PATH"] = "/tmp/ansible-ssh/%h-%p-%r"
        
        cmd = ["ansible-playbook", "-i", inventory_file, playbook_file, "-vvv"]
        
        log_message(deployment_id, f"Executing: {' '.join(cmd)}")
        
        # Use Popen for real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env_vars,
            bufsize=1,
            universal_newlines=True
        )
        
        # Read output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                # Clean up the output and log it
                clean_output = output.strip()
                if clean_output:  # Only log non-empty lines
                    log_message(deployment_id, clean_output)
        
        rc = process.poll()
        
        # Clean up temporary files
        try:
            os.remove(playbook_file)
            os.remove(inventory_file)
        except Exception as e:
            log_message(deployment_id, f"Warning: Could not clean up temporary files: {str(e)}")
        
        if rc == 0:
            log_message(deployment_id, "Ansible playbook executed successfully")
            return True
        else:
            log_message(deployment_id, f"Ansible playbook failed with return code: {rc}")
            return False
            
    except Exception as e:
        log_message(deployment_id, f"ERROR executing Ansible playbook: {str(e)}")
        return False

def execute_deployment_step(step, deployment_id, ft_number, current_user):
    """Execute a single deployment step"""
    # Import here to avoid circular imports
    from app import deployments
    
    deployment = deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        step_type = step.get('type')
        log_message(deployment_id, f"Executing step {step.get('order')}: {step.get('description')}")
        
        if step_type == 'file_deployment':
            return execute_file_deployment_step(step, deployment_id, ft_number, current_user)
        elif step_type == 'sql_deployment':
            return execute_sql_deployment_step(step, deployment_id, ft_number, current_user)
        elif step_type == 'service_restart':
            return execute_service_restart_step(step, deployment_id, current_user)
        elif step_type == 'ansible_playbook':
            return execute_ansible_playbook_step(step, deployment_id, current_user)
        elif step_type == 'helm_upgrade':
            return execute_helm_upgrade_step(step, deployment_id, current_user)
        else:
            log_message(deployment_id, f"ERROR: Unknown step type: {step_type}")
            return False
            
    except Exception as e:
        log_message(deployment_id, f"ERROR in step {step.get('order')}: {str(e)}")
        return False

def run_template_deployment(deployment_id, template, ft_number):
    """Run the template deployment in a separate thread"""
    # Import here to avoid circular imports
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
                
            success = execute_deployment_step(step, deployment_id, ft_number, current_user)
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
    """Start a template deployment"""
    try:
        # Import here to avoid circular imports
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
    """Get logs for a template deployment"""
    try:
        # Import here to avoid circular imports
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
