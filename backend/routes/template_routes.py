
from flask import Blueprint, request, jsonify, current_app
import json
import os
import uuid
import threading
import time
from datetime import datetime
import subprocess
import logging

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
            
            for vm in target_vms:
                for file in files:
                    # Simulate file copy (replace with actual implementation)
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Copying {file} to {vm}:{target_path}")
                    # Add your actual file copy logic here
                    time.sleep(2)  # Simulate processing time
                    deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully copied {file} to {vm}")
        
        elif step_type == 'sql_deployment':
            # Execute SQL deployment
            sql_file = step.get('sqlFile', 'query.sql')
            db_connection = step.get('dbConnection')
            db_user = step.get('dbUser')
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing SQL file: {sql_file}")
            # Add your actual SQL execution logic here
            time.sleep(3)  # Simulate processing time
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed SQL file: {sql_file}")
        
        elif step_type == 'service_restart':
            # Execute service restart
            service = step.get('service', 'docker.service')
            target_vms = step.get('targetVMs', [])
            
            for vm in target_vms:
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Restarting {service} on {vm}")
                # Add your actual service restart logic here
                time.sleep(2)  # Simulate processing time
                deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully restarted {service} on {vm}")
        
        elif step_type == 'ansible_playbook':
            # Execute Ansible playbook
            playbook = step.get('playbook', 'playbook.yml')
            target_vms = step.get('targetVMs', [])
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Running playbook: {playbook}")
            # Add your actual Ansible playbook execution logic here
            time.sleep(4)  # Simulate processing time
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully executed playbook: {playbook}")
        
        elif step_type == 'helm_upgrade':
            # Execute Helm upgrade
            chart = step.get('chart', 'chart')
            target_vms = step.get('targetVMs', [])
            
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Upgrading Helm chart: {chart}")
            # Add your actual Helm upgrade logic here
            time.sleep(3)  # Simulate processing time
            deployment['logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully upgraded Helm chart: {chart}")
        
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
    """Save a generated template to the FT directory"""
    try:
        data = request.get_json()
        ft_number = data.get('ft_number')
        template = data.get('template')
        
        if not ft_number or not template:
            return jsonify({'error': 'Missing ft_number or template'}), 400
        
        # Create templates directory if it doesn't exist
        templates_dir = os.path.join('/app/uploads', ft_number, 'templates')
        os.makedirs(templates_dir, exist_ok=True)
        
        # Save template to file
        template_file = os.path.join(templates_dir, f'{ft_number}_template.json')
        with open(template_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        return jsonify({'message': 'Template saved successfully', 'path': template_file})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/templates/list', methods=['GET'])
def list_templates():
    """List all available templates"""
    try:
        templates = []
        uploads_dir = '/app/uploads'
        
        if os.path.exists(uploads_dir):
            for ft_dir in os.listdir(uploads_dir):
                template_file = os.path.join(uploads_dir, ft_dir, 'templates', f'{ft_dir}_template.json')
                if os.path.exists(template_file):
                    templates.append(ft_dir)
        
        return jsonify(templates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@template_bp.route('/api/templates/<ft_number>', methods=['GET'])
def get_template(ft_number):
    """Get a specific template"""
    try:
        template_file = os.path.join('/app/uploads', ft_number, 'templates', f'{ft_number}_template.json')
        
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
