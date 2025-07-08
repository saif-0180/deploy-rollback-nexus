
# Add these imports to your app.py file
from routes.template_routes import template_bp
from routes.deploy_template import deploy_template_bp

# Add these blueprint registrations to your app.py file
app.register_blueprint(template_bp)
app.register_blueprint(deploy_template_bp)

# Also add these new API endpoints to handle the additional data we need:

@app.route('/api/playbooks', methods=['GET'])
def get_playbooks():
    """Get playbooks from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify({'playbooks': []})
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        return jsonify({'playbooks': inventory.get('playbooks', [])})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/helm-upgrades', methods=['GET'])
def get_helm_upgrades():
    """Get helm upgrades from inventory"""
    try:
        inventory_path = '/app/inventory/inventory.json'
        
        if not os.path.exists(inventory_path):
            return jsonify({'helm_upgrades': []})
        
        with open(inventory_path, 'r') as f:
            inventory = json.load(f)
        
        return jsonify({'helm_upgrades': inventory.get('helm_upgrades', [])})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/db-inventory', methods=['GET'])
def get_db_inventory():
    """Get database inventory"""
    try:
        db_inventory_path = '/app/inventory/db_inventory.json'
        
        if not os.path.exists(db_inventory_path):
            return jsonify({'db_connections': [], 'db_users': []})
        
        with open(db_inventory_path, 'r') as f:
            db_inventory = json.load(f)
        
        return jsonify(db_inventory)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
