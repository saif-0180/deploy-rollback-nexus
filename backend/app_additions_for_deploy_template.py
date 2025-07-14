
# Add these imports to the top of your app.py file (after existing imports)
from deploy_template_routes import deploy_template_bp

# Add this line after your existing blueprint registrations
app.register_blueprint(deploy_template_bp)

# Add these helper methods to your Flask app class or as global functions in app.py:

def run_ansible_command(command, logs):
    """Run ansible command and capture output"""
    try:
        import subprocess
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend(result.stderr.split('\n'))
        
        if result.returncode == 0:
            logs.append(f"Command executed successfully: {' '.join(command)}")
            return True
        else:
            logs.append(f"Command failed with return code {result.returncode}: {' '.join(command)}")
            return False
            
    except subprocess.TimeoutExpired:
        logs.append(f"Command timed out: {' '.join(command)}")
        return False
    except Exception as e:
        logs.append(f"Error executing command: {str(e)}")
        return False

def run_command_with_logging(command, logs):
    """Run command and capture output with logging"""
    try:
        import subprocess
        logs.append(f"Executing command: {' '.join(command)}")
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    logs.append(f"STDOUT: {line}")
        
        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip():
                    logs.append(f"STDERR: {line}")
        
        if result.returncode == 0:
            logs.append(f"Command completed successfully")
            return True
        else:
            logs.append(f"Command failed with return code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        logs.append(f"Command timed out after 10 minutes")
        return False
    except Exception as e:
        logs.append(f"Error executing command: {str(e)}")
        return False

# Add these as methods to your Flask app instance:
app.run_ansible_command = run_ansible_command
app.run_command_with_logging = run_command_with_logging
