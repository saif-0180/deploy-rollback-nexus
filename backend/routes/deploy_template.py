from flask import current_app, Blueprint, jsonify, request
import os
import json
import subprocess
import threading
import time
import uuid
import base64
import shutil
import tempfile
import logging
import traceback

# Get logger
logger = logging.getLogger('fix_deployment_orchestrator')
logging.basicConfig(level=logging.DEBUG)

# Create the blueprint
deploy_template_bp = Blueprint('deploy_template', __name__)

# Deploy directory for logs
TEMPLATE_LOGS_DIR = os.environ.get('TEMPLATE_LOGS_DIR', '/app/template_logs')
DEPLOYMENT_LOGS_DIR = os.environ.get('DEPLOYMENT_LOGS_DIR', '/app/logs')
TEMPLATE_DIR = "/app/deployment_templates"
INVENTORY_FILE = "/app/inventory/inventory.json"
DB_INVENTORY_FILE = "/app/inventory/db_inventory.json"
FIX_FILES_DIR = "/app/fixfiles"


def test_file_permissions():
    """Test if we can write to the template logs directory"""
    try:
        test_file = os.path.join(TEMPLATE_LOGS_DIR, 'test_write.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info(f"File permissions OK for {TEMPLATE_LOGS_DIR}")
        return True
    except Exception as e:
        logger.error(f"File permission error for {TEMPLATE_LOGS_DIR}: {e}")
        return False

def ensure_directories():
    """Create required directories if they don't exist"""
    directories = [
        TEMPLATE_LOGS_DIR,
        DEPLOYMENT_LOGS_DIR,
        TEMPLATE_DIR,
        os.path.dirname(INVENTORY_FILE),
        os.path.dirname(DB_INVENTORY_FILE),
        FIX_FILES_DIR
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to create directory {directory}: {e}")
        else:
            logger.debug(f"Directory exists: {directory}")


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

@deploy_template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
    from app import deployments, save_deployment_history
    """Start template deployment with extreme debugging"""
    try:
        logger.info("=" * 60)
        logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
        logger.info("=" * 60)
        
        # Validate request
        if not request.is_json:
            logger.error("Request content type is not JSON")
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.json
        if not data:
            logger.error("No JSON data in request body")
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Extract fields
        template_name = data.get('template')
        ft_number = data.get('ft_number', '')
        variables = data.get('variables', {})
        
        logger.info(f"Request details: template='{template_name}', ft_number='{ft_number}'")
        
        if not template_name:
            return jsonify({"error": "Template name is required"}), 400
        
        # Generate deployment ID
        deployment_id = str(uuid.uuid4())
        logger.info(f"Generated deployment ID: {deployment_id}")
        
        # Show storage state BEFORE adding
        logger.debug("BEFORE STORAGE:")
        logger.debug(f"  Current storage: {TEMPLATE_DEPLOYMENTS_STORAGE}")
        logger.debug(f"  Storage size: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        
        # Create deployment data
        deployments[deployment_id] = {
            "id": deployment_id,
            "template": template_name.strip(),
            "ft_number": ft_number,
            "variables": variables,
            "status": "running",
            "timestamp": time.time(),
            "logs": [],
            "logged_in_user": "admin",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
        
        # Save deployment history
        save_deployment_history()

        logger.debug(f"Created deployment data: {deployment_data}")

        threading.Thread(target=process_template_deployment_wrapper, args=(deployment_id, template_name, ft_number, variables)).start()
    
        logger.info(f"Template deployment initiated with ID: {deployment_id}")
        return jsonify({"deploymentId": deployment_id})
        
        # Store in memory first
        # logger.debug("STORING IN MEMORY...")
        # TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id] = deployment_data
        
        # # Show storage state AFTER adding
        # logger.debug("AFTER MEMORY STORAGE:")
        # logger.debug(f"  Current storage: {TEMPLATE_DEPLOYMENTS_STORAGE}")
        # logger.debug(f"  Storage size: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        # logger.debug(f"  Our deployment in storage: {deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE}")
        
        # # Save to file
        # logger.debug("SAVING TO FILE...")
        # save_success = save_template_deployments()
        
        # if not save_success:
        #     logger.error("FAILED TO SAVE TO FILE!")
        #     return jsonify({"error": "Failed to save deployment"}), 500
        
        # # Verify it's actually there
        # logger.debug("VERIFYING STORAGE...")
        # if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
        #     logger.debug(f"SUCCESS: Deployment {deployment_id} found in memory")
        # else:
        #     logger.error(f"CRITICAL: Deployment {deployment_id} NOT found in memory after storage!")
        #     return jsonify({"error": "Storage verification failed"}), 500
        
        # Add initial log
        # logger.debug("ADDING INITIAL LOG...")
        # timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        # log_entry = {
        #     "timestamp": timestamp,
        #     "message": f"Template deployment initiated: {template_name}"
        # }
        # TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["logs"].append(log_entry)
        
        # # Save again with log
        # logger.debug("SAVING WITH LOG...")
        # save_template_deployments()
        
        # Final verification
    #     logger.debug("FINAL VERIFICATION...")
    #     final_deployment = TEMPLATE_DEPLOYMENTS_STORAGE.get(deployment_id)
    #     if final_deployment:
    #         logger.debug(f"Final deployment data: {final_deployment}")
    #         logger.debug(f"Final deployment logs: {final_deployment.get('logs', [])}")
    #     else:
    #         logger.error("CRITICAL: Final deployment not found!")
        
    #     logger.info(f"Template deployment successfully created with ID: {deployment_id}")
    #     logger.info("=" * 60)
        
    #     return jsonify({
    #         "deploymentId": deployment_id,
    #         "status": "initiated",
    #         "message": "Template deployment started successfully"
    #     }), 202

    # except Exception as e:
    #     logger.error(f"CRITICAL ERROR during template deployment: {e}")
    #     logger.error(f"Full traceback: {traceback.format_exc()}")
    #     return jsonify({"error": str(e)}), 500

# def process_template_deployment_wrapper(deployment_id, template_name, ft_number, variables):

#     from app import log_message, deployments, save_deployment_history
#     """Wrapper function to handle exceptions in the deployment thread"""
#     try:
#         logger.info(f"=== WRAPPER: Starting template deployment thread for {deployment_id} ===")
#         process_template_deployment(deployment_id, template_name, ft_number, variables)
#     except Exception as e:
#         logger.error(f"=== WRAPPER: Exception in template deployment thread {deployment_id}: {str(e)} ===")
#         logger.exception("Full wrapper exception details:")
#         try:
#             log_template_message(deployment_id, f"ERROR: Deployment thread failed: {str(e)}")
#             if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
#                 TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
#                 save_template_deployments()
#         except Exception as cleanup_e:
#             logger.error(f"Failed to update deployment status after thread error: {str(cleanup_e)}")

def process_template_deployment(deployment_id, template_name, ft_number, variables):

    from app import log_message, deployments, save_deployment_history
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

# ... keep existing code (all execution step functions remain the same)

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

# writing my whole code myself one by one with same deployment dictionary from main app.py

# import os
# import json
# import subprocess
# import threading
# import time
# import uuid
# import base64
# import shutil
# import tempfile
# from flask import current_app, Blueprint, jsonify, request
# import logging
# import traceback
# # Create the blueprint
# deploy_template_bp = Blueprint('deploy_template', __name__)


# # Set up logging
# # logger = logging.getLogger('template_deployment')
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# # Deploy directory for logs
# TEMPLATE_LOGS_DIR = os.environ.get('TEMPLATE_LOGS_DIR', '/app/template_logs')
# DEPLOYMENT_LOGS_DIR = os.environ.get('DEPLOYMENT_LOGS_DIR', '/app/logs')
# TEMPLATE_DIR = "/app/deployment_templates"
# INVENTORY_FILE = "/app/inventory/inventory.json"
# DB_INVENTORY_FILE = "/app/inventory/db_inventory.json"
# FIX_FILES_DIR = "/app/fixfiles"

# # Global template deployments storage (separate from main deployments)
# TEMPLATE_DEPLOYMENTS_STORAGE = {}
# TEMPLATE_HISTORY_FILE = os.path.join(TEMPLATE_LOGS_DIR, 'template_deployments.json')

# # Thread lock for safe access to TEMPLATE_DEPLOYMENTS_STORAGE
# deployment_lock = threading.Lock()

# def initialize_template_deployments():
#     global TEMPLATE_DEPLOYMENTS_STORAGE
#     TEMPLATE_DEPLOYMENTS_STORAGE = load_template_deployments()

# def test_file_permissions():
#     """Test if we can write to the template logs directory"""
#     try:
#         test_file = os.path.join(TEMPLATE_LOGS_DIR, 'test_write.txt')
#         with open(test_file, 'w') as f:
#             f.write('test')
#         os.remove(test_file)
#         logger.info(f"File permissions OK for {TEMPLATE_LOGS_DIR}")
#         return True
#     except Exception as e:
#         logger.error(f"File permission error for {TEMPLATE_LOGS_DIR}: {e}")
#         return False

# def ensure_directories():
#     """Create required directories if they don't exist"""
#     directories = [
#         TEMPLATE_LOGS_DIR,
#         DEPLOYMENT_LOGS_DIR,
#         TEMPLATE_DIR,
#         os.path.dirname(INVENTORY_FILE),
#         os.path.dirname(DB_INVENTORY_FILE),
#         FIX_FILES_DIR
#     ]
    
#     for directory in directories:
#         if not os.path.exists(directory):
#             try:
#                 os.makedirs(directory, exist_ok=True)
#                 logger.info(f"Created directory: {directory}")
#             except Exception as e:
#                 logger.error(f"Failed to create directory {directory}: {e}")
#         else:
#             logger.debug(f"Directory exists: {directory}")




# def load_template_deployments():
#     """Load template deployments from file"""
#     global TEMPLATE_DEPLOYMENTS_STORAGE
#     try:
#         logger.debug(f"Loading template deployments from {TEMPLATE_HISTORY_FILE}")
        
#         if not os.path.exists(TEMPLATE_HISTORY_FILE):
#             logger.debug(f"No deployment file found at {TEMPLATE_HISTORY_FILE}. Creating empty storage.")
#             TEMPLATE_DEPLOYMENTS_STORAGE = {}
#             return TEMPLATE_DEPLOYMENTS_STORAGE

#         with open(TEMPLATE_HISTORY_FILE, 'r') as f:
#             content = f.read().strip()
#             if not content:
#                 logger.debug("Deployment file is empty. Creating empty storage.")
#                 TEMPLATE_DEPLOYMENTS_STORAGE = {}
#                 return TEMPLATE_DEPLOYMENTS_STORAGE
            
#             TEMPLATE_DEPLOYMENTS_STORAGE = json.loads(content)
#             logger.debug(f"Loaded {len(TEMPLATE_DEPLOYMENTS_STORAGE)} deployments from file.")
#             return TEMPLATE_DEPLOYMENTS_STORAGE
            
#     except Exception as e:
#         logger.error(f"Error loading template deployments: {e}")
#         TEMPLATE_DEPLOYMENTS_STORAGE = {}
#         return TEMPLATE_DEPLOYMENTS_STORAGE

# def load_template_deployments():
#     """Load template deployments from file"""
#     global TEMPLATE_DEPLOYMENTS_STORAGE
    
#     with deployment_lock:
#         try:
#             logger.debug(f"Loading template deployments from {TEMPLATE_HISTORY_FILE}")
            
#             if os.path.exists(TEMPLATE_HISTORY_FILE):
#                 with open(TEMPLATE_HISTORY_FILE, 'r') as f:
#                     content = f.read().strip()
#                     if content:
#                         TEMPLATE_DEPLOYMENTS_STORAGE = json.loads(content)
#                         logger.info(f"Loaded {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments from file")
#                         logger.debug(f"Loaded deployment IDs: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")
#                     else:
#                         logger.debug("Deployment file is empty. Creating empty storage.")
#                         TEMPLATE_DEPLOYMENTS_STORAGE = {}
#             else:
#                 logger.debug("Template deployments file does not exist, starting with empty storage")
#                 TEMPLATE_DEPLOYMENTS_STORAGE = {}
#         except Exception as e:
#             logger.error(f"Error loading template deployments: {e}")
#             TEMPLATE_DEPLOYMENTS_STORAGE = {}

def load_template_deployments():
    """Load template deployments from file"""
    global TEMPLATE_DEPLOYMENTS_STORAGE
    
    logger.debug("=" * 50)
    logger.debug("LOAD_TEMPLATE_DEPLOYMENTS CALLED")
    logger.debug(f"Loading from: {TEMPLATE_HISTORY_FILE}")
    
    try:
        if os.path.exists(TEMPLATE_HISTORY_FILE):
            logger.debug("File exists, reading...")
            with open(TEMPLATE_HISTORY_FILE, 'r') as f:
                content = f.read().strip()
                logger.debug(f"File content: '{content}'")
                
                if content:
                    TEMPLATE_DEPLOYMENTS_STORAGE = json.loads(content)
                    logger.info(f"Loaded {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments from file")
                    logger.debug(f"Loaded deployment IDs: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")
                else:
                    logger.debug("Deployment file is empty. Creating empty storage.")
                    TEMPLATE_DEPLOYMENTS_STORAGE = {}
        else:
            logger.debug("File does not exist, starting with empty storage")
            TEMPLATE_DEPLOYMENTS_STORAGE = {}
            
        logger.debug("=" * 50)
        
    except Exception as e:
        logger.error(f"Error loading template deployments: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        TEMPLATE_DEPLOYMENTS_STORAGE = {}

# def save_template_deployments():
#     """Save template deployments to file atomically"""
#     try:
#         logger.debug("Ensuring logs directory exists...")
#         os.makedirs(TEMPLATE_LOGS_DIR, exist_ok=True)
#         logger.debug(f"Logs directory ready at {TEMPLATE_LOGS_DIR}")
        
#         # Create backup if exists
#         if os.path.exists(TEMPLATE_HISTORY_FILE):
#             backup_file = f"{TEMPLATE_HISTORY_FILE}.backup"
#             shutil.copy2(TEMPLATE_HISTORY_FILE, backup_file)
#             logger.debug(f"Created backup of template history: {backup_file}")
#         else:
#             logger.debug("No existing template history file found. Skipping backup.")

#         # Write to a temp file
#         logger.debug("Writing to temporary file for atomic save...")
#         with tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(TEMPLATE_HISTORY_FILE)) as tmpfile:
#             json.dump(TEMPLATE_DEPLOYMENTS_STORAGE, tmpfile, indent=2, default=str)
#             temp_path = tmpfile.name
#             logger.debug(f"Template deployments written to temp file: {temp_path}")
        
#         # Replace original with temp
#         os.replace(temp_path, TEMPLATE_HISTORY_FILE)
#         logger.debug(f"Replaced {TEMPLATE_HISTORY_FILE} with new data.")
#         logger.info(f"Saved {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments to file")

#     except Exception as e:
#         logger.error(f"Error saving template deployments: {str(e)}")
#         backup_file = f"{TEMPLATE_HISTORY_FILE}.backup"
#         if os.path.exists(backup_file):
#             logger.debug("Attempting to restore from backup...")
#             try:
#                 shutil.copy2(backup_file, TEMPLATE_HISTORY_FILE)
#                 logger.info("Restored template deployments from backup.")
#             except Exception as restore_error:
#                 logger.error(f"Failed to restore from backup: {str(restore_error)}")
#         else:
#             logger.debug("No backup file found to restore from.")

# def save_template_deployments():
#     """Save template deployments to file"""
#     with deployment_lock:
#         try:
#             logger.debug(f"Saving {len(TEMPLATE_DEPLOYMENTS_STORAGE)} template deployments to {TEMPLATE_HISTORY_FILE}")
#             logger.debug(f"Deployment IDs being saved: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")
            
#             # Ensure directory exists
#             os.makedirs(os.path.dirname(TEMPLATE_HISTORY_FILE), exist_ok=True)
            
#             with open(TEMPLATE_HISTORY_FILE, 'w') as f:
#                 json.dump(TEMPLATE_DEPLOYMENTS_STORAGE, f, indent=2, default=str)
            
#             logger.debug(f"Successfully saved template deployments to file")
            
#             # Verify the save by reading back
#             with open(TEMPLATE_HISTORY_FILE, 'r') as f:
#                 saved_content = f.read().strip()
#                 if saved_content:
#                     saved_data = json.loads(saved_content)
#                     logger.debug(f"Verification: File now contains {len(saved_data)} deployments")
#                 else:
#                     logger.warning("Verification: File is empty after save!")
                    
#         except Exception as e:
#             logger.error(f"Error saving template deployments: {e}")
#             raise

def save_template_deployments():
    """Save template deployments to file with extensive debugging"""
    logger.debug("=" * 50)
    logger.debug("SAVE_TEMPLATE_DEPLOYMENTS CALLED")
    logger.debug(f"Current storage contents: {TEMPLATE_DEPLOYMENTS_STORAGE}")
    logger.debug(f"Storage size: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
    logger.debug(f"Target file: {TEMPLATE_HISTORY_FILE}")
    
    try:
        # Check if directory exists
        directory = os.path.dirname(TEMPLATE_HISTORY_FILE)
        if not os.path.exists(directory):
            logger.error(f"Directory does not exist: {directory}")
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        
        # Check permissions
        if not test_file_permissions():
            logger.error("Cannot write to template logs directory!")
            return False
        
        # Create the JSON content
        json_content = json.dumps(TEMPLATE_DEPLOYMENTS_STORAGE, indent=2, default=str)
        logger.debug(f"JSON content to save: {json_content}")
        
        # Write to file
        # with open(TEMPLATE_HISTORY_FILE, 'w') as f:
        #     f.write(json_content)
        with open(TEMPLATE_HISTORY_FILE, 'w') as f:
            f.write(json_content)
            f.flush()             # ✅ force flush buffer to file
            os.fsync(f.fileno())  # ✅ force sync file to disk (especially for Docker volumes)
                
        logger.debug("File write completed")

        with open(TEMPLATE_HISTORY_FILE, 'r') as f:
            verify_content = f.read().strip()
            if not verify_content:
                logger.critical("File was written but is empty. Aborting.")
            else:
                logger.debug("File written and verified successfully.")
        
        # Verify the save immediately
        if os.path.exists(TEMPLATE_HISTORY_FILE):
            file_size = os.path.getsize(TEMPLATE_HISTORY_FILE)
            logger.debug(f"File exists, size: {file_size} bytes")
            
            with open(TEMPLATE_HISTORY_FILE, 'r') as f:
                saved_content = f.read()
                logger.debug(f"File content: {saved_content}")
                
                if saved_content.strip():
                    saved_data = json.loads(saved_content)
                    logger.debug(f"Verification: File contains {len(saved_data)} deployments")
                    logger.debug(f"Verification: Deployment IDs in file: {list(saved_data.keys())}")
                    
                    # Check if our specific deployment is there
                    for dep_id, dep_data in saved_data.items():
                        logger.debug(f"Saved deployment {dep_id}: {dep_data}")
                else:
                    logger.error("CRITICAL: File is empty after save!")
        else:
            logger.error("CRITICAL: File does not exist after save!")
            
        logger.debug("=" * 50)
        return True
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR in save_template_deployments: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

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
#         save_template_deployments()
#     else:
#         logger.warning(f"Deployment ID {deployment_id} not found in TEMPLATE_DEPLOYMENTS_STORAGE")

# def log_template_message(deployment_id, message):
#     """Add a log message to a specific deployment"""
#     with deployment_lock:
#         if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
#             timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
#             log_entry = {
#                 "timestamp": timestamp,
#                 "message": message
#             }
#             TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["logs"].append(log_entry)
#             logger.debug(f"Added log message to deployment {deployment_id}: {message}")
#         else:
#             logger.warning(f"Attempted to log message to non-existent deployment {deployment_id}")
#             logger.debug(f"Available template deployments: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")

# def load_inventory_files():
#     """Load inventory files with fallbacks"""
#     try:
#         logger.debug("Loading inventory files")
        
#         # Load main inventory
#         inventory = {}
#         if os.path.exists(INVENTORY_FILE):
#             with open(INVENTORY_FILE, 'r') as f:
#                 inventory = json.load(f)
#             logger.debug(f"Loaded inventory: {len(inventory.get('vms', []))} VMs")
#         else:
#             inventory = {
#                 "vms": [{"name": "batch1", "ip": "10.172.145.204"}],
#                 "databases": ["db1"],
#                 "helm_upgrades": [{"pod_name": "avm1", "command": "helmFU.Sh -f avm1 -t upgrade"}],
#                 "ansible_playbooks": [{"name": "tc1_helm_values_creation_play.yml", "path": "/etc/ansible/playbooks/"}]
#             }
#             logger.debug("Using fallback inventory")
        
#         # Load database inventory
#         db_inventory = {}
#         if os.path.exists(DB_INVENTORY_FILE):
#             with open(DB_INVENTORY_FILE, 'r') as f:
#                 db_inventory = json.load(f)
#             logger.debug(f"Loaded db_inventory: {len(db_inventory.get('db_connections', []))} connections")
#         else:
#             db_inventory = {
#                 "db_connections": [
#                     {"hostname": "10.172.145.204", "port": "5400", "users": ["xpidbo1cfg", "postgres"], "connection_name": "app_db"}
#                 ],
#                 "db_users": ["xpidbo1cfg", "postgres"]
#             }
#             logger.debug("Using fallback db_inventory")
        
#         # Merge inventories
#         inventory.update(db_inventory)
#         return inventory
        
#     except Exception as e:
#         logger.error(f"Error loading inventory: {str(e)}")
#         return {
#             "vms": [{"name": "batch1", "ip": "10.172.145.204"}],
#             "databases": ["db1"],
#             "db_connections": [{"hostname": "10.172.145.204", "port": "5400", "users": ["xpidbo1cfg"], "connection_name": "app_db"}],
#             "helm_upgrades": [{"pod_name": "avm1", "command": "helmFU.Sh -f avm1 -t upgrade"}],
#             "ansible_playbooks": [{"name": "tc1_helm_values_creation_play.yml", "path": "/etc/ansible/playbooks/"}]
#         }

# def load_template(template_name):
#     """Load template from the templates directory"""
#     try:
#         logger.debug(f"Loading template: {template_name}")
#         template_path = os.path.join(TEMPLATE_DIR, template_name)
        
#         if not os.path.exists(template_path):
#             logger.warning(f"Template not found: {template_path}")
#             return None
        
#         with open(template_path, 'r') as f:
#             template = json.load(f)
        
#         logger.debug(f"Template loaded successfully: {template.get('metadata', {}).get('ft_number', 'unknown')}")
#         return template
#     except Exception as e:
#         logger.error(f"Error loading template: {str(e)}")
#         return None

# # Load template deployments on startup
# try:
#     load_template_deployments()
#     logger.info(f"Template deployments loaded successfully. Count: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
# except Exception as e:
#     logger.error(f"Failed to load template deployments on startup: {str(e)}")
#     TEMPLATE_DEPLOYMENTS_STORAGE = {}

# # @deploy_template_bp.route('/api/templates', methods=['GET'])
# # def list_templates():
# #     """List available deployment templates"""
# #     try:
# #         logger.debug("Listing available templates")
# #         templates = []
# #         if os.path.exists(TEMPLATE_DIR):
# #             for file_name in os.listdir(TEMPLATE_DIR):
# #                 if file_name.endswith('.json'):
# #                     try:
# #                         template = load_template(file_name)
# #                         if template:
# #                             templates.append({
# #                                 "name": file_name,
# #                                 "description": template.get('metadata', {}).get('description', ''),
# #                                 "ft_number": template.get('metadata', {}).get('ft_number', ''),
# #                                 "total_steps": template.get('metadata', {}).get('total_steps', len(template.get('steps', []))),
# #                                 "steps": [
# #                                     {
# #                                         "order": step.get('order'),
# #                                         "type": step.get('type'),
# #                                         "description": step.get('description', '')
# #                                     } for step in template.get('steps', [])
# #                                 ]
# #                             })
# #                     except Exception as e:
# #                         logger.warning(f"Failed to load template {file_name}: {str(e)}")
# #                         continue

# #         logger.debug(f"Found {len(templates)} templates")
# #         return jsonify({"templates": templates})
# #     except Exception as e:
# #         logger.error(f"Failed to list templates: {str(e)}")
# #         return jsonify({"error": str(e)}), 500

# # @deploy_template_bp.route('/api/template/<template_name>', methods=['GET'])
# # def get_template_details(template_name):
# #     """Get details of a specific template"""
# #     try:
# #         logger.debug(f"Getting template details for: {template_name}")
# #         template = load_template(template_name)
# #         if template:
# #             return jsonify(template)
# #         else:
# #             return jsonify({"error": "Template not found"}), 404
# #     except Exception as e:
# #         logger.error(f"Failed to get template details: {str(e)}")
# #         return jsonify({"error": str(e)}), 500

# # @deploy_template_bp.route('/api/deploy/template', methods=['POST'])
# # def deploy_template():
# #     """Start template deployment"""
# #     deployment_id = None
# #     try:
# #         logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
        
# #         data = request.json
# #         logger.debug(f"Request data received: {data}")
        
# #         template_name = data.get('template')
# #         ft_number = data.get('ft_number', '')
# #         variables = data.get('variables', {})
        
# #         logger.info(f"Processing template deployment request: template='{template_name}', ft_number='{ft_number}'")
        
# #         if not template_name:
# #             logger.error("Missing template name in the request")
# #             return jsonify({"error": "Missing template name"}), 400
        
# #         # Generate a unique deployment ID
# #         deployment_id = str(uuid.uuid4())
# #         logger.info(f"Generated deployment ID: {deployment_id}")
        
# #         # Prepare deployment data - FIXED SYNTAX ERROR HERE
# #         deployment_data = {
# #             "id": deployment_id,
# #             "template": template_name,
# #             "ft_number": ft_number,
# #             "variables": variables,
# #             "status": "running",
# #             "timestamp": time.time(),
# #             "logs": [],
# #             "logged_in_user": "infadm"
# #         }
        
# #         # Log the deployment data
# #         logger.debug("Deployment data dictionary created:")
# #         logger.debug(json.dumps(deployment_data, indent=2, default=str))

# #         # Store in global template deployments
# #         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id] = deployment_data
# #         logger.debug(f"Stored deployment in TEMPLATE_DEPLOYMENTS_STORAGE under key {deployment_id}")
# #         save_template_deployments()
# #         logger.info(f"Stored template deployment. Total count: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        
# #         # Log initial message in logs
# #         log_template_message(deployment_id, f"Template deployment initiated: {template_name}")
# #         logger.info(f"Initial log message recorded for deployment ID: {deployment_id}")
        
# #         # Start background thread
# #         logger.info(f"Starting background thread for template deployment ID: {deployment_id}")
# #         deployment_thread = threading.Thread(
# #             target=process_template_deployment_wrapper,
# #             args=(deployment_id, template_name, ft_number, variables),
# #             daemon=True,
# #             name=f"template-deploy-{deployment_id[:8]}"
# #         )
# #         deployment_thread.start()
# #         logger.info(f"Background thread '{deployment_thread.name}' started successfully")

# #         logger.info(f"Template deployment successfully initiated with ID: {deployment_id}")
# #         return jsonify({"deploymentId": deployment_id})

# #     except Exception as e:
# #         logger.error(f"Error during template deployment: {str(e)}")
# #         logger.exception("Full exception traceback:")

# #         # Attempt to mark the deployment as failed
# #         if deployment_id and deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
# #             try:
# #                 TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
# #                 log_template_message(deployment_id, f"ERROR: {str(e)}")
# #             except Exception as update_error:
# #                 logger.error(f"Failed to update status or log error message for deployment {deployment_id}: {update_error}")
        
# #         return jsonify({"error": str(e)}), 500

# # @deploy_template_bp.route('/api/deploy/template', methods=['POST'])
# # def deploy_template():
# #     """Start template deployment"""
# #     deployment_id = None
# #     try:
# #         logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
        
# #         # Validate request content type
# #         if not request.is_json:
# #             logger.error("Request content type is not JSON")
# #             return jsonify({"error": "Content-Type must be application/json"}), 400
        
# #         data = request.get_json()
# #         if not data:
# #             logger.error("No JSON data in request body")
# #             return jsonify({"error": "No JSON data provided"}), 400
        
# #         logger.debug(f"Request data received: {data}")
        
# #         # Extract and validate required fields
# #         template_name = data.get('template')
# #         ft_number = data.get('ft_number', '')
# #         variables = data.get('variables', {})
        
# #         logger.info(f"Processing template deployment request: template='{template_name}', ft_number='{ft_number}'")
        
# #         if not template_name:
# #             logger.error("Missing template name in the request")
# #             return jsonify({"error": "Template name is required"}), 400
        
# #         if not isinstance(template_name, str) or not template_name.strip():
# #             logger.error("Invalid template name provided")
# #             return jsonify({"error": "Template name must be a non-empty string"}), 400
        
# #         if not isinstance(variables, dict):
# #             logger.error("Variables must be a dictionary")
# #             return jsonify({"error": "Variables must be a dictionary"}), 400
        
# #         # Generate a unique deployment ID
# #         deployment_id = str(uuid.uuid4())
# #         logger.info(f"Generated deployment ID: {deployment_id}")
        
# #         # Prepare deployment data
# #         deployment_data = {
# #             "id": deployment_id,
# #             "template": template_name.strip(),
# #             "ft_number": ft_number,
# #             "variables": variables,
# #             "status": "running",
# #             "timestamp": time.time(),
# #             "logs": [],
# #             "logged_in_user": "infadm",
# #             "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
# #         }
        
# #         # Log the deployment data (with better formatting)
# #         logger.debug("Deployment data dictionary created:")
# #         logger.debug(json.dumps(deployment_data, indent=2, default=str))

# #         # Store in global template deployments
# #         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id] = deployment_data
# #         logger.debug(f"Stored deployment in TEMPLATE_DEPLOYMENTS_STORAGE under key {deployment_id}")
        
# #         # Save deployments to persistent storage
# #         try:
# #             save_template_deployments()
# #             logger.info(f"Stored template deployment. Total count: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
# #         except Exception as save_error:
# #             logger.error(f"Failed to save template deployments: {save_error}")
# #             # Don't fail the request, but log the error
        
# #         # Log initial message in logs
# #         try:
# #             log_template_message(deployment_id, f"Template deployment initiated: {template_name}")
# #             logger.info(f"Initial log message recorded for deployment ID: {deployment_id}")
# #         except Exception as log_error:
# #             logger.error(f"Failed to log initial message: {log_error}")
        
# #         # Start background thread
# #         logger.info(f"Starting background thread for template deployment ID: {deployment_id}")
# #         deployment_thread = threading.Thread(
# #             target=process_template_deployment_wrapper,
# #             args=(deployment_id, template_name.strip(), ft_number, variables),
# #             daemon=True,
# #             name=f"template-deploy-{deployment_id[:8]}"
# #         )
# #         deployment_thread.start()
# #         logger.info(f"Background thread '{deployment_thread.name}' started successfully")

# #         logger.info(f"Template deployment successfully initiated with ID: {deployment_id}")
# #         return jsonify({
# #             "deploymentId": deployment_id,
# #             "status": "initiated",
# #             "message": "Template deployment started successfully"
# #         }), 202  # 202 Accepted is more appropriate for async operations

# #     except Exception as e:
# #         logger.error(f"Error during template deployment: {str(e)}")
# #         logger.exception("Full exception traceback:")

# #         # Attempt to mark the deployment as failed
# #         if deployment_id and deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
# #             try:
# #                 TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
# #                 TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["error"] = str(e)
# #                 log_template_message(deployment_id, f"ERROR: {str(e)}")
# #                 save_template_deployments()
# #             except Exception as update_error:
# #                 logger.error(f"Failed to update status or log error message for deployment {deployment_id}: {update_error}")
        
# #         return jsonify({
# #             "error": "Internal server error during template deployment",
# #             "deploymentId": deployment_id
# #         }), 500

# def get_template_deployment(deployment_id):
#     """Get a template deployment by ID with debugging"""
#     with deployment_lock:
#         logger.debug(f"Available template deployments: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")
        
#         if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
#             logger.debug(f"Template deployment {deployment_id} found in memory")
#             return TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]
#         else:
#             logger.warning(f"Template deployment {deployment_id} not found, reloading from file")
            
#             # Try reloading from file
#             load_template_deployments()
            
#             if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
#                 logger.info(f"Template deployment {deployment_id} found after reload")
#                 return TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]
#             else:
#                 logger.warning(f"Template deployment {deployment_id} not found after reload")
#                 return None

# def store_template_deployment(deployment_data):
#     """Store a template deployment with proper locking and verification"""
#     deployment_id = deployment_data["id"]
    
#     with deployment_lock:
#         logger.debug(f"Storing template deployment {deployment_id}")
        
#         # Store in memory
#         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id] = deployment_data
#         logger.debug(f"Stored deployment in memory. Current count: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        
#         # Save to file
#         save_template_deployments()
        
#         # Verify storage
#         if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
#             logger.debug(f"Verification: Deployment {deployment_id} successfully stored")
#         else:
#             logger.error(f"Verification failed: Deployment {deployment_id} not found after storage")


# # @deploy_template_bp.route('/api/deploy/template', methods=['POST'])
# # def deploy_template():
# #     """Start template deployment"""
# #     deployment_id = None
# #     try:
# #         logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
        
# #         # Validate request content type
# #         if not request.is_json:
# #             logger.error("Request content type is not JSON")
# #             return jsonify({"error": "Content-Type must be application/json"}), 400
        
# #         data = request.get_json()
# #         if not data:
# #             logger.error("No JSON data in request body")
# #             return jsonify({"error": "No JSON data provided"}), 400
        
# #         logger.debug(f"Request data received: {data}")
        
# #         # Extract and validate required fields
# #         template_name = data.get('template')
# #         ft_number = data.get('ft_number', '')
# #         variables = data.get('variables', {})
        
# #         logger.info(f"Processing template deployment request: template='{template_name}', ft_number='{ft_number}'")
        
# #         if not template_name:
# #             logger.error("Missing template name in the request")
# #             return jsonify({"error": "Template name is required"}), 400
        
# #         if not isinstance(template_name, str) or not template_name.strip():
# #             logger.error("Invalid template name provided")
# #             return jsonify({"error": "Template name must be a non-empty string"}), 400
        
# #         if not isinstance(variables, dict):
# #             logger.error("Variables must be a dictionary")
# #             return jsonify({"error": "Variables must be a dictionary"}), 400
        
# #         # Generate a unique deployment ID
# #         deployment_id = str(uuid.uuid4())
# #         logger.info(f"Generated deployment ID: {deployment_id}")
        
# #         # Prepare deployment data
# #         deployment_data = {
# #             "id": deployment_id,
# #             "template": template_name.strip(),
# #             "ft_number": ft_number,
# #             "variables": variables,
# #             "status": "running",
# #             "timestamp": time.time(),
# #             "logs": [],
# #             "logged_in_user": "infadm",
# #             "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
# #         }
        
# #         logger.debug("Deployment data dictionary created:")
# #         logger.debug(json.dumps(deployment_data, indent=2, default=str))

# #         # Store deployment using the helper function
# #         store_template_deployment(deployment_data)
        
# #         # Log initial message
# #         log_template_message(deployment_id, f"Template deployment initiated: {template_name}")
# #         logger.info(f"Initial log message recorded for deployment ID: {deployment_id}")
        
# #         # Start background thread
# #         logger.info(f"Starting background thread for template deployment ID: {deployment_id}")
# #         deployment_thread = threading.Thread(
# #             target=process_template_deployment_wrapper,
# #             args=(deployment_id, template_name.strip(), ft_number, variables),
# #             daemon=True,
# #             name=f"template-deploy-{deployment_id[:8]}"
# #         )
# #         deployment_thread.start()
# #         logger.info(f"Background thread '{deployment_thread.name}' started successfully")

# #         logger.info(f"Template deployment successfully initiated with ID: {deployment_id}")
# #         return jsonify({
# #             "deploymentId": deployment_id,
# #             "status": "initiated",
# #             "message": "Template deployment started successfully"
# #         }), 202

# #     except Exception as e:
# #         logger.error(f"Error during template deployment: {str(e)}")
# #         logger.exception("Full exception traceback:")

# #         # Attempt to mark the deployment as failed
# #         if deployment_id:
# #             try:
# #                 deployment = get_template_deployment(deployment_id)
# #                 if deployment:
# #                     deployment["status"] = "failed"
# #                     deployment["error"] = str(e)
# #                     store_template_deployment(deployment)
# #                     log_template_message(deployment_id, f"ERROR: {str(e)}")
# #             except Exception as update_error:
# #                 logger.error(f"Failed to update status for deployment {deployment_id}: {update_error}")
        
# #         return jsonify({
# #             "error": "Internal server error during template deployment",
# #             "deploymentId": deployment_id
# #         }), 500

# # @deploy_template_bp.route('/api/deploy/template', methods=['POST'])
# # def deploy_template():
# #     """Start template deployment with extreme debugging"""
# #     deployment_id = None
# #     try:
# #         logger.info("=" * 60)
# #         logger.info("=== TEMPLATE DEPLOYMENT REQUEST RECEIVED ===")
# #         logger.info("=" * 60)
        
# #         # Validate request
# #         if not request.is_json:
# #             logger.error("Request content type is not JSON")
# #             return jsonify({"error": "Content-Type must be application/json"}), 400
        
# #         data = request.get_json()
# #         if not data:
# #             logger.error("No JSON data in request body")
# #             return jsonify({"error": "No JSON data provided"}), 400
        
# #         # Extract fields
# #         template_name = data.get('template')
# #         ft_number = data.get('ft_number', '')
# #         variables = data.get('variables', {})
        
# #         logger.info(f"Request details: template='{template_name}', ft_number='{ft_number}'")
        
# #         if not template_name:
# #             return jsonify({"error": "Template name is required"}), 400
        
# #         # Generate deployment ID
# #         deployment_id = str(uuid.uuid4())
# #         logger.info(f"Generated deployment ID: {deployment_id}")
        
# #         # Show storage state BEFORE adding
# #         logger.debug("BEFORE STORAGE:")
# #         logger.debug(f"  Current storage: {TEMPLATE_DEPLOYMENTS_STORAGE}")
# #         logger.debug(f"  Storage size: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        
# #         # Create deployment data
# #         deployment_data = {
# #             "id": deployment_id,
# #             "template": template_name.strip(),
# #             "ft_number": ft_number,
# #             "variables": variables,
# #             "status": "running",
# #             "timestamp": time.time(),
# #             "logs": [],
# #             "logged_in_user": "infadm",
# #             "created_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
# #         }
        
# #         logger.debug(f"Created deployment data: {deployment_data}")
        
# #         # Store in memory first
# #         logger.debug("STORING IN MEMORY...")
# #         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id] = deployment_data
        
# #         # Show storage state AFTER adding
# #         logger.debug("AFTER MEMORY STORAGE:")
# #         logger.debug(f"  Current storage: {TEMPLATE_DEPLOYMENTS_STORAGE}")
# #         logger.debug(f"  Storage size: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
# #         logger.debug(f"  Our deployment in storage: {deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE}")
        
# #         # Save to file
# #         logger.debug("SAVING TO FILE...")
# #         save_success = save_template_deployments()
        
# #         if not save_success:
# #             logger.error("FAILED TO SAVE TO FILE!")
# #             return jsonify({"error": "Failed to save deployment"}), 500
        
# #         # Verify it's actually there
# #         logger.debug("VERIFYING STORAGE...")
# #         if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
# #             logger.debug(f"SUCCESS: Deployment {deployment_id} found in memory")
# #         else:
# #             logger.error(f"CRITICAL: Deployment {deployment_id} NOT found in memory after storage!")
# #             return jsonify({"error": "Storage verification failed"}), 500
        
# #         # Add initial log
# #         logger.debug("ADDING INITIAL LOG...")
# #         timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
# #         log_entry = {
# #             "timestamp": timestamp,
# #             "message": f"Template deployment initiated: {template_name}"
# #         }
# #         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["logs"].append(log_entry)
        
# #         # Save again with log
# #         logger.debug("SAVING WITH LOG...")
# #         save_template_deployments()
        
# #         # Final verification
# #         logger.debug("FINAL VERIFICATION...")
# #         final_deployment = TEMPLATE_DEPLOYMENTS_STORAGE.get(deployment_id)
# #         if final_deployment:
# #             logger.debug(f"Final deployment data: {final_deployment}")
# #             logger.debug(f"Final deployment logs: {final_deployment.get('logs', [])}")
# #         else:
# #             logger.error("CRITICAL: Final deployment not found!")
        
# #         logger.info(f"Template deployment successfully created with ID: {deployment_id}")
# #         logger.info("=" * 60)
        
# #         return jsonify({
# #             "deploymentId": deployment_id,
# #             "status": "initiated",
# #             "message": "Template deployment started successfully"
# #         }), 202

# #     except Exception as e:
# #         logger.error(f"CRITICAL ERROR during template deployment: {e}")
# #         logger.error(f"Full traceback: {traceback.format_exc()}")
# #         return jsonify({"error": str(e)}), 500

# # def process_template_deployment_wrapper(deployment_id, template_name, ft_number, variables):
# #     """Wrapper function to handle exceptions in the deployment thread"""
# #     try:
# #         logger.info(f"=== WRAPPER: Starting template deployment thread for {deployment_id} ===")
# #         process_template_deployment(deployment_id, template_name, ft_number, variables)
# #     except Exception as e:
# #         logger.error(f"=== WRAPPER: Exception in template deployment thread {deployment_id}: {str(e)} ===")
# #         logger.exception("Full wrapper exception details:")
# #         try:
# #             log_template_message(deployment_id, f"ERROR: Deployment thread failed: {str(e)}")
# #             if deployment_id in TEMPLATE_DEPLOYMENTS_STORAGE:
# #                 TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
# #                 save_template_deployments()
# #         except Exception as cleanup_e:
# #             logger.error(f"Failed to update deployment status after thread error: {str(cleanup_e)}")

# # def process_template_deployment(deployment_id, template_name, ft_number, variables):
# #     """Process template deployment in a separate thread"""
# #     try:
# #         logger.info(f"=== STARTING TEMPLATE DEPLOYMENT PROCESSING: {deployment_id} ===")
        
# #         if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
# #             logger.error(f"Template deployment ID {deployment_id} not found")
# #             return
            
# #         logger.info(f"Processing template deployment: {template_name}")
# #         log_template_message(deployment_id, f"Starting template deployment: {template_name}")
        
# #         # Load template
# #         template = load_template(template_name)
# #         if not template:
# #             raise Exception(f"Failed to load template: {template_name}")
        
# #         log_template_message(deployment_id, f"Loaded template: {template_name}")
        
# #         # Load inventory
# #         inventory = load_inventory_files()
        
# #         # Process deployment steps
# #         steps = template.get("steps", [])
# #         log_template_message(deployment_id, f"Processing {len(steps)} deployment steps")
# #         logger.info(f"Processing {len(steps)} deployment steps")
        
# #         for i, step in enumerate(sorted(steps, key=lambda x: x.get('order', 0)), 1):
# #             try:
# #                 step_type = step.get("type")
# #                 step_order = step.get("order", i)
# #                 step_description = step.get("description", "")
                
# #                 log_template_message(deployment_id, f"Executing step {step_order}: {step_description}")
# #                 logger.info(f"[{deployment_id}] Executing step {step_order}: {step_type}")
                
# #                 # Execute different step types
# #                 if step_type == "file_deployment":
# #                     execute_file_deployment_step(deployment_id, step, inventory)
# #                 elif step_type == "sql_deployment":
# #                     execute_sql_deployment_step(deployment_id, step, inventory)
# #                 elif step_type == "service_restart":
# #                     execute_service_restart_step(deployment_id, step, inventory)
# #                 elif step_type == "ansible_playbook":
# #                     execute_ansible_playbook_step(deployment_id, step, inventory)
# #                 elif step_type == "helm_upgrade":
# #                     execute_helm_upgrade_step(deployment_id, step, inventory)
# #                 else:
# #                     log_template_message(deployment_id, f"WARNING: Unknown step type: {step_type}")
                
# #                 log_template_message(deployment_id, f"Completed step {step_order}")
# #                 time.sleep(2)  # Delay between steps
                
# #             except Exception as e:
# #                 error_msg = f"Failed to execute step {step_order}: {str(e)}"
# #                 log_template_message(deployment_id, f"ERROR: {error_msg}")
# #                 logger.error(f"[{deployment_id}] {error_msg}")
# #                 TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
# #                 save_template_deployments()
# #                 return
        
# #         # If we get here, all steps completed successfully
# #         log_template_message(deployment_id, "SUCCESS: Template deployment completed successfully")
# #         TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "success"
# #         logger.info(f"Template deployment {deployment_id} completed successfully")
# #         save_template_deployments()
        
# #     except Exception as e:
# #         error_msg = f"Unexpected error during template deployment: {str(e)}"
# #         logger.error(f"[{deployment_id}] {error_msg}")
# #         logger.exception("Full exception details:")
        
# #         try:
# #             log_template_message(deployment_id, f"ERROR: {error_msg}")
# #             TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
# #             save_template_deployments()
# #         except:
# #             logger.error("Failed to update deployment status after error")

# # # ... keep existing code (all execution step functions remain the same)

# # def execute_file_deployment_step(deployment_id, step, inventory):
# #     """Execute file deployment step"""
# #     try:
# #         files = step.get("files", [])
# #         ft_number = step.get("ftNumber", "")
# #         target_path = step.get("targetPath", "/tmp")
# #         target_user = step.get("targetUser", "infadm")
# #         target_vms = step.get("targetVMs", ["batch1"])
        
# #         log_template_message(deployment_id, f"File deployment: {files} to {target_path} on {target_vms}")
        
# #         # Execute file deployment using Ansible
# #         for vm in target_vms:
# #             vm_ip = "10.172.145.204"  # Default IP for batch1
# #             for vm_info in inventory.get("vms", []):
# #                 if vm_info.get("name") == vm:
# #                     vm_ip = vm_info.get("ip", vm_ip)
# #                     break
            
# #             for file_name in files:
# #                 source_file = os.path.join(FIX_FILES_DIR, ft_number, file_name)
                
# #                 if not os.path.exists(source_file):
# #                     raise Exception(f"Source file not found: {source_file}")
                
# #                 # Copy file using scp
# #                 cmd = [
# #                     "scp", "-o", "StrictHostKeyChecking=no", "-i", "/app/ssh-keys/id_rsa",
# #                     source_file, f"{target_user}@{vm_ip}:{target_path}/{file_name}"
# #                 ]
                
# #                 result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
# #                 if result.returncode == 0:
# #                     log_template_message(deployment_id, f"File {file_name} deployed successfully to {vm}")
# #                 else:
# #                     raise Exception(f"File deployment failed for {file_name}: {result.stderr}")
                    
# #     except Exception as e:
# #         logger.error(f"File deployment step failed: {str(e)}")
# #         raise

# # def execute_sql_deployment_step(deployment_id, step, inventory):
# #     """Execute SQL deployment step"""
# #     try:
# #         files = step.get("files", [])
# #         ft_number = step.get("ftNumber", "")
# #         db_connection = step.get("dbConnection", "")
# #         db_user = step.get("dbUser", "")
# #         db_password = step.get("dbPassword", "")
        
# #         # Decode password if base64 encoded
# #         try:
# #             decoded_password = base64.b64decode(db_password).decode('utf-8')
# #             db_password = decoded_password
# #         except:
# #             pass
        
# #         log_template_message(deployment_id, f"SQL deployment: {files} on connection {db_connection}")
        
# #         # Find database connection details
# #         db_info = None
# #         for conn in inventory.get("db_connections", []):
# #             if conn.get("connection_name") == db_connection:
# #                 db_info = conn
# #                 break
        
# #         if not db_info:
# #             raise Exception(f"Database connection {db_connection} not found")
        
# #         hostname = db_info.get("hostname", "localhost")
# #         port = db_info.get("port", "5432")
        
# #         for file_name in files:
# #             sql_file = os.path.join(FIX_FILES_DIR, ft_number, file_name)
            
# #             if not os.path.exists(sql_file):
# #                 raise Exception(f"SQL file not found: {sql_file}")
            
# #             # Execute SQL file using psql
# #             cmd = [
# #                 "psql", 
# #                 f"postgresql://{db_user}:{db_password}@{hostname}:{port}/postgres",
# #                 "-f", sql_file
# #             ]
            
# #             result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
# #             if result.stdout:
# #                 log_template_message(deployment_id, f"SQL OUTPUT: {result.stdout}")
            
# #             if result.returncode == 0:
# #                 log_template_message(deployment_id, f"SQL file {file_name} executed successfully")
# #             else:
# #                 raise Exception(f"SQL execution failed for {file_name}: {result.stderr}")
                
# #     except Exception as e:
# #         logger.error(f"SQL deployment step failed: {str(e)}")
# #         raise

# # def execute_service_restart_step(deployment_id, step, inventory):
# #     """Execute service restart step"""
# #     try:
# #         service = step.get("service", "docker")
# #         operation = step.get("operation", "restart")
# #         target_vms = step.get("targetVMs", ["batch1"])
        
# #         log_template_message(deployment_id, f"Service operation: {operation} {service} on {target_vms}")
        
# #         for vm in target_vms:
# #             vm_ip = "10.172.145.204"  # Default IP for batch1
# #             for vm_info in inventory.get("vms", []):
# #                 if vm_info.get("name") == vm:
# #                     vm_ip = vm_info.get("ip", vm_ip)
# #                     break
            
# #             # Execute systemctl command
# #             cmd = [
# #                 "ssh", "-o", "StrictHostKeyChecking=no", "-i", "/app/ssh-keys/id_rsa",
# #                 f"infadm@{vm_ip}", f"sudo systemctl {operation} {service}"
# #             ]
            
# #             result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
# #             if result.stdout:
# #                 log_template_message(deployment_id, f"SERVICE OUTPUT: {result.stdout}")
            
# #             if result.returncode == 0:
# #                 log_template_message(deployment_id, f"Service {operation} completed successfully on {vm}")
# #             else:
# #                 raise Exception(f"Service {operation} failed on {vm}: {result.stderr}")
                
# #     except Exception as e:
# #         logger.error(f"Service restart step failed: {str(e)}")
# #         raise

# # def execute_ansible_playbook_step(deployment_id, step, inventory):
# #     """Execute Ansible playbook step"""
# #     try:
# #         playbook_name = step.get("playbook", "")
        
# #         log_template_message(deployment_id, f"Executing Ansible playbook: {playbook_name}")
        
# #         # Find playbook path from inventory
# #         playbook_path = f"/etc/ansible/playbooks/{playbook_name}"
# #         for pb in inventory.get("ansible_playbooks", []):
# #             if pb.get("name") == playbook_name:
# #                 playbook_path = os.path.join(pb.get("path", "/etc/ansible/playbooks/"), playbook_name)
# #                 break
        
# #         if not os.path.exists(playbook_path):
# #             raise Exception(f"Playbook file not found: {playbook_path}")
        
# #         # Execute ansible playbook
# #         cmd = ["ansible-playbook", playbook_path, "-v"]
# #         env_vars = os.environ.copy()
# #         env_vars["ANSIBLE_HOST_KEY_CHECKING"] = "False"
        
# #         result = subprocess.run(cmd, capture_output=True, text=True, env=env_vars, timeout=600)
        
# #         if result.stdout:
# #             for line in result.stdout.splitlines():
# #                 if line.strip():
# #                     log_template_message(deployment_id, f"ANSIBLE: {line.strip()}")
        
# #         if result.returncode == 0:
# #             log_template_message(deployment_id, "Ansible playbook executed successfully")
# #         else:
# #             raise Exception(f"Ansible playbook execution failed with return code: {result.returncode}")
            
# #     except Exception as e:
# #         logger.error(f"Ansible playbook step failed: {str(e)}")
# #         raise

# # def execute_helm_upgrade_step(deployment_id, step, inventory):
# #     """Execute Helm upgrade step"""
# #     try:
# #         helm_deployment_type = step.get("helmDeploymentType", "")
        
# #         log_template_message(deployment_id, f"Executing Helm upgrade: {helm_deployment_type}")
        
# #         # Find helm command from inventory
# #         helm_command = None
# #         for helm_upgrade in inventory.get("helm_upgrades", []):
# #             if helm_upgrade.get("pod_name") == helm_deployment_type:
# #                 helm_command = helm_upgrade.get("command")
# #                 break
        
# #         if not helm_command:
# #             raise Exception(f"Helm upgrade command not found for pod: {helm_deployment_type}")
        
# #         # Execute helm command on batch1
# #         cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", "/app/ssh-keys/id_rsa", 
# #                "infadm@10.172.145.204", helm_command]
        
# #         result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
# #         if result.stdout:
# #             for line in result.stdout.splitlines():
# #                 if line.strip():
# #                     log_template_message(deployment_id, f"HELM: {line.strip()}")
        
# #         if result.returncode == 0:
# #             log_template_message(deployment_id, "Helm upgrade completed successfully")
# #         else:
# #             raise Exception(f"Helm upgrade failed with return code: {result.returncode}")
            
# #     except Exception as e:
# #         logger.error(f"Helm upgrade step failed: {str(e)}")
# #         raise

# @deploy_template_bp.route('/api/template-deploy/<deployment_id>/logs', methods=['GET'])
# def get_template_deployment_logs(deployment_id):
#     """Get template deployment logs"""
#     try:
#         logger.debug(f"Looking for template deployment: {deployment_id}")
#         logger.debug(f"Available template deployments: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")
        
#         # Try to reload deployments if not found
#         if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
#             logger.warning(f"Template deployment {deployment_id} not found, reloading from file")
#             load_template_deployments()
        
#         if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
#             logger.warning(f"Template deployment {deployment_id} not found after reload")
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

# @deploy_template_bp.route('/api/deploy/template/<deployment_id>/status', methods=['GET'])
# def get_deployment_status(deployment_id):
#     """Get status with debugging"""
#     logger.debug(f"Looking for template deployment: {deployment_id}")
#     logger.debug(f"Available template deployments: {list(TEMPLATE_DEPLOYMENTS_STORAGE.keys())}")
    
#     if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
#         logger.warning(f"Template deployment {deployment_id} not found, reloading from file")
#         load_template_deployments()
        
#         if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
#             logger.warning(f"Template deployment {deployment_id} not found after reload")
#             return jsonify({"error": "Deployment not found"}), 404
    
#     deployment = TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]
#     return jsonify({
#         "id": deployment["id"],
#         "template": deployment["template"],
#         "ft_number": deployment["ft_number"],
#         "status": deployment["status"],
#         "timestamp": deployment["timestamp"],
#         "created_at": deployment.get("created_at", "Unknown"),
#         "logs": deployment.get("logs", []),
#         "error": deployment.get("error")
#     }), 200

# @deploy_template_bp.route('/api/template-deployments/history', methods=['GET'])
# def get_template_deployment_history():
#     """Get template deployment history"""
#     try:
#         deployment_list = []
#         for deployment_id, deployment in TEMPLATE_DEPLOYMENTS_STORAGE.items():
#             deployment_list.append({
#                 "id": deployment_id,
#                 "template": deployment.get("template", ""),
#                 "ft_number": deployment.get("ft_number", ""),
#                 "status": deployment.get("status", "unknown"),
#                 "timestamp": deployment.get("timestamp", 0),
#                 "logs": deployment.get("logs", []),
#                 "logged_in_user": deployment.get("logged_in_user", "")
#             })
        
#         deployment_list.sort(key=lambda x: x["timestamp"], reverse=True)
#         logger.debug(f"Returning {len(deployment_list)} template deployments")
#         return jsonify(deployment_list)
        
#     except Exception as e:
#         logger.error(f"Error fetching template deployment history: {str(e)}")
#         return jsonify({"error": str(e)}), 500



# ensure_directories()
# test_file_permissions()
# load_template_deployments()
# logger.info("Template deployment module initialized successfully")