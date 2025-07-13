
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

def get_shared_resources():
    """Get shared resources from the main app"""
    try:
        # Ensure template_deployments exists in current_app
        if not hasattr(current_app, 'template_deployments'):
            current_app.template_deployments = {}
        
        # Get the main app's deployment functions
        from app import log_message, save_deployment_history
        
        # Load inventory files
        inventory = load_inventory_files()
        
        logger.debug(f"Retrieved shared resources. Template deployments count: {len(current_app.template_deployments)}")
        
        return current_app.template_deployments, log_message, save_deployment_history, inventory
        
    except Exception as e:
        logger.error(f"Failed to get shared resources: {str(e)}")
        
        # Fallback resources
        if not hasattr(current_app, 'template_deployments'):
            current_app.template_deployments = {}
        
        def fallback_log(deployment_id, message):
            logger.info(f"[{deployment_id}] {message}")
        
        def fallback_save():
            pass
        
        inventory = load_inventory_files()
        
        return current_app.template_deployments, fallback_log, fallback_save, inventory

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

def log_template_message(deployment_id, message):
    """Log message for template deployments"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_message = f"[{timestamp}] {message}"
    
    logger.info(f"[{deployment_id}] {message}")
    
    # Store in template deployments
    if deployment_id in current_app.template_deployments:
        if 'logs' not in current_app.template_deployments[deployment_id]:
            current_app.template_deployments[deployment_id]['logs'] = []
        current_app.template_deployments[deployment_id]['logs'].append(formatted_message)

def save_template_deployment_history():
    """Save template deployment history"""
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
        
        # Get shared resources
        template_deployments, log_message, save_deployment_history, inventory = get_shared_resources()
        logger.debug("Successfully got shared resources")
        
        # Generate a unique deployment ID
        deployment_id = str(uuid.uuid4())
        logger.info(f"Generated deployment ID: {deployment_id}")
        
        # Store deployment information
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
        logger.info(f"Stored template deployment. Total template deployments: {len(current_app.template_deployments)}")
        
        # Log initial message
        log_template_message(deployment_id, f"Template deployment initiated: {template_name}")
        logger.info(f"Logged initial message for template deployment {deployment_id}")
        
        # Save template deployment history
        save_template_deployment_history()
        
        # Start deployment in a separate thread
        logger.info(f"Creating background thread for template deployment {deployment_id}")
        deployment_thread = threading.Thread(
            target=process_template_deployment_wrapper, 
            args=(deployment_id, template_name, ft_number, variables, inventory),
            daemon=True,
            name=f"template-deploy-{deployment_id[:8]}"
        )
        deployment_thread.start()
        logger.info(f"Background thread '{deployment_thread.name}' started successfully")
        
        logger.info(f"Template deployment initiated with ID: {deployment_id}")
        return jsonify({"deploymentId": deployment_id})
        
    except Exception as e:
        logger.error(f"Error starting template deployment: {str(e)}")
        logger.exception("Full exception details:")
        if deployment_id and hasattr(current_app, 'template_deployments'):
            try:
                current_app.template_deployments[deployment_id]["status"] = "failed"
                log_template_message(deployment_id, f"ERROR: {str(e)}")
                save_template_deployment_history()
            except:
                pass
        return jsonify({"error": str(e)}), 500

def process_template_deployment_wrapper(deployment_id, template_name, ft_number, variables, inventory):
    """Wrapper function to handle exceptions in the deployment thread"""
    try:
        logger.info(f"=== WRAPPER: Starting template deployment thread for {deployment_id} ===")
        
        with current_app.app_context():
            process_template_deployment(deployment_id, template_name, ft_number, variables, inventory)
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

def process_template_deployment(deployment_id, template_name, ft_number, variables, inventory):
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
                
                # Execute different step types using main app functions
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

def execute_file_deployment_step(deployment_id, step, inventory):
    """Execute file deployment step by calling main app function"""
    try:
        # Import the main app's file deployment function
        from app import execute_ansible_file_deployment
        
        files = step.get("files", [])
        ft_number = step.get("ftNumber", "")
        target_path = step.get("targetPath", "/tmp")
        target_user = step.get("targetUser", "infadm")
        target_vms = step.get("targetVMs", ["batch1"])
        
        log_template_message(deployment_id, f"File deployment: {files} to {target_path} on {target_vms}")
        
        # Use the main app's function
        result = execute_ansible_file_deployment(
            vms=target_vms,
            ft=ft_number,
            file=files[0] if files else "",
            target_path=target_path,
            target_user=target_user,
            files=files
        )
        
        if result.get('success'):
            log_template_message(deployment_id, "File deployment completed successfully")
        else:
            raise Exception(result.get('error', 'File deployment failed'))
            
    except Exception as e:
        logger.error(f"File deployment step failed: {str(e)}")
        raise

def execute_sql_deployment_step(deployment_id, step, inventory):
    """Execute SQL deployment step by calling main app function"""
    try:
        # Import the main app's SQL deployment function
        from app import execute_sql_deployment
        
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
        
        # Use the main app's function
        result = execute_sql_deployment(
            ft=ft_number,
            file=files[0] if files else "",
            db_connection=db_connection,
            db_user=db_user,
            db_password=db_password
        )
        
        if result.get('success'):
            log_template_message(deployment_id, "SQL deployment completed successfully")
        else:
            raise Exception(result.get('error', 'SQL deployment failed'))
            
    except Exception as e:
        logger.error(f"SQL deployment step failed: {str(e)}")
        raise

def execute_service_restart_step(deployment_id, step, inventory):
    """Execute service restart step by calling main app function"""
    try:
        # Import the main app's systemctl function
        from app import execute_ansible_systemctl
        
        service = step.get("service", "docker")
        operation = step.get("operation", "restart")
        target_vms = step.get("targetVMs", ["batch1"])
        
        log_template_message(deployment_id, f"Service operation: {operation} {service} on {target_vms}")
        
        # Use the main app's function
        result = execute_ansible_systemctl(
            vms=target_vms,
            service=service,
            operation=operation
        )
        
        if result.get('success'):
            log_template_message(deployment_id, f"Service {operation} completed successfully")
        else:
            raise Exception(result.get('error', f'Service {operation} failed'))
            
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

@deploy_template_bp.route('/api/template-deploy/<deployment_id>/logs', methods=['GET'])
def get_template_deployment_logs(deployment_id):
    """Get template deployment logs"""
    try:
        logger.debug(f"Looking for template deployment: {deployment_id}")
        
        if not hasattr(current_app, 'template_deployments'):
            current_app.template_deployments = {}
        
        if deployment_id not in current_app.template_deployments:
            logger.warning(f"Template deployment {deployment_id} not found")
            return jsonify({"error": "Template deployment not found"}), 404
        
        deployment = current_app.template_deployments[deployment_id]
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
        logger.debug(f"Returning {len(deployment_list)} template deployments")
        return jsonify(deployment_list)
        
    except Exception as e:
        logger.error(f"Error fetching template deployment history: {str(e)}")
        return jsonify({"error": str(e)}), 500
