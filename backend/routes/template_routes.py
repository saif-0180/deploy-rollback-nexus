
from flask import Blueprint, request, jsonify, current_app
import json
import os
import uuid
import threading
import time
from datetime import datetime
import subprocess
import logging
import base64

template_bp = Blueprint('template', __name__)

# Store active deployments
active_deployments = {}

def execute_deployment_step(step, deployment_id, ft_number, orchestration_user='infadm'):
    """Execute a single deployment step"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return False
    
    try:
        step_type = step.get('type')
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing step {step.get('order')}: {step.get('description')}")
        
        if step_type == 'file_deployment':
            # Execute file deployment
            files = step.get('files', [])
            target_path = step.get('targetPath', '/home/users/abpwrk1/pbin/app')
            target_user = step.get('targetUser', 'abpwrk1')
            target_vms = step.get('targetVMs', [])
            ft_number = step.get('ftNumber', '')
            
            for vm in target_vms:
                for file in files:
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Copying {file} from FT {ft_number} to {vm}:{target_path} as {target_user}")
                    # Add your actual file copy logic here
                    time.sleep(2)  # Simulate processing time
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully copied {file} to {vm}")
        
        elif step_type == 'sql_deployment':
            # Execute SQL deployment
            files = step.get('files', [])
            db_connection = step.get('dbConnection')
            db_user = step.get('dbUser')
            db_name = step.get('dbName')
            db_password_encoded = step.get('dbPassword', '')
            
            # Decode base64 password
            db_password = base64.b64decode(db_password_encoded).decode('utf-8') if db_password_encoded else ''
            
            for sql_file in files:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing SQL file: {sql_file} on {db_connection}")
                # Add your actual SQL execution logic here
                time.sleep(3)  # Simulate processing time
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed SQL file: {sql_file}")
        
        elif step_type == 'service_restart':
            # Execute service restart
            service = step.get('service', 'docker.service')
            operation = step.get('operation', 'restart')
            target_vms = step.get('targetVMs', [])
            
            for vm in target_vms:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Performing {operation} on {service} on {vm}")
                # Add your actual service operation logic here
                time.sleep(2)  # Simulate processing time
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully performed {operation} on {service} on {vm}")
        
        elif step_type == 'ansible_playbook':
            # Execute Ansible playbook
            playbook = step.get('playbook', '')
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Running Ansible playbook: {playbook}")
            
            # Construct the ansible-playbook command
            cmd = f"""ansible-playbook /opt/amdocs/infadm/rm-acd/playbooks/TC1/install_playbooks/{playbook} \
                -i /home/users/infadm/rm-acd/generated_inventory.ini -f 10 \
                -e env_type=K8S \
                -e@/home/users/infadm/rm-acd/acd_input/silentProperties/tc1_silentProperties_common.yml \
                -e@/home/users/infadm/rm-acd/acd_input/silentProperties/tc1_silentProperties_topology.yml \
                -e@/home/users/infadm/rm-acd/acd_input/silentProperties/tc1_silentProperties_encrypted.yml \
                -e@/home/users/infadm/rm-acd/acd_input/silentProperties/tc1_silentProperties_topology_k8s.yml \
                -e@/home/users/infadm/rm-acd/acd_input/silentProperties/tc1_silentProperties_encrypted_k8s.yml \
                -e@/home/users/infadm/workspace/TC_CD_PIPELINE1@2/../git_area/VM07/cd-input/silent_properties/ABP1_silentProperties_fco.yml \
                -e@/home/users/infadm/workspace/TC_CD_PIPELINE1@2/../git_area/VM07/cd-input/silent_properties/ABP1_silentProperties_fco_enc.yml \
                --vault-password-file /home/users/infadm/rm-acd/vaultPwdfile.txt"""
            
            # Add your actual Ansible playbook execution logic here
            time.sleep(60)  # Simulate long running playbook (1 minute for demo, actual can be 1 hour)
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed Ansible playbook: {playbook}")
        
        elif step_type == 'helm_upgrade':
            # Execute Helm upgrade
            deployment_type = step.get('helmDeploymentType', '')
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Performing Helm upgrade for deployment type: {deployment_type}")
            # Add your actual Helm upgrade logic here
            time.sleep(3)  # Simulate processing time
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully performed Helm upgrade for: {deployment_type}")
        
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Step {step.get('order')} completed successfully")
        return True
        
    except Exception as e:
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR in step {step.get('order')}: {str(e)}")
        return False

def run_template_deployment(deployment_id, template, ft_number):
    """Run the template deployment in a separate thread"""
    deployment = active_deployments.get(deployment_id)
    if not deployment:
        return
    
    try:
        deployment['status'] = 'running'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting template deployment for {ft_number}")
        
        steps = template.get('steps', [])
        total_steps = len(steps)
        
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Total steps to execute: {total_steps}")
        
        # Execute steps in order
        for step in sorted(steps, key=lambda x: x.get('order', 0)):
            if deployment['status'] != 'running':
                break
                
            success = execute_deployment_step(step, deployment_id, ft_number)
            if not success:
                deployment['status'] = 'failed'
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Deployment failed at step {step.get('order')}")
                return
        
        deployment['status'] = 'success'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Template deployment completed successfully")
        
    except Exception as e:
        deployment['status'] = 'failed'
        deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")

@template_bp.route('/api/templates/save', methods=['POST'])
def save_template():
    """Save a generated template to the deployment templates directory"""
    try:
        data = request.get_json()
        ft_number = data.get('ft_number')
        template = data.get('template')
        
        if not ft_number or not template:
            return jsonify({'error': 'Missing ft_number or template'}), 400
        
        # Create deployment templates directory if it doesn't exist
        templates_dir = '/apps/deployment_templates'
        os.makedirs(templates_dir, exist_ok=True)
        
        # Save template to file with FT number in filename
        template_file = os.path.join(templates_dir, f'{ft_number}_template.json')
        with open(template_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        return jsonify({'message': 'Template saved successfully', 'path': template_file})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/templates/list', methods=['GET'])
def list_templates():
    """List all available templates from deployment templates directory"""
    try:
        templates = []
        templates_dir = '/apps/deployment_templates'
        
        if os.path.exists(templates_dir):
            for file in os.listdir(templates_dir):
                if file.endswith('_template.json'):
                    ft_number = file.replace('_template.json', '')
                    templates.append(ft_number)
        
        return jsonify(templates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/templates/<ft_number>', methods=['GET'])
def get_template(ft_number):
    """Get a specific template from deployment templates directory"""
    try:
        template_file = os.path.join('/apps/deployment_templates', f'{ft_number}_template.json')
        
        if not os.path.exists(template_file):
            return jsonify({'error': 'Template not found'}), 404
        
        with open(template_file, 'r') as f:
            template = json.load(f)
        
        return jsonify(template)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/deploy/template', methods=['POST'])
def deploy_template():
    """Start a template deployment"""
    try:
        data = request.get_json()
        ft_number = data.get('ft_number')
        template = data.get('template')
        
        if not ft_number or not template:
            return jsonify({'error': 'Missing ft_number or template'}), 400
        
        # Generate deployment ID
        deployment_id = str(uuid.uuid4())
        
        # Initialize deployment tracking
        active_deployments[deployment_id] = {
            'id': deployment_id,
            'ft_number': ft_number,
            'status': 'running',
            'logs': [],
            'started_at': datetime.now().isoformat(),
            'template': template
        }
        
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
            'status': 'running'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/deploy/template/<deployment_id>/logs', methods=['GET'])
def get_deployment_logs(deployment_id):
    """Get logs for a template deployment"""
    try:
        deployment = active_deployments.get(deployment_id)
        
        if not deployment:
            return jsonify({'error': 'Deployment not found'}), 404
        
        return jsonify({
            'logs': deployment['logs'],
            'status': deployment['status'],
            'ft_number': deployment['ft_number'],
            'started_at': deployment['started_at']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/users', methods=['GET'])
def get_users():
    """Get users from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify(['infadm', 'abpwrk1', 'root'])  # Default users
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        users = inventory.get('users', ['infadm', 'abpwrk1', 'root'])
        return jsonify(users)
        
    except Exception as e:
        return jsonify(['infadm', 'abpwrk1', 'root'])  # Fallback to default users

@template_bp.route('/api/ansible-playbooks', methods=['GET'])
def get_ansible_playbooks():
    """Get available Ansible playbooks"""
    try:
        # Return predefined playbooks for now - you can modify this to read from filesystem
        playbooks = [
            'tc1_tc_changeSet_install.yml',
            'tc1_deployment_playbook.yml',
            'tc1_configuration_playbook.yml',
            'tc1_maintenance_playbook.yml'
        ]
        return jsonify(playbooks)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/helm-deployment-types', methods=['GET'])
def get_helm_deployment_types():
    """Get available Helm deployment types"""
    try:
        # Return predefined deployment types - you can modify this to read from inventory
        deployment_types = [
            'rb1',
            'pw1',
            'tc1',
            'abp1'
        ]
        return jsonify(deployment_types)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
