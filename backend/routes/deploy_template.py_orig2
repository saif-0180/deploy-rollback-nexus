

import os
import json
import subprocess
import threading
import time
import uuid
import base64
from flask import current_app, Blueprint, jsonify, request
import logging

# Create the blueprint without importing from app
deploy_template_bp = Blueprint('deploy_template', __name__)

logger = logging.getLogger('fix_deployment_orchestrator')
logging.basicConfig(level=logging.DEBUG)

# Deploy directory for logs
DEPLOYMENT_LOGS_DIR = os.environ.get('DEPLOYMENT_LOGS_DIR', '/app/logs')
TEMPLATE_DIR = "/app/deployment_templates"
INVENTORY_FILE = "/app/inventory/inventory.json"
DB_INVENTORY_FILE = "/app/inventory/db_inventory.json"
FIX_FILES_DIR = "/app/fixfiles"

def get_app_globals():
    """Get shared objects from the main app through current_app context"""
    try:
        from flask import current_app
        return current_app.deployments, current_app.save_deployment_history, current_app.log_message
    except:
        # Fallback - import directly (this should be avoided in production)
        logger.warning("Using fallback import - this may cause issues")
        import sys
        sys.path.append('/app/backend')
        app_module = __import__('app')
        return app_module.deployments, app_module.save_deployment_history, app_module.log_message

def load_template(template_name):
    """Load template from the deployment_templates directory"""
    try:
        template_path = os.path.join(TEMPLATE_DIR, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(template_path, 'r') as f:
            template = json.load(f)
        
        return template
    except Exception as e:
        raise Exception(f"Failed to load template: {str(e)}")

def load_inventory():
    """Load inventory and db_inventory files"""
    try:
        # Load main inventory
        with open(INVENTORY_FILE, 'r') as f:
            inventory = json.load(f)
        
        # Load database inventory
        db_inventory = {}
        if os.path.exists(DB_INVENTORY_FILE):
            with open(DB_INVENTORY_FILE, 'r') as f:
                db_inventory = json.load(f)
        
        return inventory, db_inventory
    except Exception as e:
        raise Exception(f"Failed to load inventory: {str(e)}")

def get_inventory_value(key, inventory, db_inventory):
    """Get value from inventory or db_inventory based on key"""
    # First check in main inventory
    if key in inventory:
        return inventory[key]
    
    # Then check in db_inventory
    if key in db_inventory:
        return db_inventory[key]
    
    # If not found, return None or raise exception
    return None

def execute_file_deployment(deployment_id, step, inventory, db_inventory):
    """Execute file deployment step using Ansible like in app.py"""
    try:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        
        logger.info(f"[{deployment_id}] Starting file deployment step {step['order']}: {step['description']}")
        log_message(deployment_id, f"Starting file deployment step {step['order']}: {step['description']}")
        
        ft_number = step['ftNumber']
        files = step['files']
        target_path = step['targetPath']
        target_user = step['targetUser']
        target_vms = step['targetVMs']
        
        # Get logged in user from deployment
        deployment = deployments[deployment_id]
        logged_in_user = deployment.get("logged_in_user", "system")
        
        # Resolve target VMs from inventory if needed
        resolved_vms = []
        for vm in target_vms:
            vm_info = get_inventory_value(vm, inventory, db_inventory)
            if vm_info:
                resolved_vms.append(vm_info)
            else:
                resolved_vms.append(vm)
        
        log_message(deployment_id, f"Deploying {len(files)} files to {len(resolved_vms)} VMs (initiated by {logged_in_user})")
        logger.info(f"[{deployment_id}] Deploying {len(files)} files to {len(resolved_vms)} VMs")
        
        for file_name in files:
            source_file = os.path.join(FIX_FILES_DIR, 'AllFts', ft_number, file_name)
            
            if not os.path.exists(source_file):
                error_msg = f"Source file not found: {source_file}"
                log_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                raise FileNotFoundError(error_msg)
            
            log_message(deployment_id, f"Deploying file: {file_name} (initiated by {logged_in_user})")
            
            # Generate ansible playbook for file deployment
            playbook_file = f"/tmp/file_deploy_{deployment_id}_{step['order']}.yml"
            final_target_path = os.path.join(target_path, file_name)
            
            with open(playbook_file, 'w') as f:
                f.write(f"""---
- name: Deploy file {file_name} (Step {step['order']}) (initiated by {logged_in_user})
  hosts: deployment_targets
  gather_facts: false
  become: true
  become_method: sudo
  become_user: {target_user}
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      
    - name: Create target directory
      ansible.builtin.file:
        path: "{target_path}"
        state: directory
        mode: '0755'
        owner: "{target_user}"
      
    - name: Check if file exists
      ansible.builtin.stat:
        path: "{final_target_path}"
      register: file_stat
      
    - name: Create backup if file exists
      ansible.builtin.copy:
        src: "{final_target_path}"
        dest: "{final_target_path}.bak.{{{{ ansible_date_time.epoch }}}}"
        remote_src: yes
      when: file_stat.stat.exists
      
    - name: Copy file to target
      ansible.builtin.copy:
        src: "{source_file}"
        dest: "{final_target_path}"
        mode: '0644'
        owner: "{target_user}"
      register: copy_result
      
    - name: Log success
      ansible.builtin.debug:
        msg: "File {file_name} deployed successfully by {logged_in_user}"
      when: copy_result.changed
""")
            
            # Create inventory file
            inventory_file = f"/tmp/inventory_{deployment_id}_{step['order']}"
            with open(inventory_file, 'w') as f:
                f.write("[deployment_targets]\n")
                for vm_name in resolved_vms:
                    if isinstance(vm_name, dict) and 'ip' in vm_name:
                        f.write(f"{vm_name['name']} ansible_host={vm_name['ip']} ansible_user=infadm ansible_ssh_private_key_file=/home/users/infadm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n")
                    else:
                        vm_info = next((v for v in inventory.get("vms", []) if v["name"] == vm_name), None)
                        if vm_info:
                            f.write(f"{vm_name} ansible_host={vm_info['ip']} ansible_user=infadm ansible_ssh_private_key_file=/home/users/infadm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n")
            
            # Execute ansible playbook
            env_vars = os.environ.copy()
            env_vars["ANSIBLE_CONFIG"] = "/etc/ansible/ansible.cfg"
            env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
            env_vars["ANSIBLE_SSH_CONTROL_PATH"] = "/tmp/ansible-ssh/%h-%p-%r"
            env_vars["ANSIBLE_SSH_CONTROL_PATH_DIR"] = "/tmp/ansible-ssh"
            
            cmd = ["ansible-playbook", "-i", inventory_file, playbook_file, "-v"]
            
            log_message(deployment_id, f"Executing: {' '.join(cmd)}")
            logger.info(f"Executing Ansible command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=300)
            
            # Log the output line by line
            if result.stdout:
                log_message(deployment_id, "=== ANSIBLE OUTPUT ===")
                for line in result.stdout.splitlines():
                    if line.strip():
                        log_message(deployment_id, line.strip())
            
            if result.stderr:
                log_message(deployment_id, "=== ANSIBLE STDERR ===")
                for line in result.stderr.splitlines():
                    if line.strip():
                        log_message(deployment_id, line.strip())
            
            if result.returncode == 0:
                log_message(deployment_id, f"File {file_name} deployed successfully")
                logger.info(f"[{deployment_id}] File {file_name} deployed successfully")
            else:
                error_msg = f"File deployment failed: {result.stderr}"
                log_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                raise Exception(error_msg)
            
            # Clean up temporary files
            try:
                os.remove(playbook_file)
                os.remove(inventory_file)
            except Exception as e:
                logger.warning(f"Error cleaning up temporary files: {str(e)}")
        
        log_message(deployment_id, f"File deployment step {step['order']} completed successfully")
        logger.info(f"[{deployment_id}] File deployment step {step['order']} completed successfully")
        
    except Exception as e:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        error_msg = f"File deployment step {step['order']} failed: {str(e)}"
        log_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        deployments[deployment_id]['status'] = 'failed'
        save_deployment_history()
        raise

def execute_service_restart(deployment_id, step, inventory, db_inventory):
    """Execute service operation step using Ansible with comprehensive systemd management like in app.py"""
    try:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        
        logger.debug(f"[{deployment_id}] DEBUG: Starting execute_service_restart")
        logger.debug(f"[{deployment_id}] DEBUG: Step data: {step}")
        
        if deployment_id not in deployments:
            logger.error(f"[{deployment_id}] DEBUG: Deployment ID not found in deployments")
            return

        deployment = deployments[deployment_id]
        logger.debug(f"[{deployment_id}] DEBUG: Found deployment: {deployment}")
        
        logged_in_user = "admin"
        
        order = step.get("order")
        description = step.get("description", "")
        service = step.get("service")
        operation = step.get("operation", "status")
        target_vms = step.get("targetVMs", [])

        logger.debug(f"[{deployment_id}] DEBUG: Service={service}, Operation={operation}, VMs={target_vms}")
        
        log_message(deployment_id, f"Starting systemd {operation} for service '{service}' on {len(target_vms)} VMs")
        logger.info(f"[{deployment_id}] Starting systemd {operation} for service '{service}' on {len(target_vms)} VMs")

        # Generate an ansible playbook for systemd operation
        playbook_file = f"/tmp/systemd_{deployment_id}_{order}.yml"
        logger.debug(f"[{deployment_id}] DEBUG: Creating playbook at {playbook_file}")
        
        with open(playbook_file, 'w') as f:
            f.write(f"""---
- name: Systemd {operation} operation for {service} 
  hosts: systemd_targets
  gather_facts: true
  vars:
    service_name: "{service}"
    operation_type: "{operation}"
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      
    - name: Check if service unit file exists
      ansible.builtin.stat:
        path: "/etc/systemd/system/{{{{ service_name }}}}"
      register: service_file_etc
      
    - name: Check if service unit file exists in lib
      ansible.builtin.stat:
        path: "/usr/lib/systemd/system/{{{{ service_name }}}}"
      register: service_file_lib
      
    - name: Check if service unit file exists in local
      ansible.builtin.stat:
        path: "/usr/local/lib/systemd/system/{{{{ service_name }}}}"
      register: service_file_local
      
    - name: Set service exists fact
      ansible.builtin.set_fact:
        service_exists: "{{{{ service_file_etc.stat.exists or service_file_lib.stat.exists or service_file_local.stat.exists }}}}"
        
    - name: Report if service doesn't exist
      ansible.builtin.debug:
        msg: "ERROR: Service '{{{{ service_name }}}}' unit file not found on {{{{ inventory_hostname }}}}"
      when: not service_exists
      
    - name: Get detailed service status
      ansible.builtin.systemd:
        name: "{{{{ service_name }}}}"
      register: service_status
      when: service_exists
      failed_when: false
      
    - name: Get service status with systemctl
      ansible.builtin.shell: |
        systemctl status {{{{ service_name }}}} --no-pager -l || true
        echo "---SEPARATOR---"
        systemctl show {{{{ service_name }}}} --property=ActiveState,SubState,LoadState,UnitFileState,ExecMainStartTimestamp,ExecMainPID,MainPID || true
      register: service_details
      when: service_exists
      
    - name: Parse service uptime
      ansible.builtin.shell: |
        if systemctl is-active {{{{ service_name }}}} >/dev/null 2>&1; then
          start_time=$(systemctl show {{{{ service_name }}}} --property=ExecMainStartTimestamp --value)
          if [ -n "$start_time" ] && [ "$start_time" != "n/a" ]; then
            echo "Service started at: $start_time"
            # Calculate uptime
            start_epoch=$(date -d "$start_time" +%s 2>/dev/null || echo "0")
            current_epoch=$(date +%s)
            if [ "$start_epoch" -gt 0 ]; then
              uptime_seconds=$((current_epoch - start_epoch))
              uptime_days=$((uptime_seconds / 86400))
              uptime_hours=$(((uptime_seconds % 86400) / 3600))
              uptime_minutes=$(((uptime_seconds % 3600) / 60))
              echo "Uptime: ${{uptime_days}}d ${{uptime_hours}}h ${{uptime_minutes}}m"
            else
              echo "Uptime: Unable to calculate"
            fi
          else
            echo "Service start time: Not available"
            echo "Uptime: Not available"
          fi
        else
          echo "Service is not active"
        fi
      register: service_uptime
      when: service_exists
      
    - name: Display comprehensive service status
      ansible.builtin.debug:
        msg: |
          ===========================================
          SERVICE STATUS REPORT for {{{{ inventory_hostname }}}}
          ===========================================
          Service Name: {{{{ service_name }}}}
          Active State: {{{{ service_status.status.ActiveState | default('unknown') }}}}
          Sub State: {{{{ service_status.status.SubState | default('unknown') }}}}
          Load State: {{{{ service_status.status.LoadState | default('unknown') }}}}
          Unit File State: {{{{ service_status.status.UnitFileState | default('unknown') }}}}
          Main PID: {{{{ service_status.status.MainPID | default('N/A') }}}}
          
          {{{{ service_uptime.stdout | default('Uptime info not available') }}}}
          
          Status: {{{{ 'ACTIVE' if service_status.status.ActiveState == 'active' else 'INACTIVE/DEAD' }}}}
          Enabled: {{{{ 'YES' if service_status.status.UnitFileState in ['enabled', 'enabled-runtime'] else 'NO' }}}}
          ===========================================
      when: service_exists and operation_type == 'status'

    - name: Perform systemd START operation
      ansible.builtin.shell: |
        sudo systemctl start {{{{ service_name }}}}
      register: start_result
      when: service_exists and operation_type == 'start'

    - name: Perform systemd STOP operation
      ansible.builtin.shell: |
        sudo systemctl stop {{{{ service_name }}}}
      register: stop_result
      when: service_exists and operation_type == 'stop'

    - name: Perform systemd RESTART operation
      ansible.builtin.shell: |
        sudo systemctl restart {{{{ service_name }}}}
      register: restart_result
      when: service_exists and operation_type == 'restart'
      
    - name: Verify operation result
      ansible.builtin.systemd:
        name: "{{{{ service_name }}}}"
      register: post_operation_status
      when: service_exists and operation_type in ['start', 'stop', 'restart']
      failed_when: false
      
    - name: Report operation success
      ansible.builtin.debug:
        msg: |
          ===========================================
          OPERATION RESULT for {{{{ inventory_hostname }}}}
          ===========================================
          Service: {{{{ service_name }}}}
          Operation: {{{{ operation_type | upper }}}}
          Result: SUCCESS
          New Status: {{{{ post_operation_status.status.ActiveState | default('unknown') }}}} ({{{{ post_operation_status.status.SubState | default('unknown') }}}})
          Enabled: {{{{ 'YES' if post_operation_status.status.UnitFileState in ['enabled', 'enabled-runtime'] else 'NO' }}}}
          ===========================================
      when: service_exists and operation_type in ['start', 'stop', 'restart']
      
    - name: Get final service status for logging
      ansible.builtin.shell: systemctl is-active {{{{ service_name }}}} || echo "inactive"
      register: final_status
      when: service_exists
      
    - name: Log final status
      ansible.builtin.debug:
        msg: "Final service status on {{{{ inventory_hostname }}}}: {{{{ final_status.stdout | default('unknown') }}}}"
      when: service_exists
""")

        # Generate inventory file for ansible
        inventory_file = f"/tmp/inventory_{deployment_id}_{order}"
        logger.debug(f"[{deployment_id}] DEBUG: Creating inventory at {inventory_file}")
        
        with open(inventory_file, 'w') as f:
            f.write("[systemd_targets]\n")
            for vm_name in target_vms:
                # Find VM IP from inventory
                vm = next((v for v in inventory["vms"] if v["name"] == vm_name), None)
                if vm:
                    f.write(f"{vm_name} ansible_host={vm['ip']} ansible_user=infadm ansible_ssh_private_key_file=/home/users/infadm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ControlMaster=auto -o ControlPath=/tmp/ansible-ssh/%h-%p-%r -o ControlPersist=60s'\n")
        
        # Run ansible playbook
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_CONFIG"] = "/etc/ansible/ansible.cfg"
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        env_vars["ANSIBLE_SSH_CONTROL_PATH"] = "/tmp/ansible-ssh/%h-%p-%r"
        env_vars["ANSIBLE_SSH_CONTROL_PATH_DIR"] = "/tmp/ansible-ssh"
        
        cmd = ["ansible-playbook", "-i", inventory_file, playbook_file, "-v"]
        
        log_message(deployment_id, f"Executing: {' '.join(cmd)}")
        logger.info(f"Executing Ansible command: {' '.join(cmd)}")
        logger.debug(f"[{deployment_id}] DEBUG: Running command: {' '.join(cmd)}")
        
        # Use subprocess.run with capture_output=True instead of Popen
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=300)
        
        logger.debug(f"[{deployment_id}] DEBUG: Command completed with return code: {result.returncode}")
        
        # Log the output line by line
        if result.stdout:
            log_message(deployment_id, "=== ANSIBLE OUTPUT ===")
            for line in result.stdout.splitlines():
                if line.strip():  # Only log non-empty lines
                    log_message(deployment_id, line.strip())
        
        if result.stderr:
            log_message(deployment_id, "=== ANSIBLE STDERR ===")
            for line in result.stderr.splitlines():
                if line.strip():  # Only log non-empty lines
                    log_message(deployment_id, line.strip())
        
        # Check result and update status
        if result.returncode == 0:
            log_message(deployment_id, f"SUCCESS: Systemd {operation} operation completed successfully (initiated by {logged_in_user})")
            deployments[deployment_id]["status"] = "completed"
            logger.info(f"Systemd operation {deployment_id} completed successfully (initiated by {logged_in_user})")
        else:
            error_msg = f"ERROR: Systemd {operation} operation failed with return code {result.returncode} (initiated by {logged_in_user})"
            log_message(deployment_id, error_msg)
            logger.error(f"Systemd operation {deployment_id} failed with return code {result.returncode} (initiated by {logged_in_user})")
            deployments[deployment_id]['status'] = 'failed'
            # save_deployment_history()
            # raise Exception(error_msg)
        
        # Clean up temporary files
        try:
            os.remove(playbook_file)
            os.remove(inventory_file)
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {str(e)}")

        log_message(deployment_id, f"Step {order} completed: systemctl {operation} {service} on all VMs")
        logger.info(f"[{deployment_id}] Step {order} completed successfully")
        # Save deployment history after completion
        save_deployment_history()
        
    except subprocess.TimeoutExpired:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        error_msg = f"ERROR: Systemd {operation} operation timed out after 5 minutes"
        log_message(deployment_id, error_msg)
        deployments[deployment_id]["status"] = "failed"
        logger.error(f"Systemd operation {deployment_id} timed out")
        save_deployment_history()
        raise Exception(error_msg)
        
    except Exception as e:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        error_msg = f"ERROR: Service operation failed: {str(e)}"
        log_message(deployment_id, error_msg)
        logger.exception(f"[{deployment_id}] Critical error in execute_service_restart()")
        if deployment_id in deployments:
            deployments[deployment_id]["status"] = "failed"
            save_deployment_history()
        raise

# ... keep existing code (other execute functions like sql_deployment, ansible_playbook, helm_upgrade)

def execute_sql_deployment(deployment_id, step, inventory, db_inventory):
    """Execute SQL deployment step using proper database connections"""
    try:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        
        logger.info(f"[{deployment_id}] Starting SQL deployment step {step['order']}: {step['description']}")
        log_message(deployment_id, f"Starting SQL deployment step {step['order']}: {step['description']}")
        
        db_connection = step['dbConnection']
        db_user = step['dbUser']
        db_password = step['dbPassword']
        files = step['files']
        ft_number = step['ftNumber']
        
        # Get logged in user from deployment
        deployment = deployments[deployment_id]
        logged_in_user = deployment.get("logged_in_user", "system")
        
        # Resolve database connection details from inventory
        db_info = get_inventory_value(db_connection, inventory, db_inventory)
        if not db_info:
            error_msg = f"Database connection '{db_connection}' not found in inventory"
            log_message(deployment_id, f"ERROR: {error_msg}")
            logger.error(f"[{deployment_id}] {error_msg}")
            raise Exception(error_msg)
        
        # Decode password if it's base64 encoded
        try:
            decoded_password = base64.b64decode(db_password).decode('utf-8')
        except:
            decoded_password = db_password
        
        log_message(deployment_id, f"Executing SQL files: {', '.join(files)} (initiated by {logged_in_user})")
        logger.info(f"[{deployment_id}] Executing SQL files: {', '.join(files)}")
        
        for sql_file in files:
            source_file = os.path.join(FIX_FILES_DIR, 'AllFts', ft_number, sql_file)
            
            if not os.path.exists(source_file):
                error_msg = f"SQL file not found: {source_file}"
                log_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                raise FileNotFoundError(error_msg)
            
            log_message(deployment_id, f"Executing SQL file: {sql_file}")
            
            # Execute SQL file (adjust based on your database type)
            if 'oracle' in db_info.get('type', '').lower():
                cmd = ["sqlplus", "-s", f"{db_user}/{decoded_password}@{db_info['host']}:{db_info['port']}/{db_info['service']}", f"@{source_file}"]
            elif 'mysql' in db_info.get('type', '').lower():
                cmd = ["mysql", "-h", db_info['host'], "-P", str(db_info['port']), "-u", db_user, f"-p{decoded_password}", "-e", f"source {source_file}"]
            elif 'postgres' in db_info.get('type', '').lower():
                cmd = ["psql", "-h", db_info['host'], "-p", str(db_info['port']), "-U", db_user, "-d", db_info['database'], "-f", source_file]
            else:
                error_msg = f"Unsupported database type: {db_info.get('type', 'unknown')}"
                log_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                raise Exception(error_msg)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                log_message(deployment_id, f"SQL file {sql_file} executed successfully")
                logger.info(f"[{deployment_id}] SQL file {sql_file} executed successfully")
            else:
                error_msg = f"SQL execution failed: {result.stderr}"
                log_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                raise Exception(error_msg)
        
        log_message(deployment_id, f"SQL deployment step {step['order']} completed successfully")
        logger.info(f"[{deployment_id}] SQL deployment step {step['order']} completed successfully")
        
    except Exception as e:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        error_msg = f"SQL deployment step {step['order']} failed: {str(e)}"
        log_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        deployments[deployment_id]['status'] = 'failed'
        save_deployment_history()
        raise

def execute_ansible_playbook(deployment_id, step, inventory, db_inventory):
    """Execute ansible playbook step using proper playbook execution"""
    try:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        
        logger.info(f"[{deployment_id}] Starting ansible playbook step {step['order']}: {step['description']}")
        log_message(deployment_id, f"Starting ansible playbook step {step['order']}: {step['description']}")
        
        playbook = step['playbook']
        
        # Get logged in user from deployment
        deployment = deployments[deployment_id]
        logged_in_user = deployment.get("logged_in_user", "system")
        
        # Find playbook file
        playbook_path = os.path.join("/app/ansible_playbooks", playbook)
        if not os.path.exists(playbook_path):
            # Try alternative locations
            alternative_paths = [
                os.path.join(FIX_FILES_DIR, "playbooks", playbook),
                os.path.join("/app/playbooks", playbook),
                f"/tmp/{playbook}"
            ]
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    playbook_path = alt_path
                    break
            else:
                error_msg = f"Playbook not found: {playbook}"
                log_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                raise FileNotFoundError(error_msg)
        
        log_message(deployment_id, f"Executing playbook: {playbook} (initiated by {logged_in_user})")
        logger.info(f"[{deployment_id}] Executing playbook: {playbook}")
        
        # Create inventory file with all VMs
        inventory_file = f"/tmp/inventory_{deployment_id}_{step['order']}"
        with open(inventory_file, 'w') as f:
            f.write("[all]\n")
            for vm in inventory.get("vms", []):
                f.write(f"{vm['name']} ansible_host={vm['ip']} ansible_user=infadm ansible_ssh_private_key_file=/home/users/infadm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n")
        
        # Execute ansible playbook
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_CONFIG"] = "/etc/ansible/ansible.cfg"
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
        cmd = ["ansible-playbook", "-i", inventory_file, playbook_path, "-v"]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=600)
        
        # Log the output line by line
        if result.stdout:
            log_message(deployment_id, "=== ANSIBLE PLAYBOOK OUTPUT ===")
            for line in result.stdout.splitlines():
                if line.strip():
                    log_message(deployment_id, line.strip())
        
        if result.stderr:
            log_message(deployment_id, "=== ANSIBLE PLAYBOOK STDERR ===")
            for line in result.stderr.splitlines():
                if line.strip():
                    log_message(deployment_id, line.strip())
        
        if result.returncode == 0:
            log_message(deployment_id, f"Playbook {playbook} executed successfully")
            logger.info(f"[{deployment_id}] Playbook {playbook} executed successfully")
        else:
            error_msg = f"Playbook execution failed: {result.stderr}"
            log_message(deployment_id, f"ERROR: {error_msg}")
            logger.error(f"[{deployment_id}] {error_msg}")
            raise Exception(error_msg)
        
        # Clean up temporary files
        try:
            os.remove(inventory_file)
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {str(e)}")
        
        log_message(deployment_id, f"Ansible playbook step {step['order']} completed successfully")
        logger.info(f"[{deployment_id}] Ansible playbook step {step['order']} completed successfully")
        
    except Exception as e:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        error_msg = f"Ansible playbook step {step['order']} failed: {str(e)}"
        log_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        deployments[deployment_id]['status'] = 'failed'
        save_deployment_history()
        raise

def execute_helm_upgrade(deployment_id, step, inventory, db_inventory):
    """Execute helm upgrade step using proper helm commands"""
    try:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        
        logger.info(f"[{deployment_id}] Starting helm upgrade step {step['order']}: {step['description']}")
        log_message(deployment_id, f"Starting helm upgrade step {step['order']}: {step['description']}")
        
        helm_deployment_type = step['helmDeploymentType']
        
        # Get logged in user from deployment
        deployment = deployments[deployment_id]
        logged_in_user = deployment.get("logged_in_user", "system")
        
        # Get helm configuration from inventory
        helm_config = get_inventory_value(f"helm_{helm_deployment_type}", inventory, db_inventory)
        if not helm_config:
            error_msg = f"Helm configuration for '{helm_deployment_type}' not found in inventory"
            log_message(deployment_id, f"ERROR: {error_msg}")
            logger.error(f"[{deployment_id}] {error_msg}")
            raise Exception(error_msg)
        
        log_message(deployment_id, f"Executing helm upgrade for: {helm_deployment_type} (initiated by {logged_in_user})")
        logger.info(f"[{deployment_id}] Executing helm upgrade for: {helm_deployment_type}")
        
        # Construct helm upgrade command
        release_name = helm_config.get('release_name', helm_deployment_type)
        chart_name = helm_config.get('chart_name', helm_deployment_type)
        namespace = helm_config.get('namespace', 'default')
        values_file = helm_config.get('values_file', '')
        
        cmd = ["helm", "upgrade", release_name, chart_name, "--namespace", namespace]
        
        if values_file:
            values_path = os.path.join("/app/helm_values", values_file)
            if os.path.exists(values_path):
                cmd.extend(["-f", values_path])
        
        # Add any additional helm arguments
        if 'args' in helm_config:
            cmd.extend(helm_config['args'])
        
        log_message(deployment_id, f"Executing helm command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            log_message(deployment_id, f"Helm upgrade for {helm_deployment_type} completed successfully")
            log_message(deployment_id, f"Helm output: {result.stdout}")
            logger.info(f"[{deployment_id}] Helm upgrade for {helm_deployment_type} completed successfully")
        else:
            error_msg = f"Helm upgrade failed: {result.stderr}"
            log_message(deployment_id, f"ERROR: {error_msg}")
            logger.error(f"[{deployment_id}] {error_msg}")
            raise Exception(error_msg)
        
        log_message(deployment_id, f"Helm upgrade step {step['order']} completed successfully")
        logger.info(f"[{deployment_id}] Helm upgrade step {step['order']} completed successfully")
        
    except Exception as e:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        error_msg = f"Helm upgrade step {step['order']} failed: {str(e)}"
        log_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        deployments[deployment_id]['status'] = 'failed'
        save_deployment_history()
        raise

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template_route():
    try:
        data = request.get_json()
        logger.debug(f"DEBUG: Received JSON payload: {data}")

        template_name = data.get('template')
        if not template_name:
            logger.warning("DEBUG: Missing 'template' key in request")
            return jsonify({"error": "Template name is required"}), 400

        # Get current user from request headers or use default
        current_user = {"username": "admin", "role": "admin"}
        logger.info(f"DEBUG: Initiating deployment for template: {template_name} by user: {current_user['username']}")

        # Call the deployment function
        result, status_code = deploy_template(template_name, current_user)
        logger.info(f"DEBUG: Deployment started: {result.get('deploymentId')} (Status code: {status_code})")

        return jsonify(result), status_code

    except Exception as e:
        logger.exception("DEBUG: Error occurred while handling template deployment")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/templates', methods=['GET'])
def list_templates():
    """List available deployment templates"""
    try:
        templates = []
        if os.path.exists(TEMPLATE_DIR):
            for file_name in os.listdir(TEMPLATE_DIR):
                if file_name.endswith('.json'):
                    try:
                        template = load_template(file_name)
                        templates.append({
                            "name": file_name,
                            "description": template.get('metadata', {}).get('description', ''),
                            "ft_number": template.get('metadata', {}).get('ft_number', ''),
                            "total_steps": template.get('metadata', {}).get('total_steps', len(template.get('steps', []))),
                            "steps": [
                                {
                                    "order": step.get('order'),
                                    "type": step.get('type'),
                                    "description": step.get('description', '')
                                } for step in template.get('steps', [])
                            ]
                        })
                    except Exception as e:
                        logger.warning(f"Failed to load template {file_name}: {str(e)}")
                        continue

        return jsonify({"templates": templates})
    except Exception as e:
        logger.error(f"Failed to list templates: {str(e)}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/template/<template_name>', methods=['GET'])
def get_template_details(template_name):
    """Get details of a specific template"""
    try:
        template = load_template(template_name)
        return jsonify(template)
    except Exception as e:
        logger.error(f"Failed to get template details: {str(e)}")
        return jsonify({"error": str(e)}), 500

def execute_step(deployment_id, step, inventory, db_inventory):
    """Execute a single step based on its type"""
    step_type = step['type']
    logger.debug(f"[{deployment_id}] DEBUG: Executing step type: {step_type}")
    
    if step_type == 'file_deployment':
        execute_file_deployment(deployment_id, step, inventory, db_inventory)
    elif step_type == 'sql_deployment':
        execute_sql_deployment(deployment_id, step, inventory, db_inventory)
    elif step_type == 'service_restart':
        execute_service_restart(deployment_id, step, inventory, db_inventory)
    elif step_type == 'ansible_playbook':
        execute_ansible_playbook(deployment_id, step, inventory, db_inventory)
    elif step_type == 'helm_upgrade':
        execute_helm_upgrade(deployment_id, step, inventory, db_inventory)
    else:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
        error_msg = f"Unknown step type: {step_type}"
        log_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        raise Exception(error_msg)

def can_execute_step(step, completed_steps, dependencies):
    """Check if a step can be executed based on its dependencies"""
    step_number = step['order']
    
    # Find dependencies for this step
    step_deps = None
    for dep in dependencies:
        if dep['step'] == step_number:
            step_deps = dep
            break
    
    if not step_deps:
        return True  # No dependencies defined
    
    # Check if all dependencies are completed
    for dep_step in step_deps['depends_on']:
        if dep_step not in completed_steps:
            return False
    
    return True

# def process_template_deployment(deployment_id):
#     """Process template deployment with dependency management"""
#     logger.debug(f"[{deployment_id}] DEBUG: Starting process_template_deployment")
    
#     try:
#         deployments, save_deployment_history, log_message, _ = get_app_globals()
#     except Exception as e:
#         logger.error(f"[{deployment_id}] Failed to get app globals: {str(e)}")
#         return
    
#     if deployment_id not in deployments:
#         logger.error(f"[{deployment_id}] DEBUG: Deployment ID not found in deployments")
#         return
        
#     deployment = deployments[deployment_id]
#     logger.debug(f"[{deployment_id}] DEBUG: Processing deployment: {deployment}")
    
#     try:
#         template_name = deployment['template']
        
#         # Load template
#         template = load_template(template_name)
#         log_message(deployment_id, f"Loaded template: {template_name}")
#         logger.info(f"[{deployment_id}] Loaded template: {template_name}")
        
#         # Load inventory
#         inventory, db_inventory = load_inventory()
#         log_message(deployment_id, f"Loaded inventory data")
#         logger.info(f"[{deployment_id}] Loaded inventory data")
        
#         # Get steps and dependencies
#         steps = template['steps']
#         dependencies = template.get('dependencies', [])
        
#         log_message(deployment_id, f"Starting template deployment with {len(steps)} steps")
#         logger.info(f"[{deployment_id}] Starting template deployment with {len(steps)} steps")
        
#         # Sort steps by order
#         steps.sort(key=lambda x: x['order'])
        
#         completed_steps = set()
#         failed_steps = set()
        
#         # Execute steps based on dependencies
#         while len(completed_steps) < len(steps) and not failed_steps:
#             ready_steps = []
            
#             for step in steps:
#                 step_number = step['order']
#                 if step_number not in completed_steps and step_number not in failed_steps:
#                     if can_execute_step(step, completed_steps, dependencies):
#                         ready_steps.append(step)
            
#             if not ready_steps:
#                 if len(completed_steps) < len(steps):
#                     error_msg = "No more steps can be executed due to dependencies"
#                     log_message(deployment_id, f"ERROR: {error_msg}")
#                     logger.error(f"[{deployment_id}] {error_msg}")
#                     break
#                 else:
#                     break
            
#             # Execute ready steps
#             for step in ready_steps:
#                 try:
#                     log_message(deployment_id, f"Executing step {step['order']}: {step['description']}")
#                     logger.info(f"[{deployment_id}] Executing step {step['order']}: {step['description']}")
#                     execute_step(deployment_id, step, inventory, db_inventory)
#                     completed_steps.add(step['order'])
#                     log_message(deployment_id, f"Step {step['order']} completed successfully")
#                     logger.info(f"[{deployment_id}] Step {step['order']} completed successfully")
#                 except Exception as e:
#                     error_msg = f"Step {step['order']} failed: {str(e)}"
#                     log_message(deployment_id, f"ERROR: {error_msg}")
#                     logger.error(f"[{deployment_id}] {error_msg}")
#                     failed_steps.add(step['order'])
#                     break  # Stop execution on first failure
        
#         # Update deployment status
#         if failed_steps:
#             deployments[deployment_id]['status'] = 'failed'
#             log_message(deployment_id, f"Template deployment failed. Steps failed: {failed_steps}")
#             logger.error(f"[{deployment_id}] Template deployment failed. Steps failed: {failed_steps}")
#         else:
#             deployments[deployment_id]['status'] = 'success'
#             log_message(deployment_id, f"Template deployment completed successfully. Steps completed: {completed_steps}")
#             logger.info(f"[{deployment_id}] Template deployment completed successfully. Steps completed: {completed_steps}")
        
#     except Exception as e:
#         error_msg = f"Template deployment failed: {str(e)}"
#         log_message(deployment_id, f"ERROR: {error_msg}")
#         logger.exception(f"[{deployment_id}] Template deployment critical error")
#         deployments[deployment_id]['status'] = 'failed'
    
#     finally:
#         # Save deployment history
#         save_deployment_history()
#         logger.info(f"[{deployment_id}] Deployment history saved")

# def deploy_template(template_name, current_user):
#     """Main function to start template deployment"""
#     try:
#         logger.debug(f"DEBUG: Starting deploy_template for {template_name}")
        
#         # Validate template exists
#         template_path = os.path.join(TEMPLATE_DIR, template_name)
#         if not os.path.exists(template_path):
#             error_msg = f"Template not found: {template_name}"
#             logger.error(f"DEBUG: {error_msg}")
#             return {"error": error_msg}, 404
        
#         # Generate deployment ID
#         deployment_id = str(uuid.uuid4())
#         logger.debug(f"DEBUG: Generated deployment ID: {deployment_id}")
        
#         # Get app globals
#         deployments, save_deployment_history, log_message, _ = get_app_globals()
        
#         # Store deployment information in the main app's deployments dict
#         deployments[deployment_id] = {
#             "id": deployment_id,
#             "type": "template",
#             "template": template_name,
#             "logged_in_user": "admin",
#             "user_role": "admin",
#             "status": "running",
#             "timestamp": time.time(),
#             "logs": []
#         }
        
#         logger.debug(f"DEBUG: Added deployment to deployments dict: {deployments[deployment_id]}")
#         logger.info(f"[{deployment_id}] Template deployment initiated ")
        
#         # Save deployment history
#         save_deployment_history()
#         logger.debug(f"DEBUG: Saved deployment history")
        
#         # Start deployment in separate thread
#         logger.debug(f"DEBUG: Starting background thread for deployment")
#         threading.Thread(target=process_template_deployment, args=(deployment_id,)).start()
        
#         return {
#             "deploymentId": deployment_id,
#             # "initiatedBy": current_user['username'],
#             "template": template_name
#         }, 200
        
#     except Exception as e:
#         error_msg = f"Failed to start template deployment: {str(e)}"
#         logger.exception(f"DEBUG: Critical error in deploy_template: {error_msg}")
#         return {"error": error_msg}, 500
def process_template_deployment(deployment_id):
    """Process template deployment with dependency management"""
    logger.debug(f"[{deployment_id}] DEBUG: Starting process_template_deployment")

    try:
        deployments, save_deployment_history, log_message, _ = get_app_globals()
    except Exception as e:
        logger.error(f"[{deployment_id}] Failed to get app globals: {str(e)}")
        return

    if deployment_id not in deployments:
        logger.error(f"[{deployment_id}] DEBUG: Deployment ID not found in deployments")
        return

    deployment = deployments[deployment_id]
    logger.debug(f"[{deployment_id}] DEBUG: Processing deployment: {deployment}")

    try:
        template_name = deployment['template']

        # Load template
        template = load_template(template_name)
        log_message(deployment_id, f"Loaded template: {template_name}")
        logger.info(f"[{deployment_id}] Loaded template: {template_name}")

        # Load inventory
        inventory, db_inventory = load_inventory()
        log_message(deployment_id, f"Loaded inventory data")
        logger.info(f"[{deployment_id}] Loaded inventory data")

        # Get steps and dependencies
        steps = template['steps']
        dependencies = template.get('dependencies', [])

        log_message(deployment_id, f"Starting template deployment with {len(steps)} steps")
        logger.info(f"[{deployment_id}] Starting template deployment with {len(steps)} steps")

        # Sort steps by order
        steps.sort(key=lambda x: x['order'])

        completed_steps = set()
        failed_steps = set()

        # Execute steps based on dependencies
        while len(completed_steps) < len(steps) and not failed_steps:
            ready_steps = []

            for step in steps:
                step_number = step['order']
                if step_number not in completed_steps and step_number not in failed_steps:
                    if can_execute_step(step, completed_steps, dependencies):
                        ready_steps.append(step)

            if not ready_steps:
                if len(completed_steps) < len(steps):
                    error_msg = "No more steps can be executed due to dependencies"
                    log_message(deployment_id, f"ERROR: {error_msg}")
                    logger.error(f"[{deployment_id}] {error_msg}")
                    break
                else:
                    break

            # Execute ready steps
            for step in ready_steps:
                try:
                    log_message(deployment_id, f"Executing step {step['order']}: {step['description']}")
                    logger.info(f"[{deployment_id}] Executing step {step['order']}: {step['description']}")
                    execute_step(deployment_id, step, inventory, db_inventory)
                    completed_steps.add(step['order'])
                    log_message(deployment_id, f"Step {step['order']} completed successfully")
                    logger.info(f"[{deployment_id}] Step {step['order']} completed successfully")
                except Exception as e:
                    error_msg = f"Step {step['order']} failed: {str(e)}"
                    log_message(deployment_id, f"ERROR: {error_msg}")
                    logger.error(f"[{deployment_id}] {error_msg}")
                    failed_steps.add(step['order'])
                    break  # Stop execution on first failure

        # Update deployment status
        if failed_steps:
            deployments[deployment_id]['status'] = 'failed'
            log_message(deployment_id, f"Template deployment failed. Steps failed: {failed_steps}")
            logger.error(f"[{deployment_id}] Template deployment failed. Steps failed: {failed_steps}")
        else:
            deployments[deployment_id]['status'] = 'success'
            log_message(deployment_id, f"Template deployment completed successfully. Steps completed: {completed_steps}")
            logger.info(f"[{deployment_id}] Template deployment completed successfully. Steps completed: {completed_steps}")

    except Exception as e:
        error_msg = f"Template deployment failed: {str(e)}"
        log_message(deployment_id, f"ERROR: {error_msg}")
        logger.exception(f"[{deployment_id}] Template deployment critical error")
        deployments[deployment_id]['status'] = 'failed'

    finally:
        # Save deployment history
        save_deployment_history()
        logger.info(f"[{deployment_id}] Deployment history saved")

def run_in_app_context(app, deployment_id):
    with app.app_context():
        process_template_deployment(deployment_id)

# def deploy_template(template_name, current_user):
#     """Main function to start template deployment"""
#     try:
#         logger.debug(f"DEBUG: Starting deploy_template for {template_name}")

#         # Validate template exists
#         template_path = os.path.join(TEMPLATE_DIR, template_name)
#         if not os.path.exists(template_path):
#             error_msg = f"Template not found: {template_name}"
#             logger.error(f"DEBUG: {error_msg}")
#             return {"error": error_msg}, 404

#         # Generate deployment ID
#         deployment_id = str(uuid.uuid4())
#         logger.debug(f"DEBUG: Generated deployment ID: {deployment_id}")

#         # Get app globals
#         deployments, save_deployment_history, log_message, _ = get_app_globals()

#         # Store deployment information in the main app's deployments dict
#         deployments[deployment_id] = {
#             "id": deployment_id,
#             "type": "template",
#             "template": template_name,
#             "logged_in_user": "admin",
#             "user_role": "admin",
#             "status": "running",
#             "timestamp": time.time(),
#             "logs": []
#         }

#         logger.debug(f"DEBUG: Added deployment to deployments dict: {deployments[deployment_id]}")
#         logger.info(f"[{deployment_id}] Template deployment initiated ")

#         # Save deployment history
#         save_deployment_history()
#         logger.debug(f"DEBUG: Saved deployment history")

#         # Start deployment in separate thread with app context
#         logger.debug(f"DEBUG: Starting background thread for deployment")
#         app = current_app._get_current_object()
#         threading.Thread(target=lambda: app.app_context().push() or process_template_deployment(deployment_id)).start()

#         return {
#             "deploymentId": deployment_id,
#             "template": template_name
#         }, 200

#     except Exception as e:
#         error_msg = f"Failed to start template deployment: {str(e)}"
#         logger.exception(f"DEBUG: Critical error in deploy_template: {error_msg}")
#         return {"error": error_msg}, 500

def deploy_template(template_name, current_user):
    """Main function to start template deployment"""
    try:
        logger.debug(f"DEBUG: Starting deploy_template for {template_name}")

        # Validate template exists
        template_path = os.path.join(TEMPLATE_DIR, template_name)
        if not os.path.exists(template_path):
            error_msg = f"Template not found: {template_name}"
            logger.error(f"DEBUG: {error_msg}")
            return {"error": error_msg}, 404

        # Generate deployment ID
        deployment_id = str(uuid.uuid4())
        logger.debug(f"DEBUG: Generated deployment ID: {deployment_id}")

        # Get app globals
        deployments, save_deployment_history, log_message, _ = get_app_globals()

        # Store deployment information in the main app's deployments dict
        deployments[deployment_id] = {
            "id": deployment_id,
            "type": "template",
            "template": template_name,
            "logged_in_user": current_user.get("username", "admin"),
            "user_role": current_user.get("role", "admin"),
            "status": "running",
            "timestamp": time.time(),
            "logs": []
        }

        logger.debug(f"DEBUG: Added deployment to deployments dict: {deployments[deployment_id]}")
        logger.info(f"[{deployment_id}] Template deployment initiated ")

        # Save deployment history
        save_deployment_history()
        logger.debug(f"DEBUG: Saved deployment history")

        # Push app context properly to the new thread
        app = current_app._get_current_object()

        def run_in_app_context(app, deployment_id):
            with app.app_context():
                process_template_deployment(deployment_id)

        app = current_app._get_current_object()
        threading.Thread(target=run_in_app_context, args=(app, deployment_id)).start()
        return {
            "deploymentId": deployment_id,
            "template": template_name
        }, 200

    except Exception as e:
        error_msg = f"Failed to start template deployment: {str(e)}"
        logger.exception(f"DEBUG: Critical error in deploy_template: {error_msg}")
        return {"error": error_msg}, 500
