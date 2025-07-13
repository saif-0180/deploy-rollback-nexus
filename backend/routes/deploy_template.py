
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
TEMPLATE_LOGS_DIR = os.environ.get('TEMPLATE_LOGS_DIR', '/app/template_logs')
DEPLOYMENT_LOGS_DIR = os.environ.get('DEPLOYMENT_LOGS_DIR', '/app/logs')
TEMPLATE_DIR = "/app/deployment_templates"
INVENTORY_FILE = "/app/inventory/inventory.json"
DB_INVENTORY_FILE = "/app/inventory/db_inventory.json"
FIX_FILES_DIR = "/app/fixfiles"

# Global template deployments storage (separate from main deployments)
TEMPLATE_DEPLOYMENTS_STORAGE = {}
TEMPLATE_HISTORY_FILE = os.path.join(TEMPLATE_LOGS_DIR, 'template_deployments.json')

def load_template_deployments():
    """Load template deployments from file"""
    global TEMPLATE_DEPLOYMENTS_STORAGE
    try:
        if os.path.exists(TEMPLATE_HISTORY_FILE):
            with open(TEMPLATE_HISTORY_FILE, 'r') as f:
                TEMPLATE_DEPLOYMENTS_STORAGE = json.load(f)
            logger.debug(f"Loaded {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments from file")
        else:
            TEMPLATE_DEPLOYMENTS_STORAGE = {}
            logger.debug("No template deployment history file found, starting fresh")
    except Exception as e:
        logger.error(f"Error loading template deployments: {str(e)}")
        TEMPLATE_DEPLOYMENTS_STORAGE = {}

# def save_template_deployments():
#     """Save template deployments to file"""
#     try:
#         os.makedirs(TEMPLATE_LOGS_DIR, exist_ok=True)
#         with open(TEMPLATE_HISTORY_FILE, 'w') as f:
#             json.dump(TEMPLATE_DEPLOYMENTS_STORAGE, f, indent=2, default=str)
#         logger.debug(f"Saved {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments to file")
#     except Exception as e:
#         logger.error(f"Error saving template deployments: {str(e)}")

# def save_template_deployments():
#     """Save template deployments to file"""
#     try:
#         os.makedirs(TEMPLATE_LOGS_DIR, exist_ok=True)
        
#         # Create a backup of existing file before saving
#         if os.path.exists(TEMPLATE_HISTORY_FILE):
#             backup_file = f"{TEMPLATE_HISTORY_FILE}.backup"
#             import shutil
#             shutil.copy2(TEMPLATE_HISTORY_FILE, backup_file)
        
#         with open(TEMPLATE_HISTORY_FILE, 'w') as f:
#             json.dump(TEMPLATE_DEPLOYMENTS_STORAGE, f, indent=2, default=str)
#         logger.debug(f"Saved {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments to file")
        
#     except Exception as e:
#         logger.error(f"Error saving template deployments: {str(e)}")
#         # Try to restore from backup if save failed
#         backup_file = f"{TEMPLATE_HISTORY_FILE}.backup"
#         if os.path.exists(backup_file):
#             try:
#                 import shutil
#                 shutil.copy2(backup_file, TEMPLATE_HISTORY_FILE)
#                 logger.info("Restored template deployments from backup")
#             except:
#                 logger.error("Failed to restore from backup")

def save_template_deployments():
    """Save template deployments to file"""
    try:
        logger.debug("Ensuring logs directory exists...")
        os.makedirs(TEMPLATE_LOGS_DIR, exist_ok=True)
        logger.debug(f"Logs directory ready at {TEMPLATE_LOGS_DIR}")
        
        # Create a backup of existing file before saving
        if os.path.exists(TEMPLATE_HISTORY_FILE):
            logger.debug(f"Found existing template history file: {TEMPLATE_HISTORY_FILE}")
            backup_file = f"{TEMPLATE_HISTORY_FILE}.backup"
            import shutil
            shutil.copy2(TEMPLATE_HISTORY_FILE, backup_file)
            logger.debug(f"Created backup of template history: {backup_file}")
        else:
            logger.debug("No existing template history file found. Skipping backup step.")
        
        logger.debug(f"Saving template deployments to file: {TEMPLATE_HISTORY_FILE}")
        with open(TEMPLATE_HISTORY_FILE, 'w') as f:
            json.dump(TEMPLATE_DEPLOYMENTS_STORAGE, f, indent=2, default=str)
        logger.debug(f"Saved {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments to file")
        
    except Exception as e:
        logger.error(f"Error saving template deployments: {str(e)}")
        # Try to restore from backup if save failed
        backup_file = f"{TEMPLATE_HISTORY_FILE}.backup"
        if os.path.exists(backup_file):
            logger.debug("Attempting to restore from backup...")
            try:
                import shutil
                shutil.copy2(backup_file, TEMPLATE_HISTORY_FILE)
                logger.info("Restored template deployments from backup")
            except Exception as restore_error:
                logger.error(f"Failed to restore from backup: {str(restore_error)}")
        else:
            logger.debug("No backup file found to restore from.")

# def log_template_message(deployment_id, message):
#     """Log message for template deployments"""
#     timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
#     formatted_message = f"[{timestamp}] {message}"
    
#     logger.info(f"[{deployment_id}] {message}")
    
#     # Store in global template deployments
#     if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
#         if 'logs' not in TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]:
#             TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]['logs'] = []
#         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]['logs'].append(formatted_message)
        # save_template_deployments()

def log_template_message(deployment_id, message):
    """Log message for template deployments"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_message = f"[{timestamp}] {message}"
    
    logger.info(f"[{deployment_id}] {message}")
    
    # Store in global template deployments
    if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
        if 'logs' not in TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]:
            TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]['logs'] = []
        TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]['logs'].append(formatted_message)
        save_template_deployments()
    else:
        logger.warning(f"Deployment ID {deployment_id} not found in TEMPLATE_DEPLOYMENTS_STORAGE")

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

# Load template deployments on startup
# load_template_deployments()

try:
    load_template_deployments()
    logger.info(f"Template deployments loaded successfully. Count: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
except Exception as e:
    logger.error(f"Failed to load template deployments on startup: {str(e)}")
    TEMPLATE_DEPLOYMENTS_STORAGE = {}

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

# @deploy_template_bp.route('/api/deploy/template', methods=['POST'])
# def deploy_template():
#     """Start template deployment"""
#     deployment_id = None
#     try:
#         logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
#         data = request.json
#         logger.debug(f"Request data: {data}")
        
#         template_name = data.get('template')
#         ft_number = data.get('ft_number', '')
#         variables = data.get('variables', {})
        
#         logger.info(f"Template deployment request: template={template_name}, ft_number={ft_number}")
        
#         if not template_name:
#             logger.error("Missing template name for template deployment")
#             return jsonify({"error": "Missing template name"}), 400
        
#         # Generate a unique deployment ID
#         deployment_id = str(uuid.uuid4())
#         logger.info(f"Generated deployment ID: {deployment_id}")
        
#         # Store deployment information in global storage
#         deployment_data = {
#             "id": deployment_id,
#             "template": template_name,
#             "ft_number": ft_number,
#             "variables": variables,
#             "status": "running",
#             "timestamp": time.time(),
#             "logs": [],
#             "logged_in_user": "infadm"
#         }
        
#         # Store in global template deployments
#         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id] = deployment_data
#         save_template_deployments()
#         logger.info(f"Stored template deployment. Total template deployments: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        
#         # Log initial message
#         log_template_message(deployment_id, f"Template deployment initiated: {template_name}")
#         logger.info(f"Logged initial message for template deployment {deployment_id}")
        
#         # Start deployment in a separate thread
#         logger.info(f"Creating background thread for template deployment {deployment_id}")
#         deployment_thread = threading.Thread(
#             target=process_template_deployment_wrapper, 
#             args=(deployment_id, template_name, ft_number, variables),
#             daemon=True,
#             name=f"template-deploy-{deployment_id[:8]}"
#         )
#         deployment_thread.start()
#         logger.info(f"Background thread '{deployment_thread.name}' started successfully")
        
#         logger.info(f"Template deployment initiated with ID: {deployment_id}")
#         return jsonify({"deploymentId": deployment_id})
        
#     except Exception as e:
#         logger.error(f"Error starting template deployment: {str(e)}")
#         logger.exception("Full exception details:")
#         if deployment_id and deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
#             try:
#                 TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
#                 log_template_message(deployment_id, f"ERROR: {str(e)}")
#             except:
#                 pass
#         return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
    """Start template deployment"""
    deployment_id = None
    try:
        logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
        
        data = request.json
        logger.debug(f"Request data received: {data}")
        
        template_name = data.get('template')
        ft_number = data.get('ft_number', '')
        variables = data.get('variables', {})
        
        logger.info(f"Processing template deployment request: template='{template_name}', ft_number='{ft_number}'")
        
        if not template_name:
            logger.error("Missing template name in the request")
            return jsonify({"error": "Missing template name"}), 400
        
        # Generate a unique deployment ID
        deployment_id = str(uuid.uuid4())
        logger.info(f"Generated deployment ID: {deployment_id}")
        
        # Prepare deployment data
        deployment_data[deployment_id]= {
            "id": deployment_id,
            "template": template_name,
            "ft_number": ft_number,
            "variables": variables,
            "status": "running",
            "timestamp": time.time(),
            "logs": [],
            "logged_in_user": "infadm"
        }
        
        # Log the full deployment data dictionary
        logger.debug("Deployment data dictionary created:")
        logger.debug(json.dumps(deployment_data, indent=2, default=str))

        # Store in global template deployments
        TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id] = deployment_data
        logger.debug(f"Stored deployment in TEMPLATE_DEPLOYMENTS_STORAGE under key {deployment_id}")
        save_template_deployments()
        logger.info(f"Stored template deployment. Total count: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        
        # Log initial message in logs
        log_template_message(deployment_id, f"Template deployment initiated: {template_name}")
        logger.info(f"Initial log message recorded for deployment ID: {deployment_id}")
        
        # Start background thread
        logger.info(f"Starting background thread for template deployment ID: {deployment_id}")
        deployment_thread = threading.Thread(
            target=process_template_deployment_wrapper,
            args=(deployment_id, template_name, ft_number, variables),
            daemon=True,
            name=f"template-deploy-{deployment_id[:8]}"
        )
        deployment_thread.start()
        logger.info(f"Background thread '{deployment_thread.name}' started successfully")

        logger.info(f"Template deployment successfully initiated with ID: {deployment_id}")
        return jsonify({"deploymentId": deployment_id})

    except Exception as e:
        logger.error(f"Error during template deployment: {str(e)}")
        logger.exception("Full exception traceback:")

        # Attempt to mark the deployment as failed
        if deployment_id and deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
            try:
                TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
                log_template_message(deployment_id, f"ERROR: {str(e)}")
            except Exception as update_error:
                logger.error(f"Failed to update status or log error message for deployment {deployment_id}: {update_error}")
        
        return jsonify({"error": str(e)}), 500


def process_template_deployment_wrapper(deployment_id, template_name, ft_number, variables):
    """Wrapper function to handle exceptions in the deployment thread"""
    try:
        logger.info(f"=== WRAPPER: Starting template deployment thread for {deployment_id} ===")
        process_template_deployment(deployment_id, template_name, ft_number, variables)
    except Exception as e:
        logger.error(f"=== WRAPPER: Exception in template deployment thread {deployment_id}: {str(e)} ===")
        logger.exception("Full wrapper exception details:")
        try:
            log_template_message(deployment_id, f"ERROR: Deployment thread failed: {str(e)}")
            if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
                TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
                save_template_deployments()
        except Exception as cleanup_e:
            logger.error(f"Failed to update deployment status after thread error: {str(cleanup_e)}")

def process_template_deployment(deployment_id, template_name, ft_number, variables):
    """Process template deployment in a separate thread"""
    try:
        logger.info(f"=== STARTING TEMPLATE DEPLOYMENT PROCESSING: {deployment_id} ===")
        
        if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
            logger.error(f"Template deployment ID {deployment_id} not found")
            return
            
        logger.info(f"Processing template deployment: {template_name}")
        log_template_message(deployment_id, f"Starting template deployment: {template_name}")
        
        # Load template
        template = load_template(template_name)
        if not template:
            raise Exception(f"Failed to load template: {template_name}")
        
        log_template_message(deployment_id, f"Loaded template: {template_name}")
        
        # Load inventory
        inventory = load_inventory_files()
        
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
                    execute_file_deployment_step(deployment_id, step, inventory)
                elif step_type == "sql_deployment":
                    execute_sql_deployment_step(deployment_id, step, inventory)
                elif step_type == "service_restart":
                    execute_service_restart_step(deployment_id, step, inventory)
                elif step_type == "ansible_playbook":
                    execute_ansible_playbook_step(deployment_id, step, inventory)
                elif step_type == "helm_upgrade":
                    execute_helm_upgrade_step(deployment_id, step, inventory)
                else:
                    log_template_message(deployment_id, f"WARNING: Unknown step type: {step_type}")
                
                log_template_message(deployment_id, f"Completed step {step_order}")
                time.sleep(2)  # Delay between steps
                
            except Exception as e:
                error_msg = f"Failed to execute step {step_order}: {str(e)}"
                log_template_message(deployment_id, f"ERROR: {error_msg}")
                logger.error(f"[{deployment_id}] {error_msg}")
                TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
                save_template_deployments()
                return
        
        # If we get here, all steps completed successfully
        log_template_message(deployment_id, "SUCCESS: Template deployment completed successfully")
        TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "success"
        logger.info(f"Template deployment {deployment_id} completed successfully")
        save_template_deployments()
        
    except Exception as e:
        error_msg = f"Unexpected error during template deployment: {str(e)}"
        logger.error(f"[{deployment_id}] {error_msg}")
        logger.exception("Full exception details:")
        
        try:
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
            save_template_deployments()
        except:
            logger.error("Failed to update deployment status after error")

def execute_file_deployment_step(deployment_id, step, inventory):
    """Execute file deployment step"""
    try:
        files = step.get("files", [])
        ft_number = step.get("ftNumber", "")
        target_path = step.get("targetPath", "/tmp")
        target_user = step.get("targetUser", "infadm")
        target_vms = step.get("targetVMs", ["batch1"])
        
        log_template_message(deployment_id, f"File deployment: {files} to {target_path} on {target_vms}")
        
        # Execute file deployment using Ansible
        for vm in target_vms:
            vm_ip = "10.172.145.204"  # Default IP for batch1
            for vm_info in inventory.get("vms", []):
                if vm_info.get("name") == vm:
                    vm_ip = vm_info.get("ip", vm_ip)
                    break
            
            for file_name in files:
                source_file = os.path.join(FIX_FILES_DIR, ft_number, file_name)
                
                if not os.path.exists(source_file):
                    raise Exception(f"Source file not found: {source_file}")
                
                # Copy file using scp
                cmd = [
                    "scp", "-o", "StrictHostKeyChecking=no", "-i", "/app/ssh-keys/id_rsa",
                    source_file, f"{target_user}@{vm_ip}:{target_path}/{file_name}"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    log_template_message(deployment_id, f"File {file_name} deployed successfully to {vm}")
                else:
                    raise Exception(f"File deployment failed for {file_name}: {result.stderr}")
                    
    except Exception as e:
        logger.error(f"File deployment step failed: {str(e)}")
        raise

def execute_sql_deployment_step(deployment_id, step, inventory):
    """Execute SQL deployment step"""
    try:
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
            pass
        
        log_template_message(deployment_id, f"SQL deployment: {files} on connection {db_connection}")
        
        # Find database connection details
        db_info = None
        for conn in inventory.get("db_connections", []):
            if conn.get("connection_name") == db_connection:
                db_info = conn
                break
        
        if not db_info:
            raise Exception(f"Database connection {db_connection} not found")
        
        hostname = db_info.get("hostname", "localhost")
        port = db_info.get("port", "5432")
        
        for file_name in files:
            sql_file = os.path.join(FIX_FILES_DIR, ft_number, file_name)
            
            if not os.path.exists(sql_file):
                raise Exception(f"SQL file not found: {sql_file}")
            
            # Execute SQL file using psql
            cmd = [
                "psql", 
                f"postgresql://{db_user}:{db_password}@{hostname}:{port}/postgres",
                "-f", sql_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.stdout:
                log_template_message(deployment_id, f"SQL OUTPUT: {result.stdout}")
            
            if result.returncode == 0:
                log_template_message(deployment_id, f"SQL file {file_name} executed successfully")
            else:
                raise Exception(f"SQL execution failed for {file_name}: {result.stderr}")
                
    except Exception as e:
        logger.error(f"SQL deployment step failed: {str(e)}")
        raise

def execute_service_restart_step(deployment_id, step, inventory):
    """Execute service restart step"""
    try:
        service = step.get("service", "docker")
        operation = step.get("operation", "restart")
        target_vms = step.get("targetVMs", ["batch1"])
        
        log_template_message(deployment_id, f"Service operation: {operation} {service} on {target_vms}")
        
        for vm in target_vms:
            vm_ip = "10.172.145.204"  # Default IP for batch1
            for vm_info in inventory.get("vms", []):
                if vm_info.get("name") == vm:
                    vm_ip = vm_info.get("ip", vm_ip)
                    break
            
            # Execute systemctl command
            cmd = [
                "ssh", "-o", "StrictHostKeyChecking=no", "-i", "/app/ssh-keys/id_rsa",
                f"infadm@{vm_ip}", f"sudo systemctl {operation} {service}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.stdout:
                log_template_message(deployment_id, f"SERVICE OUTPUT: {result.stdout}")
            
            if result.returncode == 0:
                log_template_message(deployment_id, f"Service {operation} completed successfully on {vm}")
            else:
                raise Exception(f"Service {operation} failed on {vm}: {result.stderr}")
                
    except Exception as e:
        logger.error(f"Service restart step failed: {str(e)}")
        raise

def execute_ansible_playbook_step(deployment_id, step, inventory):
    """Execute Ansible playbook step"""
    try:
        playbook_name = step.get("playbook", "")
        
        log_template_message(deployment_id, f"Executing Ansible playbook: {playbook_name}")
        
        # Find playbook path from inventory
        playbook_path = f"/etc/ansible/playbooks/{playbook_name}"
        for pb in inventory.get("ansible_playbooks", []):
            if pb.get("name") == playbook_name:
                playbook_path = os.path.join(pb.get("path", "/etc/ansible/playbooks/"), playbook_name)
                break
        
        if not os.path.exists(playbook_path):
            raise Exception(f"Playbook file not found: {playbook_path}")
        
        # Execute ansible playbook
        cmd = ["ansible-playbook", playbook_path, "-v"]
        env_vars = os.environ.copy()
        env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=600)
        
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    log_template_message(deployment_id, f"ANSIBLE: {line.strip()}")
        
        if result.returncode == 0:
            log_template_message(deployment_id, "Ansible playbook executed successfully")
        else:
            raise Exception(f"Ansible playbook execution failed with return code: {result.returncode}")
            
    except Exception as e:
        logger.error(f"Ansible playbook step failed: {str(e)}")
        raise

def execute_helm_upgrade_step(deployment_id, step, inventory):
    """Execute Helm upgrade step"""
    try:
        helm_deployment_type = step.get("helmDeploymentType", "")
        
        log_template_message(deployment_id, f"Executing Helm upgrade: {helm_deployment_type}")
        
        # Find helm command from inventory
        helm_command = None
        for helm_upgrade in inventory.get("helm_upgrades", []):
            if helm_upgrade.get("pod_name") == helm_deployment_type:
                helm_command = helm_upgrade.get("command")
                break
        
        if not helm_command:
            raise Exception(f"Helm upgrade command not found for pod: {helm_deployment_type}")
        
        # Execute helm command on batch1
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", "/app/ssh-keys/id_rsa", 
               "infadm@10.172.145.204", helm_command]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    log_template_message(deployment_id, f"HELM: {line.strip()}")
        
        if result.returncode == 0:
            log_template_message(deployment_id, "Helm upgrade completed successfully")
        else:
            raise Exception(f"Helm upgrade failed with return code: {result.returncode}")
            
    except Exception as e:
        logger.error(f"Helm upgrade step failed: {str(e)}")
        raise

# @deploy_template_bp.route('/api/template-deploy/<deployment_id>/logs', methods=['GET'])
# def get_template_deployment_logs(deployment_id):
#     """Get template deployment logs"""
#     try:
#         logger.debug(f"Looking for template deployment: {deployment_id}")
        
#         if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
#             logger.warning(f"Template deployment {deployment_id} not found")
#             return jsonify({"error": "Template deployment not found"}), 404
        
#         deployment = TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]
#         logs = deployment.get('logs', [])
        
#         logger.debug(f"Found template deployment {deployment_id} with {len(logs)} log entries")
        
#         return jsonify({
#             "deploymentId": deployment_id,
#             "status": deployment.get('status', 'unknown'),
#             "logs": logs,
#             "timestamp": deployment.get('timestamp'),
#             "template": deployment.get('template', ''),
#             "ft_number": deployment.get('ft_number', '')
#         })
        
#     except Exception as e:
#         logger.error(f"Error fetching template deployment logs for {deployment_id}: {str(e)}")
#         return jsonify({"error": str(e)}), 500

@deploy_template_bp.route('/api/template-deploy/<deployment_id>/logs', methods=['GET'])
def get_template_deployment_logs(deployment_id):
    """Get template deployment logs"""
    try:
        logger.debug(f"Looking for template deployment: {deployment_id}")
        logger.debug(f"Available template deployments: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")
        
        # Try to reload deployments if not found
        if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
            logger.warning(f"Template deployment {deployment_id} not found, reloading from file")
            load_template_deployments()
        
        if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
            logger.warning(f"Template deployment {deployment_id} not found after reload")
            return jsonify({"error": "Template deployment not found"}), 404
        
        deployment = TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]
        logs = deployment.get('logs', [])
        
        logger.debug(f"Found template deployment {deployment_id} with {len(logs)} log entries")
        
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
        deployment_list = []
        for deployment_id, deployment in TEMPLATE_DEPLOYMENTS_STORAGE.items():
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
        logger.debug(f"Returning {len(deployment_list)} template deployments")
        return jsonify(deployment_list)
        
    except Exception as e:
        logger.error(f"Error fetching template deployment history: {str(e)}")
        return jsonify({"error": str(e)}), 500
