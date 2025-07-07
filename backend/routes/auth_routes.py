from flask import Blueprint, request, jsonify
import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta
import jwt

auth_bp = Blueprint('auth', __name__)

# Configuration
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-this-in-production')
USERS_FILE = '/app/users/users.json'

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    """Load users from JSON file"""
    if not os.path.exists(USERS_FILE):
        # Create default admin user
        default_users = {
            "admin": {
                "password": hash_password("admin123"),
                "role": "admin",
                "created_at": datetime.now().isoformat()
            }
        }
        save_users(default_users)
        return default_users
    
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def generate_token(username, role):
    """Generate JWT token"""
    payload = {
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# def token_required(f):
#     """Decorator to require valid token"""
#     @wraps(f)
#     def decorated(*args, **kwargs):
#         auth_header = request.headers.get('Authorization')
#         if not auth_header or not auth_header.startswith('Bearer '):
#             return jsonify({'error': 'No token provided'}), 401
        
#         token = auth_header.split(' ')[1]
#         payload = verify_token(token)
        
#         if not payload:
#             return jsonify({'error': 'Invalid token'}), 401
        
#         # Store user info in Flask's g object for use in other routes
#         g.current_user = {
#             'username': payload['username'],
#             'role': payload['role']
#         }
        
#         return f(*args, **kwargs)
#     return decorated

def get_current_user():
    """Get current authenticated user"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    payload = verify_token(token)
    
    if not payload:
        return None
    
    return {
        'username': payload['username'],
        'role': payload['role']
    }

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login endpoint"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        users = load_users()
        
        if username not in users:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        hashed_password = hash_password(password)
        if users[username]['password'] != hashed_password:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        token = generate_token(username, users[username]['role'])
        
        return jsonify({
            'token': token,
            'username': username,
            'role': users[username]['role']
        })
        
    except Exception as e:
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/api/auth/verify', methods=['GET'])
def verify():
    """Verify token endpoint"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid token'}), 401
        
        return jsonify({
            'username': payload['username'],
            'role': payload['role']
        })
        
    except Exception as e:
        return jsonify({'error': 'Token verification failed'}), 500

@auth_bp.route('/api/auth/users', methods=['GET'])
def get_users():
    """Get all users (admin only)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        
        if not payload or payload['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        users = load_users()
        user_list = []
        
        for username, user_data in users.items():
            user_list.append({
                'username': username,
                'role': user_data['role'],
                'created_at': user_data.get('created_at', '')
            })
        
        # Return the array directly, not wrapped in 'users' key
        return jsonify(user_list)
        
    except Exception as e:
        return jsonify({'error': 'Failed to get users'}), 500


@auth_bp.route('/api/auth/users', methods=['POST'])
def create_user():
    """Create new user (admin only)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        
        if not payload or payload['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'user')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        users = load_users()
        
        if username in users:
            return jsonify({'error': 'User already exists'}), 400
        
        users[username] = {
            'password': hash_password(password),
            'role': role,
            'created_at': datetime.now().isoformat()
        }
        
        save_users(users)
        
        return jsonify({'message': 'User created successfully'})
        
    except Exception as e:
        return jsonify({'error': 'Failed to create user'}), 500

@auth_bp.route('/api/auth/users/<username>', methods=['DELETE'])
def delete_user(username):
    """Delete user (admin only)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        
        if not payload or payload['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        if username == 'admin':
            return jsonify({'error': 'Cannot delete admin user'}), 400
        
        users = load_users()
        
        if username not in users:
            return jsonify({'error': 'User not found'}), 404
        
        del users[username]
        save_users(users)
        
        return jsonify({'message': 'User deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': 'Failed to delete user'}), 500

@auth_bp.route('/api/auth/users/<username>/password', methods=['PUT'])
def change_password(username):
    """Change user password"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Users can only change their own password, unless they're admin
        if payload['username'] != username and payload['role'] != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        new_password = data.get('password')
        
        if not new_password:
            return jsonify({'error': 'Password required'}), 400
        
        users = load_users()
        
        if username not in users:
            return jsonify({'error': 'User not found'}), 404
        
        users[username]['password'] = hash_password(new_password)
        save_users(users)
        
        return jsonify({'message': 'Password changed successfully'})
        
    except Exception as e:
        return jsonify({'error': 'Failed to change password'}), 500

