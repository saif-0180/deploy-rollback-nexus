# Frontend Build Stage
FROM node:18-alpine AS frontend-build
WORKDIR /app
COPY package*.json ./
RUN npm install && npm install -g vite
#RUN npm config set strict-ssl false && \
#    npm config set registry https://registry.npmjs.org/ && \
#    npm install --no-optional --no-audit --no-fund
#RUN npm config set strict-ssl false && \
#    npm install -g vite
COPY . .
#RUN npm config set strict-ssl false && \
#    npx vite build
RUN vite build

# Backend Build Stage
FROM python:3.10-slim AS backend-build
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Final Stage
FROM python:3.10-slim
WORKDIR /app

# Create user and group with same IDs as host infadm user
ARG USER_ID=1003
ARG GROUP_ID=1002
ARG USERNAME=infadm
ARG GROUP_NAME=aimsys

# Create group and user with specific IDs
#RUN groupadd -g $GROUP_ID $USERNAME && \
#    useradd -u $USER_ID -g $GROUP_ID -m -s /bin/bash $USERNAME

RUN groupadd -g $GROUP_ID $GROUP_NAME && \
    useradd -u $USER_ID -g $GROUP_NAME -m -s /bin/bash $USERNAME

# Copy frontend build from frontend stage
COPY --from=frontend-build /app/dist /app/frontend/dist

# Copy backend from backend stage
COPY --from=backend-build /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY backend /app/backend

# Install ansible, SSH dependencies, and PostgreSQL client
RUN apt-get update -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false && \
    apt-get install -y \
        ansible \
        openssh-client \
        sshpass \
        procps \
        sudo \
        postgresql-client \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create necessary directories with proper ownership
RUN mkdir -p /home/users/$USERNAME/.ssh \
             /app/fixfiles/AllFts \
             /app/logs \
             /tmp/ansible-ssh \
             /app/ssh-keys && \
    chmod 700 /home/users/$USERNAME/.ssh && \
    chmod -R 777 /tmp/ansible-ssh && \
    chown -R $USERNAME:$GROUP_NAME /app && \
    chown -R $USERNAME:$GROUP_NAME /home/users/$USERNAME

# Copy entrypoint script and set permissions
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    chown $USERNAME:$GROUP_NAME /entrypoint.sh

# Give sudo access to infadm user (if needed for ansible)
RUN echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Switch to the infadm user
USER $USERNAME

# Set HOME environment variable
ENV HOME=/home/users/$USERNAME

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
