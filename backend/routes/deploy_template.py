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
        
        # # Show storage state BEFORE adding
        # logger.debug("BEFORE STORAGE:")
        # logger.debug(f"  Current storage: {TEMPLATE_DEPLOYMENTS_STORAGE}")
        # logger.debug(f"  Storage size: {len(TEMPLATE_DEPLOYMENTS_STORAGE)}")
        
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

        threading.Thread(target=process_template_deployment, args=(deployment_id, template_name, ft_number, variables)).start()
    
        logger.info(f"Template deployment initiated with ID: {deployment_id}")
        return jsonify({"deploymentId": deployment_id})
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR during template deployment: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


def process_template_deployment(deployment_id, template_name, ft_number, variables):

    from app import log_message, deployments, save_deployment_history
    """Process template deployment in a separate thread"""
    try:
        logger.info(f"=== STARTING TEMPLATE DEPLOYMENT PROCESSING: {deployment_id} ===")
        
        # if deployment_id not in TEMPLATE_DEPLOYMENTS_STORAGE:
        #     logger.error(f"Template deployment ID {deployment_id} not found")
        #     return

        if deployment_id not in deployments:
            logger.error(f"Template deployment ID {deployment_id} not found in deployments")
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
                # TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
                save_template_deployments()
                return
        
        # If we get here, all steps completed successfully
        log_template_message(deployment_id, "SUCCESS: Template deployment completed successfully")
        # TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "success"
        logger.info(f"Template deployment {deployment_id} completed successfully")
        save_template_deployments()
        
    except Exception as e:
        error_msg = f"Unexpected error during template deployment: {str(e)}"
        logger.error(f"[{deployment_id}] {error_msg}")
        logger.exception("Full exception details:")
        
        try:
            log_template_message(deployment_id, f"ERROR: {error_msg}")
            # TEMPLATE_DEPLOYMENTS_STORAGE[deployment_id]["status"] = "failed"
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

        if deployment_id in deployments:
            deployments[deployment_id]["status"] = "failed"
            save_deployment_history()

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

