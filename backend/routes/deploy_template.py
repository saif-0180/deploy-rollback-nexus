
import os
import json
import subprocess
import threading
import time
import uuid
import base64
from flask import current_app, Blueprint, jsonify, request
import logging

# Create the blueprint
deploy_template_bp = Blueprint('deploy_template', __name__)

# Set up logging
logger = logging.getLogger('template_deployment')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Deploy directory for logs
DEPLOYMENT_LOGS_DIR = os.environ.get('DEPLOYMENT_LOGS_DIR', '/app/logs')
TEMPLATE_DIR = "/app/deployment_templates"
INVENTORY_FILE = "/app/inventory/inventory.json"
DB_INVENTORY_FILE = "/app/inventory/db_inventory.json"
FIX_FILES_DIR = "/app/fixfiles"

# Template deployments dictionary - separate from main deployments
template_deployments = {}

def get_app_globals():
    """Get shared objects from the main app via current_app context"""
    try:
        # Use separate template deployments dictionary
        if not hasattr(current_app, 'template_deployments'):
            current_app.template_deployments = {}
        
        # Access save_deployment_history function
        save_deployment_history = getattr(current_app, 'save_deployment_history', None)
        if save_deployment_history is None:
            save_deployment_history = current_app.config.get('save_deployment_history')
        
        # Create fallback function if needed
        if not save_deployment_history:
            logger.warning("save_deployment_history function is None, creating fallback")
            def fallback_save():
                logger.debug("Fallback save_deployment_history called")
                pass
            save_deployment_history = fallback_save
        
        # Load inventory
        inventory = load_inventory_files()
        
        logger.debug(f"Retrieved app globals for template deployments")
        
        return current_app.template_deployments, save_deployment_history, inventory
        
    except Exception as e:
        logger.error(f"Failed to get app globals: {str(e)}")
        logger.exception("Full exception details:")
        
        # Return fallback objects
        template_deployments_fallback = {}
        
        def fallback_save():
            logger.debug("Fallback save_deployment_history called")
            pass
        
        inventory = {"vms": [], "databases": [], "db_connections": [], "helm_upgrades": [], "ansible_playbooks": []}
        
        return template_deployments_fallback, fallback_save, inventory

def log_template_message(deployment_id, message):
    """Log message specifically for template deployments"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_message = f"[{timestamp}] {message}"
    
    logger.info(f"[{deployment_id}] {message}")
    
    # Store in template deployments
    if deployment_id in current_app.template_deployments:
        if 'logs' not in current_app.template_deployments[deployment_id]:
            current_app.template_deployments[deployment_id]['logs'] = []
        current_app.template_deployments[deployment_id]['logs'].append(formatted_message)

def load_inventory_files():
    """Load inventory files with fallbacks"""
    try:
        logger.debug("Loading inventory files")
        
        # Load main inventory
        inventory = {}
        if os.path.exists(INVENTORY_FILE):
            with open(INVENTORY_FILE, 'r') as f:
                inventory = json.load(f)
            logger.debug(f"Loaded inventory: {len(inventory.get('vms', []))} VMs")
        else:
            inventory = {
                "vms": [{"name": "batch1", "ip": "10.172.145.204"}],
                "databases": ["db1"],
                "helm_upgrades": [{"pod_name": "avm1", "command": "helmFU.Sh -f avm1 -t upgrade"}],
                "ansible_playbooks": [{"name": "tc1_helm_values_creation_play.yml", "path": "/etc/ansible/playbooks/"}]
            }
            logger.debug("Using fallback inventory")
        
        # Load database inventory
        db_inventory = {}
        if os.path.exists(DB_INVENTORY_FILE):
            with open(DB_INVENTORY_FILE, 'r') as f:
                db_inventory = json.load(f)
            logger.debug(f"Loaded db_inventory: {len(db_inventory.get('db_connections', []))} connections")
        else:
            db_inventory = {
                "db_connections": [
                    {"hostname": "10.172.145.204", "port": "5400", "users": ["xpidbo1cfg", "postgres"], "connection_name": "app_db"}
                ],
                "db_users": ["xpidbo1cfg", "postgres"]
            }
            logger.debug("Using fallback db_inventory")
        
        # Merge inventories
        inventory.update(db_inventory)
        return inventory
        
    except Exception as e:
        logger.error(f"Error loading inventory: {str(e)}")
        return {
            "vms": [{"name": "batch1", "ip": "10.172.145.204"}],
            "databases": ["db1"],
            "db_connections": [{"hostname": "10.172.145.204", "port": "5400", "users": ["xpidbo1cfg"], "connection_name": "app_db"}],
            "helm_upgrades": [{"pod_name": "avm1", "command": "helmFU.Sh -f avm1 -t upgrade"}],
            "ansible_playbooks": [{"name": "tc1_helm_values_creation_play.yml", "path": "/etc/ansible/playbooks/"}]
        }

def load_template(template_name):
    """Load template from the templates directory"""
    try:
        logger.debug(f"Loading template: {template_name}")
        template_path = os.path.join(TEMPLATE_DIR, template_name)
        
        if not os.path.exists(template_path):
            logger.warning(f"Template not found: {template_path}")
            return None
        
        with open(template_path, 'r') as f:
            template = json.load(f)
        
        logger.debug(f"Template loaded successfully: {template.get('metadata', {}).get('ft_number', 'unknown')}")
        return template
    except Exception as e:
        logger.error(f"Error loading template: {str(e)}")
        return None

def save_template_deployment_history():
    """Save template deployment history to a separate file"""
    try:
        if not hasattr(current_app, 'template_deployments'):
            return
            
        os.makedirs(DEPLOYMENT_LOGS_DIR, exist_ok=True)
        history_file = os.path.join(DEPLOYMENT_LOGS_DIR, 'template_deployment_history.json')
        
        with open(history_file, 'w') as f:
            json.dump(current_app.template_deployments, f, indent=2, default=str)
        
        logger.debug(f"Saved template deployment history to {history_file}")
    except Exception as e:
        logger.error(f"Error saving template deployment history: {str(e)}")

@deploy_template_bp.route('/api/templates', methods=['GET'])
def list_templates():
    """List available deployment templates"""
    try:
        logger.debug("Listing available templates")
        templates = []
        if os.path.exists(TEMPLATE_DIR):
            for file_name in os.listdir(TEMPLATE_DIR):
                if file_name.endswith('.json'):
                    try:
                        template = load_template(file_name)
                        if template:
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
        else:
            logger.warning(f"Template directory does not exist: {TEMPLATE_DIR}")

        logger.debug(f"Found {len(templates)} templates")
        return jsonify({"templates": templates})
    except Exception as e:
        logger.error(f"Failed to list templates: {str(e)}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/template/<template_name>', methods=['GET'])
def get_template_details(template_name):
    """Get details of a specific template"""
    try:
        logger.debug(f"Getting template details for: {template_name}")
        template = load_template(template_name)
        if template:
            return jsonify(template)
        else:
            return jsonify({"error": "Template not found"}), 404
    except Exception as e:
        logger.error(f"Failed to get template details: {str(e)}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
    """Start template deployment"""
    deployment_id = None
    try:
        logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
        data = request.json
        logger.debug(f"Request data: {data}")
        
        template_name = data.get('template')
        ft_number = data.get('ft_number', '')
        variables = data.get('variables', {})
        
        logger.info(f"Template deployment request: template={template_name}, ft_number={ft_number}")
        
        if not template_name:
            logger.error("Missing template name for template deployment")
            return jsonify({"error": "Missing template name"}), 400
        
        # Get shared objects from main app
        template_deployments, save_deployment_history, inventory = get_app_globals()
        logger.debug("Successfully got app globals")
        
        # Generate a unique deployment ID
        deployment_id = str(uuid.uuid4())
        logger.info(f"Generated deployment ID: {deployment_id}")
        
        # Store deployment information in the template deployments dictionary
        deployment_data = {
            "id": deployment_id,
            "template": template_name,
            "ft_number": ft_number,
            "variables": variables,
            "status": "running",
            "timestamp": time.time(),
            "logs": [],
            "logged_in_user": "infadm"
        }
        
        # Store in template deployments
        current_app.template_deployments[deployment_id] = deployment_data
        logger.info(f"Stored template deployment. Total: {len(current_app.template_deployments)}")
        
        # Log initial message
        log_template_message(deployment_id, f"Template deployment initiated: {template_name}")
        logger.info(f"Logged initial message for template deployment {deployment_id}")
        
        # Save template deployment history
        try:
            save_template_deployment_history()
            logger.debug("Saved template deployment history")
        except Exception as save_e:
            logger.warning(f"Failed to save template deployment history: {str(save_e)}")
        
        # Start deployment in a separate thread
        logger.info(f"Creating background thread for template deployment {deployment_id}")
        try:
            deployment_thread = threading.Thread(
                target=process_template_deployment_wrapper, 
                args=(deployment_id, template_name, ft_number, variables),
                daemon=True,
                name=f"template-deploy-{deployment_id[:8]}"
            )
            deployment_thread.start()
            logger.info(f"Background thread '{deployment_thread.name}' started successfully")
            
        except Exception as thread_e:
            logger.error(f"Failed to create/start thread: {str(thread_e)}")
            if deployment_id in current_app.template_deployments:
                current_app.template_deployments[deployment_id]["status"] = "failed"
            log_template_message(deployment_id, f"ERROR: Failed to start deployment thread: {str(thread_e)}")
            save_template_deployment_history()
            return jsonify({"error": f"Failed to start deployment: {str(thread_e)}"}), 500
        
        logger.info(f"Template deployment initiated with ID: {deployment_id}")
        return jsonify({"deploymentId": deployment_id})
        
    except Exception as e:
        logger.error(f"Error starting template deployment: {str(e)}")
        logger.exception("Full exception details:")
        if deployment_id:
            try:
                if deployment_id in current_app.template_deployments:
                    current_app.template_deployments[deployment_id]["status"] = "failed"
                log_template_message(deployment_id, f"ERROR: {str(e)}")
                save_template_deployment_history()
            except:
                pass
        return jsonify({"error": str(e)}), 500

def process_template_deployment_wrapper(deployment_id, template_name, ft_number, variables):
    """Wrapper function to handle exceptions in the deployment thread"""
    try:
        logger.info(f"=== WRAPPER: Starting template deployment thread for {deployment_id} ===")
        
        with current_app.app_context():
            template_deployments, save_deployment_history, inventory = get_app_globals()
            process_template_deployment(deployment_id, template_name, ft_number, variables, template_deployments, save_deployment_history, inventory)
    except Exception as e:
        logger.error(f"=== WRAPPER: Exception in template deployment thread {deployment_id}: {str(e)} ===")
        logger.exception("Full wrapper exception details:")
        try:
            with current_app.app_context():
                log_template_message(deployment_id, f"ERROR: Deployment thread failed: {str(e)}")
                if deployment_id in current_app.template_deployments:
                    current_app.template_deployments[deployment_id]["status"] = "failed"
                save_template_deployment_history()
        except Exception as cleanup_e:
            logger.error(f"Failed to update deployment status after thread error: {str(cleanup_e)}")

def process_template_deployment(deployment_id, template_name, ft_number, variables, template_deployments, save_deployment_history, inventory):
    """Process template deployment in a separate thread"""
    try:
        logger.info(f"=== STARTING TEMPLATE DEPLOYMENT PROCESSING: {deployment_id} ===")
        
        if deployment_id not in current_app.template_deployments:
            logger.error(f"Template deployment ID {deployment_id} not found")
            return
            
        logger.info(f"Processing template deployment: {template_name}")
        log_template_message(deployment_id, f"Starting template deployment: {template_name}")
        
        # Load template
        template = load_template(template_name)
        if not template:
            raise Exception(f"Failed to load template: {template_name}")
        
        log_template_message(deployment_id, f"Loaded template: {template_name}")
        
        # Process deployment steps
        steps = template.get("steps", [])
        log_template_message(deployment_id, f"Processing {len(steps)} deployment steps")
        logger.info(f"Processing {len(steps)} deployment steps")
        
        for i, step in enumerate(sorted(steps, key=lambda x: x.get('order', 0)), 1):
            try:
                step_type = step.get("type")
                step_order = step.get("order", i)
                step_description = step.get("description", "")
                
                log_template_message(deployment_id, f"Executing step {step_order}: {step_description}")
                logger.info(f"[{deployment_id}] Executing step {step_order}: {step_type}")
                
                # Execute different step types
                if step_type == "file_deployment":
                    execute_file_deployment(deployment_id, step, inventory)
                elif step_type == "sql_deployment":
                    execute_sql_deployment(deployment_id, step, inventory)
                elif step_type == "service_restart":
                    execute_service_restart(deployment_id, step, inventory)
                elif step_type == "ansible_playbook":
                    execute_ansible_playbook(deployment_id, step, inventory)
                elif step_type == "helm_upgrade":
                    execute_helm_upgrade(deployment_id, step, inventory)
                else:
                    log_template_message(deployment_id, f"WARNING: Unknown step type: {step_type}")
                
                log_template_message(deployment_id, f"Completed step {step_order}")
                time.sleep(2)  # Delay between steps
                
            except Exception as e:
                error_msg = f"Failed to execute step {step_order}: {str(e)}"
                log_template_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                current_app.template_deployments[deployment_id]["status"] = "failed"
                save_template_deployment_history()
                return
        
        # If we get here, all steps completed successfully
        log_template_message(deployment_id, "SUCCESS: Template deployment completed successfully")
        current_app.template_deployments[deployment_id]["status"] = "success"
        logger.info(f"Template deployment {deployment_id} completed successfully")
        save_template_deployment_history()
        
    except Exception as e:
        error_msg = f"Unexpected error during template deployment: {str(e)}"
        logger.error(f"[{deployment_id}] {error_msg}")
        logger.exception("Full exception details:")
        
        try:
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            current_app.template_deployments[deployment_id]["status"] = "failed"
            save_template_deployment_history()
        except:
            logger.error("Failed to update deployment status after error")

def execute_file_deployment(deployment_id, step, inventory):
    """Execute file deployment step using Ansible"""
    try:
        logger.info(f"[{deployment_id}] Starting file deployment step")
        log_template_message(deployment_id, f"Starting file deployment step")
        
        files = step.get("files", [])
        ft_number = step.get("ftNumber", "")
        target_path = step.get("targetPath", "/tmp")
        target_user = step.get("targetUser", "infadm")
        target_vms = step.get("targetVMs", ["batch1"])
        
        log_template_message(deployment_id, f"Files: {files}, Target: {target_path}, User: {target_user}, VMs: {target_vms}")
        
        # Create ansible inventory
        inventory_content = "[file_targets]\n"
        for vm_name in target_vms:
            vm_info = next((v for v in inventory.get("vms", []) if v.get("name") == vm_name), None)
            if vm_info:
                inventory_content += f"{vm_name} ansible_host={vm_info['ip']} ansible_user=infadm ansible_ssh_private_key_file=/app/ssh-keys/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
            else:
                log_template_message(deployment_id, f"WARNING: VM {vm_name} not found in inventory")
                inventory_content += f"{vm_name} ansible_host=10.172.145.204 ansible_user=infadm ansible_ssh_private_key_file=/app/ssh-keys/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
        
        # Write inventory to temp file
        inventory_file = f"/tmp/inventory_{deployment_id}"
        with open(inventory_file, 'w') as f:
            f.write(inventory_content)
        
        # Create ansible playbook for file deployment
        playbook_content = f"""---
- name: File deployment for {ft_number}
  hosts: file_targets
  gather_facts: false
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      
    - name: Create target directory
      ansible.builtin.file:
        path: {target_path}
        state: directory
        owner: {target_user}
        mode: '0755'
      become: yes
      
"""
        
        # Add tasks for each file
        for file_name in files:
            source_path = f"/app/fixfiles/{ft_number}/{file_name}"
            playbook_content += f"""    - name: Create backup of {file_name}
      ansible.builtin.copy:
        src: {target_path}/{file_name}
        dest: {target_path}/{file_name}.bak.{{{{ ansible_date_time.epoch }}}}
        remote_src: yes
      ignore_errors: yes
      become: yes
      
    - name: Copy {file_name} to target
      ansible.builtin.copy:
        src: {source_path}
        dest: {target_path}/{file_name}
        owner: {target_user}
        mode: '0644'
      become: yes
      
"""
        
        playbook_file = f"/tmp/playbook_{deployment_id}.yml"
        with open(playbook_file, 'w') as f:
            f.write(playbook_content)
        
        log_template_message(deployment_id, f"Created Ansible playbook and inventory files")
        
        # Execute ansible playbook
        cmd = ["ansible-playbook", "-i", inventory_file, playbook_file, "-v"]
        log_template_message(deployment_id, f"Executing: {' '.join(cmd)}")
        
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=300)
        
        # Log output
        if result.stdout:
            log_template_message(deployment_id, "=== ANSIBLE OUTPUT ===")
            for line in result.stdout.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        if result.stderr:
            log_template_message(deployment_id, "=== ANSIBLE STDERR ===")
            for line in result.stderr.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        # Clean up temp files
        try:
            os.remove(inventory_file)
            os.remove(playbook_file)
        except:
            pass
        
        if result.returncode == 0:
            log_template_message(deployment_id, f"File deployment completed successfully")
        else:
            error_msg = f"File deployment failed with return code: {result.returncode}"
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"File deployment failed: {str(e)}"
        log_template_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        raise

def execute_sql_deployment(deployment_id, step, inventory):
    """Execute SQL deployment step"""
    try:
        logger.info(f"[{deployment_id}] Starting SQL deployment step")
        log_template_message(deployment_id, f"Starting SQL deployment step")
        
        files = step.get("files", [])
        ft_number = step.get("ftNumber", "")
        db_connection = step.get("dbConnection", "")
        db_user = step.get("dbUser", "")
        db_password = step.get("dbPassword", "")
        
        # Decode password if base64 encoded
        try:
            decoded_password = base64.b64decode(db_password).decode('utf-8')
            db_password = decoded_password
        except:
            pass  # Use password as-is if not base64
        
        log_template_message(deployment_id, f"SQL Files: {files}, DB Connection: {db_connection}, User: {db_user}")
        
        # Find database connection info
        db_info = None
        for conn in inventory.get("db_connections", []):
            if conn.get("connection_name") == db_connection:
                db_info = conn
                break
        
        if not db_info:
            log_template_message(deployment_id, f"WARNING: Database connection '{db_connection}' not found, using first available")
            db_info = inventory.get("db_connections", [{}])[0] if inventory.get("db_connections") else {}
        
        hostname = db_info.get("hostname", "localhost")
        port = db_info.get("port", "5432")
        
        log_template_message(deployment_id, f"Connecting to database: {hostname}:{port}")
        
        # Execute SQL files
        for sql_file in files:
            sql_path = f"/app/fixfiles/{ft_number}/{sql_file}"
            
            if not os.path.exists(sql_path):
                log_template_message(deployment_id, f"WARNING: SQL file not found: {sql_path}")
                continue
            
            log_template_message(deployment_id, f"Executing SQL file: {sql_file}")
            
            # Use psql to execute SQL
            cmd = [
                "psql",
                f"postgresql://{db_user}:{db_password}@{hostname}:{port}/postgres",
                "-f", sql_path,
                "-v", "ON_ERROR_STOP=1"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.stdout:
                log_template_message(deployment_id, f"SQL Output: {result.stdout}")
            
            if result.stderr:
                log_template_message(deployment_id, f"SQL Stderr: {result.stderr}")
            
            if result.returncode == 0:
                log_template_message(deployment_id, f"SQL file {sql_file} executed successfully")
            else:
                error_msg = f"SQL file {sql_file} execution failed with return code: {result.returncode}"
                log_template_message(deployment_id, f"ERROR: {error_msg}")
                raise Exception(error_msg)
        
        log_template_message(deployment_id, f"SQL deployment completed successfully")
        
    except Exception as e:
        error_msg = f"SQL deployment failed: {str(e)}"
        log_template_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        raise

def execute_service_restart(deployment_id, step, inventory):
    """Execute service operation step using Ansible"""
    try:
        logger.info(f"[{deployment_id}] Starting service restart step")
        log_template_message(deployment_id, f"Starting service restart step")
        
        service = step.get("service", "docker")
        operation = step.get("operation", "restart")
        target_vms = step.get("targetVMs", ["batch1"])
        
        log_template_message(deployment_id, f"Service: {service}, Operation: {operation}, Target VMs: {target_vms}")
        
        # Create ansible inventory
        inventory_content = "[service_targets]\n"
        for vm_name in target_vms:
            vm_info = next((v for v in inventory.get("vms", []) if v.get("name") == vm_name), None)
            if vm_info:
                inventory_content += f"{vm_name} ansible_host={vm_info['ip']} ansible_user=infadm ansible_ssh_private_key_file=/app/ssh-keys/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
            else:
                log_template_message(deployment_id, f"WARNING: VM {vm_name} not found in inventory")
                inventory_content += f"{vm_name} ansible_host=10.172.145.204 ansible_user=infadm ansible_ssh_private_key_file=/app/ssh-keys/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
        
        # Write inventory to temp file
        inventory_file = f"/tmp/inventory_{deployment_id}"
        with open(inventory_file, 'w') as f:
            f.write(inventory_content)
        
        # Create ansible playbook
        if operation == "status":
            playbook_content = f"""---
- name: Service {operation} operation for {service}
  hosts: service_targets
  gather_facts: false
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      
    - name: Check service status
      ansible.builtin.systemd:
        name: {service}
      register: service_result
      
    - name: Show service status
      ansible.builtin.debug:
        msg: "Service {{{{ ansible_facts['hostname'] }}}}: {service} is {{{{ service_result.status.ActiveState }}}}"
"""
        else:
            playbook_content = f"""---
- name: Service {operation} operation for {service}
  hosts: service_targets
  gather_facts: false
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      
    - name: Perform systemctl {operation} {service}
      ansible.builtin.systemd:
        name: {service}
        state: {'started' if operation == 'start' else 'stopped' if operation == 'stop' else 'restarted'}
      register: service_result
      
    - name: Show service status
      ansible.builtin.debug:
        msg: "Service {{{{ ansible_facts['hostname'] }}}}: {service} operation {operation} completed"
"""
        
        playbook_file = f"/tmp/playbook_{deployment_id}.yml"
        with open(playbook_file, 'w') as f:
            f.write(playbook_content)
        
        log_template_message(deployment_id, f"Created Ansible playbook and inventory files")
        
        # Execute ansible playbook
        cmd = ["ansible-playbook", "-i", inventory_file, playbook_file, "-v"]
        log_template_message(deployment_id, f"Executing: {' '.join(cmd)}")
        
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=120)
        
        # Log output
        if result.stdout:
            log_template_message(deployment_id, "=== ANSIBLE OUTPUT ===")
            for line in result.stdout.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        if result.stderr:
            log_template_message(deployment_id, "=== ANSIBLE STDERR ===")
            for line in result.stderr.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        # Clean up temp files
        try:
            os.remove(inventory_file)
            os.remove(playbook_file)
        except:
            pass
        
        if result.returncode == 0:
            log_template_message(deployment_id, f"Service {operation} operation completed successfully")
        else:
            error_msg = f"Service {operation} operation failed with return code: {result.returncode}"
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Service restart failed: {str(e)}"
        log_template_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        raise

def execute_ansible_playbook(deployment_id, step, inventory):
    """Execute Ansible playbook step"""
    try:
        logger.info(f"[{deployment_id}] Starting Ansible playbook step")
        log_template_message(deployment_id, f"Starting Ansible playbook step")
        
        playbook_name = step.get("playbook", "")
        
        log_template_message(deployment_id, f"Executing playbook: {playbook_name}")
        
        # Find playbook path from inventory
        playbook_info = None
        for pb in inventory.get("ansible_playbooks", []):
            if pb.get("name") == playbook_name:
                playbook_info = pb
                break
        
        if not playbook_info:
            log_template_message(deployment_id, f"WARNING: Playbook '{playbook_name}' not found in inventory")
            playbook_path = f"/etc/ansible/playbooks/{playbook_name}"
        else:
            playbook_path = os.path.join(playbook_info.get("path", "/etc/ansible/playbooks/"), playbook_name)
        
        log_template_message(deployment_id, f"Playbook path: {playbook_path}")
        
        if not os.path.exists(playbook_path):
            error_msg = f"Playbook file not found: {playbook_path}"
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
        # Execute ansible playbook
        cmd = ["ansible-playbook", playbook_path, "-v"]
        log_template_message(deployment_id, f"Executing: {' '.join(cmd)}")
        
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=600)
        
        # Log output
        if result.stdout:
            log_template_message(deployment_id, "=== ANSIBLE PLAYBOOK OUTPUT ===")
            for line in result.stdout.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        if result.stderr:
            log_template_message(deployment_id, "=== ANSIBLE PLAYBOOK STDERR ===")
            for line in result.stderr.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        if result.returncode == 0:
            log_template_message(deployment_id, f"Ansible playbook executed successfully")
        else:
            error_msg = f"Ansible playbook execution failed with return code: {result.returncode}"
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Ansible playbook execution failed: {str(e)}"
        log_template_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        raise

def execute_helm_upgrade(deployment_id, step, inventory):
    """Execute Helm upgrade step"""
    try:
        logger.info(f"[{deployment_id}] Starting Helm upgrade step")
        log_template_message(deployment_id, f"Starting Helm upgrade step")
        
        helm_deployment_type = step.get("helmDeploymentType", "")
        
        log_template_message(deployment_id, f"Helm deployment type: {helm_deployment_type}")
        
        # Find helm command from inventory
        helm_command = None
        for helm_upgrade in inventory.get("helm_upgrades", []):
            if helm_upgrade.get("pod_name") == helm_deployment_type:
                helm_command = helm_upgrade.get("command")
                break
        
        if not helm_command:
            error_msg = f"Helm upgrade command not found for pod: {helm_deployment_type}"
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
        log_template_message(deployment_id, f"Executing helm command: {helm_command}")
        
        # Create ansible inventory for batch1 (assuming helm runs on batch1)
        inventory_content = "[helm_targets]\n"
        vm_info = next((v for v in inventory.get("vms", []) if v.get("name") == "batch1"), None)
        if vm_info:
            inventory_content += f"batch1 ansible_host={vm_info['ip']} ansible_user=infadm ansible_ssh_private_key_file=/app/ssh-keys/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
        else:
            inventory_content += f"batch1 ansible_host=10.172.145.204 ansible_user=infadm ansible_ssh_private_key_file=/app/ssh-keys/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
        
        # Write inventory to temp file
        inventory_file = f"/tmp/inventory_{deployment_id}"
        with open(inventory_file, 'w') as f:
            f.write(inventory_content)
        
        # Create ansible playbook for helm upgrade
        playbook_content = f"""---
- name: Helm upgrade for {helm_deployment_type}
  hosts: helm_targets
  gather_facts: false
  tasks:
    - name: Test connection
      ansible.builtin.ping:
      
    - name: Execute helm upgrade command
      ansible.builtin.shell: {helm_command}
      register: helm_result
      
    - name: Show helm output
      ansible.builtin.debug:
        msg: "{{{{ helm_result.stdout }}}}"
"""
        
        playbook_file = f"/tmp/playbook_{deployment_id}.yml"
        with open(playbook_file, 'w') as f:
            f.write(playbook_content)
        
        log_template_message(deployment_id, f"Created Ansible playbook for helm upgrade")
        
        # Execute ansible playbook
        cmd = ["ansible-playbook", "-i", inventory_file, playbook_file, "-v"]
        log_template_message(deployment_id, f"Executing: {' '.join(cmd)}")
        
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=600)
        
        # Log output
        if result.stdout:
            log_template_message(deployment_id, "=== HELM UPGRADE OUTPUT ===")
            for line in result.stdout.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        if result.stderr:
            log_template_message(deployment_id, "=== HELM UPGRADE STDERR ===")
            for line in result.stderr.splitlines():
                if line.strip():
                    log_template_message(deployment_id, line.strip())
        
        # Clean up temp files
        try:
            os.remove(inventory_file)
            os.remove(playbook_file)
        except:
            pass
        
        if result.returncode == 0:
            log_template_message(deployment_id, f"Helm upgrade completed successfully")
        else:
            error_msg = f"Helm upgrade failed with return code: {result.returncode}"
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Helm upgrade failed: {str(e)}"
        log_template_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        raise

@deploy_template_bp.route('/api/template-deploy/<deployment_id>/logs', methods=['GET'])
def get_template_deployment_logs(deployment_id):
    """Get template deployment logs"""
    try:
        logger.debug(f"Looking for template deployment: {deployment_id}")
        
        if deployment_id not in current_app.template_deployments:
            logger.warning(f"Template deployment {deployment_id} not found")
            return jsonify({"error": "Template deployment not found"}), 404
        
        deployment = current_app.template_deployments[deployment_id]
        logs = deployment.get('logs', [])
        
        return jsonify({
            "deploymentId": deployment_id,
            "status": deployment.get('status', 'unknown'),
            "logs": logs,
            "timestamp": deployment.get('timestamp'),
            "template": deployment.get('template', ''),
            "ft_number": deployment.get('ft_number', '')
        })
        
    except Exception as e:
        logger.error(f"Error fetching template deployment logs for {deployment_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/template-deployments/history', methods=['GET'])
def get_template_deployment_history():
    """Get template deployment history"""
    try:
        if not hasattr(current_app, 'template_deployments'):
            current_app.template_deployments = {}
        
        deployment_list = []
        for deployment_id, deployment in current_app.template_deployments.items():
            deployment_list.append({
                "id": deployment_id,
                "template": deployment.get("template", ""),
                "ft_number": deployment.get("ft_number", ""),
                "status": deployment.get("status", "unknown"),
                "timestamp": deployment.get("timestamp", 0),
                "logs": deployment.get("logs", []),
                "logged_in_user": deployment.get("logged_in_user", "")
            })
        
        deployment_list.sort(key=lambda x: x["timestamp"], reverse=True)
        return jsonify(deployment_list)
        
    except Exception as e:
        logger.error(f"Error fetching template deployment history: {str(e)}")
        return jsonify({"error": str(e)}), 500
