
# Frontend Build Stage
FROM node:18-alpine as frontend-build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Backend Build Stage
FROM python:3.11-slim as backend-build

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Final Stage
FROM python:3.11-slim

WORKDIR /app

# Copy frontend build from frontend stage
COPY --from=frontend-build /app/dist /app/frontend/dist

# Copy backend from backend stage
COPY --from=backend-build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY backend /app/backend

# Install ansible and SSH dependencies
RUN apt-get update && \
    apt-get install -y ansible openssh-client sshpass procps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /root/.ssh /app/fixfiles/AllFts /app/logs /tmp/ansible-ssh /app/ssh-keys && \
    chmod 700 /root/.ssh && \
    chmod -R 777 /tmp/ansible-ssh

# Create directory for fix files and ensure proper permissions for ansible control path
RUN mkdir -p /app/fixfiles/AllFts /tmp/ansible-ssh /app/ssh-keys /app/logs && \
    chmod -R 777 /tmp/ansible-ssh && \
    chmod -R 777 /app/logs

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=backend/app.py
ENV FLASK_ENV=production
ENV ANSIBLE_HOST_KEY_CHECKING=False
ENV ANSIBLE_SSH_CONTROL_PATH=/tmp/ansible-ssh/%h-%p-%r
ENV ANSIBLE_SSH_CONTROL_PATH_DIR=/tmp/ansible-ssh
ENV PYTHONUNBUFFERED=1
ENV LOG_FILE_PATH=/app/logs/application.log
ENV DEPLOYMENT_LOGS_DIR=/app/logs

# Start with entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
# CMD to run the Flask server
CMD ["python", "backend/app.py"]
