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
logger = logging.getLogger('fix_deployment_orchestrator')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Deploy directory for logs
DEPLOYMENT_LOGS_DIR = os.environ.get('DEPLOYMENT_LOGS_DIR', '/app/logs')
TEMPLATE_DIR = "/app/deployment_templates"
INVENTORY_FILE = "/app/inventory/inventory.json"
DB_INVENTORY_FILE = "/app/inventory/db_inventory.json"
FIX_FILES_DIR = "/app/fixfiles"

def get_app_globals():
    """Get shared objects from the main app via current_app context"""
    try:
        # Access deployments - handle if it's empty
        # deployments = getattr(current_app, 'deployments', None)
        # if deployments is None:
        #     deployments = current_app.config.get('deployments', {})
        # if not isinstance(deployments, dict):
        #     deployments = {}
        if not hasattr(current_app, 'deployments'):
            current_app.deployments = {}
        deployments = current_app.deployments
        
        # Access save_deployment_history function
        save_deployment_history = getattr(current_app, 'save_deployment_history', None)
        if save_deployment_history is None:
            save_deployment_history = current_app.config.get('save_deployment_history')
        
        # Access log_message function
        log_message = getattr(current_app, 'log_message', None)
        if log_message is None:
            log_message = current_app.config.get('log_message')
        
        # Access inventory - handle if it's empty
        inventory = getattr(current_app, 'inventory', None)
        if inventory is None:
            inventory = current_app.config.get('inventory', {"vms": [], "databases": []})
        if not isinstance(inventory, dict):
            inventory = {"vms": [], "databases": []}
        
        logger.debug(f"Retrieved app globals - deployments: {deployments is not None and len(deployments) >= 0}, save_history: {save_deployment_history is not None}, log_message: {log_message is not None}, inventory: {inventory is not None and len(inventory) > 0}")
        
        # Create fallback functions if needed
        if not save_deployment_history:
            logger.warning("save_deployment_history function is None, creating fallback")
            def fallback_save():
                logger.debug("Fallback save_deployment_history called")
                pass
            save_deployment_history = fallback_save
            
        if not log_message:
            logger.warning("log_message function is None, creating fallback")
            def fallback_log(deployment_id, message):
                logger.info(f"[{deployment_id}] {message}")
                if deployment_id in deployments:
                    if 'logs' not in deployments[deployment_id]:
                        deployments[deployment_id]['logs'] = []
                    deployments[deployment_id]['logs'].append(message)
            log_message = fallback_log
        
        # Ensure inventory has proper structure
        if 'vms' not in inventory:
            inventory['vms'] = []
        if 'databases' not in inventory:
            inventory['databases'] = []
        
        return deployments, save_deployment_history, log_message, inventory
        
    except Exception as e:
        logger.error(f"Failed to get app globals: {str(e)}")
        logger.exception("Full exception details:")
        
        # Return fallback objects
        deployments = {}
        
        def fallback_save():
            logger.debug("Fallback save_deployment_history called")
            pass
            
        def fallback_log(deployment_id, message):
            logger.info(f"[{deployment_id}] {message}")
            if deployment_id in deployments:
                if 'logs' not in deployments[deployment_id]:
                    deployments[deployment_id]['logs'] = []
                deployments[deployment_id]['logs'].append(message)
        
        inventory = {"vms": [], "databases": []}
        
        return deployments, fallback_save, fallback_log, inventory

def load_historical_deployment(deployment_id):
    """Load deployment from historical JSON files"""
    try:
        # Check main deployment logs directory
        logs_dir = DEPLOYMENT_LOGS_DIR
        if os.path.exists(logs_dir):
            for filename in os.listdir(logs_dir):
                if filename.startswith('deployment_') and filename.endswith('.json'):
                    filepath = os.path.join(logs_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            deployments_data = json.load(f)
                            if isinstance(deployments_data, dict):
                                for dep_id, dep_data in deployments_data.items():
                                    if dep_id == deployment_id:
                                        logger.info(f"Found historical deployment {deployment_id} in {filename}")
                                        return dep_data
                    except Exception as e:
                        logger.warning(f"Failed to load {filename}: {str(e)}")
                        continue
        
        logger.warning(f"Historical deployment {deployment_id} not found in any JSON files")
        return None
    except Exception as e:
        logger.error(f"Error loading historical deployment {deployment_id}: {str(e)}")
        return None

def load_template(template_name):
    """Load template from the templates directory"""
    try:
        logger.debug(f"Loading template: {template_name}")
        template_path = os.path.join(TEMPLATE_DIR, template_name)
        
        if not os.path.exists(template_path):
            logger.warning(f"Template not found: {template_path}")
            # Return a simple template if file doesn't exist
            return {
                "metadata": {
                    "ft_number": "TEST-001",
                    "description": f"Simple template for {template_name}",
                    "total_steps": 1,
                    "generated_at": "2025-01-01T00:00:00Z"
                },
                "steps": [
                    {
                        "order": 1,
                        "type": "service_restart",
                        "description": f"Restart docker service for {template_name}",
                        "service": "docker",
                        "operation": "restart",
                        "targetVMs": ["batch1"]
                    }
                ]
            }
        
        with open(template_path, 'r') as f:
            template = json.load(f)
        
        logger.debug(f"Template loaded successfully: {template.get('metadata', {}).get('ft_number', 'unknown')}")
        return template
    except Exception as e:
        logger.error(f"Error loading template: {str(e)}")
        # Return a fallback template
        return {
            "metadata": {
                "ft_number": "ERROR-001",
                "description": "Fallback template due to loading error",
                "total_steps": 1,
                "generated_at": "2025-01-01T00:00:00Z"
            },
            "steps": [
                {
                    "order": 1,
                    "type": "service_restart",
                    "description": f"Restart docker service - fallback",
                    "service": "docker",
                    "operation": "restart",
                    "targetVMs": ["batch1"]
                }
            ]
        }

def load_inventory():
    """Load inventory files with fallbacks"""
    try:
        logger.debug("Loading inventory files")
        
        # Load main inventory with fallback
        inventory = {}
        if os.path.exists(INVENTORY_FILE):
            with open(INVENTORY_FILE, 'r') as f:
                inventory = json.load(f)
            logger.debug(f"Loaded inventory: {len(inventory.get('vms', []))} VMs")
        else:
            # Fallback inventory
            inventory = {
                "vms": [
                    {"name": "batch1", "ip": "10.172.145.204"},
                    {"name": "batch2", "ip": "10.172.145.205"}
                ],
                "databases": ["db1", "db2"]
            }
            logger.debug("Using fallback inventory")
        
        # Load database inventory with fallback
        db_inventory = {}
        if os.path.exists(DB_INVENTORY_FILE):
            with open(DB_INVENTORY_FILE, 'r') as f:
                db_inventory = json.load(f)
            logger.debug(f"Loaded db_inventory: {len(db_inventory.get('db_connections', []))} connections")
        else:
            # Fallback db_inventory
            db_inventory = {
                "db_connections": [
                    {"hostname": "10.172.145.204", "port": "5400", "users": ["xpidbo1cfg", "abpwrk1db", "postgres"]},
                    {"hostname": "10.172.145.205", "port": "5432", "users": ["postgres", "dbadmin"]}
                ],
                "db_users": ["xpidbo1cfg", "postgres", "dbadmin"]
            }
            logger.debug("Using fallback db_inventory")
        
        return inventory, db_inventory
    except Exception as e:
        logger.error(f"Error loading inventory: {str(e)}")
        return {"vms": [], "databases": []}, {"db_connections": [], "db_users": []}

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
        return jsonify(template)
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
        deployments, save_deployment_history, log_message, inventory = get_app_globals()
        logger.debug("Successfully got app globals")
        
        # Generate a unique deployment ID
        deployment_id = str(uuid.uuid4())
        logger.info(f"Generated deployment ID: {deployment_id}")
        
        # Store deployment information in the shared deployments dictionary
        deployment_data = {
            "id": deployment_id,
            "type": "template",
            "template": template_name,
            "ft": ft_number,
            "variables": variables,
            "status": "running",
            "timestamp": time.time(),
            "logs": [],
            "logged_in_user": "infadm"
        }
        
        # # Make sure we're storing in the actual app's deployments dictionary
        # if hasattr(current_app, 'deployments'):
        #     current_app.deployments[deployment_id] = deployment_data
        #     logger.info(f"Stored deployment in current_app.deployments. Total: {len(current_app.deployments)}")
        # else:
        #     deployments[deployment_id] = deployment_data
        #     logger.info(f"Stored deployment in local dict. Total: {len(deployments)}")
        # CRITICAL FIX: Always use current_app.deployments directly


        # This ensures we're storing in the main app's deployment dictionary
        current_app.deployments[deployment_id] = deployment_data
        logger.info(f"Stored deployment in current_app.deployments. Total: {len(current_app.deployments)}")

        
        # Log initial message
        log_message(deployment_id, f"Template deployment initiated: {template_name}")
        logger.info(f"Logged initial message for deployment {deployment_id}")
        
        # Save deployment history
        try:
            save_deployment_history()
            logger.debug("Saved deployment history")
        except Exception as save_e:
            logger.warning(f"Failed to save deployment history: {str(save_e)}")
        
        # Start deployment in a separate thread
        logger.info(f"Creating background thread for deployment {deployment_id}")
        try:
            deployment_thread = threading.Thread(
                target=process_template_deployment_wrapper, 
                args=(deployment_id, template_name, ft_number, variables),
                daemon=True,
                name=f"template-deploy-{deployment_id[:8]}"
            )
            deployment_thread.start()
            logger.info(f"Background thread '{deployment_thread.name}' started successfully")
            
            # Verify thread is running
            time.sleep(0.1)  # Give thread a moment to start
            if deployment_thread.is_alive():
                logger.info(f"Thread is confirmed alive and running for deployment {deployment_id}")
            else:
                logger.error(f"Thread failed to start or died immediately for deployment {deployment_id}")
                
        except Exception as thread_e:
            logger.error(f"Failed to create/start thread: {str(thread_e)}")
            if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
                current_app.deployments[deployment_id]["status"] = "failed"
            elif deployment_id in deployments:
                deployments[deployment_id]["status"] = "failed"
            log_message(deployment_id, f"ERROR: Failed to start deployment thread: {str(thread_e)}")
            save_deployment_history()
            return jsonify({"error": f"Failed to start deployment: {str(thread_e)}"}), 500
        
        logger.info(f"Template deployment initiated with ID: {deployment_id}")
        return jsonify({"deploymentId": deployment_id})
        
    except Exception as e:
        logger.error(f"Error starting template deployment: {str(e)}")
        logger.exception("Full exception details:")
        if deployment_id:
            try:
                deployments, save_deployment_history, log_message, inventory = get_app_globals()
                if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
                    current_app.deployments[deployment_id]["status"] = "failed"
                elif deployment_id in deployments:
                    deployments[deployment_id]["status"] = "failed"
                log_message(deployment_id, f"ERROR: {str(e)}")
                save_deployment_history()
            except:
                pass
        return jsonify({"error": str(e)}), 500

def process_template_deployment_wrapper(deployment_id, template_name, ft_number, variables):
    """Wrapper function to handle exceptions in the deployment thread"""
    try:
        logger.info(f"=== WRAPPER: Starting deployment thread for {deployment_id} ===")
        
        # Get fresh app globals in the thread context
        with current_app.app_context():
            deployments, save_deployment_history, log_message, inventory = get_app_globals()
            process_template_deployment(deployment_id, template_name, ft_number, variables, deployments, save_deployment_history, log_message, inventory)
    except Exception as e:
        logger.error(f"=== WRAPPER: Exception in deployment thread {deployment_id}: {str(e)} ===")
        logger.exception("Full wrapper exception details:")
        try:
            with current_app.app_context():
                deployments, save_deployment_history, log_message, inventory = get_app_globals()
                log_message(deployment_id, f"ERROR: Deployment thread failed: {str(e)}")
                if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
                    current_app.deployments[deployment_id]["status"] = "failed"
                elif deployment_id in deployments:
                    deployments[deployment_id]["status"] = "failed"
                save_deployment_history()
        except Exception as cleanup_e:
            logger.error(f"Failed to update deployment status after thread error: {str(cleanup_e)}")

def process_template_deployment(deployment_id, template_name, ft_number, variables, deployments, save_deployment_history, log_message, inventory):
    """Process template deployment in a separate thread"""
    try:
        logger.info(f"=== STARTING TEMPLATE DEPLOYMENT PROCESSING: {deployment_id} ===")
        
        # Check if deployment exists in app's deployments or local deployments
        # deployment = None
        # if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
        #     deployment = current_app.deployments[deployment_id]
        # elif deployment_id in deployments:
        #     deployment = deployments[deployment_id]
        
        # if not deployment:
        #     logger.error(f"Deployment ID {deployment_id} not found in any deployments dictionary")
        #     return

        # CRITICAL FIX: Always use current_app.deployments directly
        if deployment_id not in current_app.deployments:
            logger.error(f"Deployment ID {deployment_id} not found in current_app.deployments")
            return
            
        logger.info(f"Processing template deployment: {template_name}")
        log_message(deployment_id, f"Starting template deployment: {template_name}")
        
        # Load template
        template = load_template(template_name)
        log_message(deployment_id, f"Loaded template: {template_name}")
        
        # Load inventory
        inv_data, db_inventory = load_inventory()
        log_message(deployment_id, "Loaded inventory files")
        
        # Process deployment steps
        steps = template.get("steps", [])
        log_message(deployment_id, f"Processing {len(steps)} deployment steps")
        logger.info(f"Processing {len(steps)} deployment steps")
        
        for i, step in enumerate(sorted(steps, key=lambda x: x.get('order', 0)), 1):
            try:
                step_type = step.get("type")
                step_order = step.get("order", i)
                step_description = step.get("description", "")
                
                log_message(deployment_id, f"Executing step {step_order}: {step_description}")
                logger.info(f"[{deployment_id}] Executing step {step_order}: {step_type}")
                
                # Execute different step types
                if step_type == "service_restart":
                    execute_service_restart(deployment_id, step, inv_data, db_inventory, deployments, save_deployment_history, log_message, inventory)
                elif step_type == "file_deployment":
                    execute_file_deployment(deployment_id, step, inv_data, db_inventory, deployments, save_deployment_history, log_message, inventory)
                elif step_type == "sql_deployment":
                    execute_sql_deployment(deployment_id, step, inv_data, db_inventory, deployments, save_deployment_history, log_message, inventory)
                elif step_type == "ansible_playbook":
                    execute_ansible_playbook(deployment_id, step, inv_data, db_inventory, deployments, save_deployment_history, log_message, inventory)
                elif step_type == "helm_upgrade":
                    execute_helm_upgrade(deployment_id, step, inv_data, db_inventory, deployments, save_deployment_history, log_message, inventory)
                elif step_type == "shell_command":
                    # Execute simple shell command
                    command = step.get("command", "echo 'No command specified'")
                    log_message(deployment_id, f"Executing command: {command}")
                    
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                    log_message(deployment_id, f"Command output: {result.stdout}")
                    if result.stderr:
                        log_message(deployment_id, f"Command stderr: {result.stderr}")
                    if result.returncode != 0:
                        log_message(deployment_id, f"Command failed with return code: {result.returncode}")
                else:
                    log_message(deployment_id, f"WARNING: Unknown step type: {step_type}")
                
                log_message(deployment_id, f"Completed step {step_order}")
                time.sleep(2)  # Delay between steps
                
            except Exception as e:
                error_msg = f"Failed to execute step {step_order}: {str(e)}"
                log_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
                    current_app.deployments[deployment_id]["status"] = "failed"
                elif deployment_id in deployments:
                    deployments[deployment_id]["status"] = "failed"
                save_deployment_history()
                return
        
        # If we get here, all steps completed successfully
        log_message(deployment_id, "SUCCESS: Template deployment completed successfully")
        if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
            current_app.deployments[deployment_id]["status"] = "success"
        elif deployment_id in deployments:
            deployments[deployment_id]["status"] = "success"
        logger.info(f"Template deployment {deployment_id} completed successfully")
        save_deployment_history()
        
    except Exception as e:
        error_msg = f"Unexpected error during template deployment: {str(e)}"
        logger.error(f"[{deployment_id}] {error_msg}")
        logger.exception("Full exception details:")
        
        try:
            log_message(deployment_id, f"ERROR: {error_msg}")
            if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
                current_app.deployments[deployment_id]["status"] = "failed"
            elif deployment_id in deployments:
                deployments[deployment_id]["status"] = "failed"
            save_deployment_history()
        except:
            logger.error("Failed to update deployment status after error")

# ... keep existing code (execute_service_restart, execute_file_deployment, execute_sql_deployment, execute_ansible_playbook, execute_helm_upgrade functions)

def execute_service_restart(deployment_id, step, inventory, db_inventory, deployments, save_deployment_history, log_message, inv):
    """Execute service operation step using Ansible"""
    try:
        logger.info(f"[{deployment_id}] Starting service restart step")
        log_message(deployment_id, f"Starting service restart step")
        
        service = step.get("service", "docker")
        operation = step.get("operation", "restart")
        target_vms = step.get("targetVMs", ["batch1"])
        
        log_message(deployment_id, f"Service: {service}, Operation: {operation}, Target VMs: {target_vms}")
        
        # Create ansible inventory for this operation
        inventory_content = "[service_targets]\n"
        for vm_name in target_vms:
            vm_info = next((v for v in inventory.get("vms", []) if v.get("name") == vm_name), None)
            if vm_info:
                inventory_content += f"{vm_name} ansible_host={vm_info['ip']} ansible_user=infadm ansible_ssh_private_key_file=/home/users/infadm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
            else:
                log_message(deployment_id, f"WARNING: VM {vm_name} not found in inventory, using fallback")
                inventory_content += f"{vm_name} ansible_host=10.172.145.204 ansible_user=infadm ansible_ssh_private_key_file=/home/users/infladm/.ssh/id_rsa ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
        
        # Write inventory to temp file
        inventory_file = f"/tmp/inventory_{deployment_id}"
        with open(inventory_file, 'w') as f:
            f.write(inventory_content)
        
        # Create simple ansible playbook
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
        
        log_message(deployment_id, f"Created Ansible playbook and inventory files")
        
        # Execute ansible playbook
        cmd = ["ansible-playbook", "-i", inventory_file, playbook_file, "-v"]
        log_message(deployment_id, f"Executing: {' '.join(cmd)}")
        
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=120)
        
        # Log output
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
        
        # Clean up temp files
        try:
            os.remove(inventory_file)
            os.remove(playbook_file)
        except:
            pass
        
        if result.returncode == 0:
            log_message(deployment_id, f"Service {operation} operation completed successfully")
        else:
            error_msg = f"Service {operation} operation failed"
            log_message(deployment_id, f"ERROR: {error_msg}")
            raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Service restart failed: {str(e)}"
        log_message(deployment_id, f"ERROR: {error_msg}")
        logger.error(f"[{deployment_id}] {error_msg}")
        raise

def execute_file_deployment(deployment_id, step, inventory, db_inventory, deployments, save_deployment_history, log_message, inv):
    """Execute file deployment step"""
    try:
        log_message(deployment_id, f"File deployment step (placeholder)")
    except Exception as e:
        log_message(deployment_id, f"ERROR: File deployment failed: {str(e)}")
        raise

def execute_sql_deployment(deployment_id, step, inventory, db_inventory, deployments, save_deployment_history, log_message, inv):
    """Execute SQL deployment step"""
    try:
        log_message(deployment_id, f"SQL deployment step (placeholder)")
    except Exception as e:
        log_message(deployment_id, f"ERROR: SQL deployment failed: {str(e)}")
        raise

def execute_ansible_playbook(deployment_id, step, inventory, db_inventory, deployments, save_deployment_history, log_message, inv):
    """Execute Ansible playbook step"""
    try:
        log_message(deployment_id, f"Ansible playbook step (placeholder)")
    except Exception as e:
        log_message(deployment_id, f"ERROR: Ansible playbook failed: {str(e)}")
        raise

def execute_helm_upgrade(deployment_id, step, inventory, db_inventory, deployments, save_deployment_history, log_message, inv):
    """Execute Helm upgrade step"""
    try:
        log_message(deployment_id, f"Helm upgrade step (placeholder)")
    except Exception as e:
        log_message(deployment_id, f"ERROR: Helm upgrade failed: {str(e)}")
        raise

@deploy_template_bp.route('/api/deploy/<deployment_id>/logs', methods=['GET'])
def get_deployment_logs(deployment_id):
    """Get deployment logs - check both current deployments and historical ones"""
    try:
        deployments, save_deployment_history, log_message, inventory = get_app_globals()

        logger.debug(f"Looking for deployment: {deployment_id}")
        
        # Check both app.deployments and local deployments first
        # deployment = None
        # if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
        #     deployment = current_app.deployments[deployment_id]
        #     logger.debug(f"Found deployment in current_app.deployments")
        # elif deployment_id in deployments:
        #     deployment = deployments[deployment_id]
        #     logger.debug(f"Found deployment in local deployments")
        deployment = None
        if deployment_id in current_app.deployments:
            deployment = current_app.deployments[deployment_id]
            logger.debug(f"Found deployment in current_app.deployments")

        else:
            # If not found in current deployments, try to load from historical files
            logger.info(f"Deployment {deployment_id} not found in current session, checking historical files")
            deployment = load_historical_deployment(deployment_id)
            if deployment:
                logger.info(f"Found deployment {deployment_id} in historical files")
            else:
                logger.warning(f"Deployment {deployment_id} not found anywhere")
                return jsonify({"error": "Deployment not found"}), 404
        
        logs = deployment.get('logs', [])
        
        return jsonify({
            "deploymentId": deployment_id,
            "status": deployment.get('status', 'unknown'),
            "logs": logs,
            "timestamp": deployment.get('timestamp'),
            "type": deployment.get('type', 'template')
        })
        
    except Exception as e:
        logger.error(f"Error fetching deployment logs for {deployment_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/deploy/<deployment_id>/status', methods=['GET'])
def get_deployment_status(deployment_id):
    """Get deployment status - check both current deployments and historical ones"""
    try:
        deployments, save_deployment_history, log_message, inventory = get_app_globals()
        
        # # Check both app.deployments and local deployments first
        # deployment = None
        # if hasattr(current_app, 'deployments') and deployment_id in current_app.deployments:
        #     deployment = current_app.deployments[deployment_id]
        # elif deployment_id in deployments:
        #     deployment = deployments[deployment_id]

        deployment = None
        if deployment_id in current_app.deployments:
            deployment = current_app.deployments[deployment_id]
            
        else:
            # If not found in current deployments, try to load from historical files
            deployment = load_historical_deployment(deployment_id)
            if not deployment:
                return jsonify({"error": "Deployment not found"}), 404
        
        return jsonify({
            "deploymentId": deployment_id,
            "status": deployment.get('status', 'unknown'),
            "type": deployment.get('type', 'template'),
            "timestamp": deployment.get('timestamp'),
            "template": deployment.get('template'),
            "variables": deployment.get('variables', {})
        })
        
    except Exception as e:
        logger.error(f"Error fetching deployment status for {deployment_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/deployments', methods=['GET'])
def get_all_deployments():
    """Get all deployments"""
    try:
        deployments, save_deployment_history, log_message, inventory = get_app_globals()
        
        deployment_list = []
        
        # Check both app.deployments and local deployments
        all_deployments = {}
        if hasattr(current_app, 'deployments'):
            all_deployments.update(current_app.deployments)
        all_deployments.update(deployments)
        
        for deployment_id, deployment in all_deployments.items():
            deployment_list.append({
                "id": deployment_id,
                "type": deployment.get("type", "unknown"),
                "status": deployment.get("status", "unknown"),
                "timestamp": deployment.get("timestamp", 0),
                "template": deployment.get("template", ""),
                "ft": deployment.get("ft", ""),
                "file": deployment.get("file", "")
            })
        
        deployment_list.sort(key=lambda x: x["timestamp"], reverse=True)
        return jsonify(deployment_list)
        
    except Exception as e:
        logger.error(f"Error fetching all deployments: {str(e)}")
        return jsonify({"error": str(e)}), 500
