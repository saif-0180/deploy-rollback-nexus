
# Add these imports to your app.py file
from routes.template_routes import template_bp

# Add this blueprint registration to your app.py file
app.register_blueprint(template_bp)

# Also add these new API endpoints to handle the additional data we need:

@app.route('/api/ansible-playbooks', methods=['GET'])
def get_ansible_playbooks():
    """Get available Ansible playbooks from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify([])
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        playbooks = inventory.get('ansible_playbooks', [])
        return jsonify(playbooks)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/helm-deployment-types', methods=['GET'])
def get_helm_deployment_types():
    """Get available Helm deployment types from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify([])
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        deployment_types = inventory.get('helm_deployment_types', [])
        return jsonify(deployment_types)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
