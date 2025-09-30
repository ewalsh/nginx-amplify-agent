# NGINX Amplify Agent - Django Receiver Implementation Guide

This guide shows how to create a Django application that receives and stores metrics from the NGINX Amplify Agent.

## Overview

The NGINX Amplify Agent sends JSON payloads to two main endpoints:
- `POST /agent/` - Initial registration and configuration updates
- `POST /update/` - Regular metrics and data updates

## Database Schema

### PostgreSQL Table Structure

```sql
-- Monitored objects (systems, containers, nginx instances)
CREATE TABLE monitored_objects (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(255) UNIQUE NOT NULL,
    object_type VARCHAR(50) NOT NULL, -- 'system', 'container', 'nginx'
    hostname VARCHAR(255),
    imagename VARCHAR(255),
    local_id VARCHAR(255),
    root_uuid VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Time-series metrics data
CREATE TABLE metrics (
    id BIGSERIAL PRIMARY KEY,
    object_id INTEGER REFERENCES monitored_objects(id),
    metric_name VARCHAR(255) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System metadata
CREATE TABLE system_metadata (
    id SERIAL PRIMARY KEY,
    object_id INTEGER REFERENCES monitored_objects(id),
    uname TEXT,
    platform VARCHAR(255),
    architecture VARCHAR(255),
    processor VARCHAR(255),
    python_version VARCHAR(50),
    agent_version VARCHAR(50),
    boot_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events and logs
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    object_id INTEGER REFERENCES monitored_objects(id),
    level VARCHAR(20) NOT NULL, -- 'INFO', 'WARN', 'ERROR', 'DEBUG'
    message TEXT NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent configurations
CREATE TABLE agent_configs (
    id SERIAL PRIMARY KEY,
    object_id INTEGER REFERENCES monitored_objects(id),
    config_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_metrics_object_timestamp ON metrics(object_id, timestamp);
CREATE INDEX idx_metrics_name_timestamp ON metrics(metric_name, timestamp);
CREATE INDEX idx_events_object_timestamp ON events(object_id, event_timestamp);
CREATE INDEX idx_objects_uuid ON monitored_objects(uuid);
CREATE INDEX idx_objects_type ON monitored_objects(object_type);
```

## Django Models

Create `models.py`:

```python
from django.db import models
from django.contrib.postgres.fields import JSONField

class MonitoredObject(models.Model):
    OBJECT_TYPES = [
        ('system', 'System'),
        ('container', 'Container'),
        ('nginx', 'NGINX'),
    ]
    
    uuid = models.CharField(max_length=255, unique=True)
    object_type = models.CharField(max_length=50, choices=OBJECT_TYPES)
    hostname = models.CharField(max_length=255, null=True, blank=True)
    imagename = models.CharField(max_length=255, null=True, blank=True)
    local_id = models.CharField(max_length=255, null=True, blank=True)
    root_uuid = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'monitored_objects'
        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['object_type']),
        ]
    
    def __str__(self):
        return f"{self.object_type}:{self.hostname or self.imagename}:{self.uuid[:8]}"

class Metric(models.Model):
    object = models.ForeignKey(MonitoredObject, on_delete=models.CASCADE)
    metric_name = models.CharField(max_length=255)
    metric_value = models.FloatField()
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'metrics'
        indexes = [
            models.Index(fields=['object', 'timestamp']),
            models.Index(fields=['metric_name', 'timestamp']),
        ]

class SystemMetadata(models.Model):
    object = models.ForeignKey(MonitoredObject, on_delete=models.CASCADE)
    uname = models.TextField(null=True, blank=True)
    platform = models.CharField(max_length=255, null=True, blank=True)
    architecture = models.CharField(max_length=255, null=True, blank=True)
    processor = models.CharField(max_length=255, null=True, blank=True)
    python_version = models.CharField(max_length=50, null=True, blank=True)
    agent_version = models.CharField(max_length=50, null=True, blank=True)
    boot_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_metadata'

class Event(models.Model):
    LEVELS = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARN', 'Warning'),
        ('ERROR', 'Error'),
    ]
    
    object = models.ForeignKey(MonitoredObject, on_delete=models.CASCADE)
    level = models.CharField(max_length=20, choices=LEVELS)
    message = models.TextField()
    event_timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'events'
        indexes = [
            models.Index(fields=['object', 'event_timestamp']),
        ]

class AgentConfig(models.Model):
    object = models.ForeignKey(MonitoredObject, on_delete=models.CASCADE)
    config_data = JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'agent_configs'
```

## Django Views

Create `views.py`:

```python
import json
import logging
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.db import transaction
from .models import MonitoredObject, Metric, SystemMetadata, Event, AgentConfig

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class AgentRegistrationView(View):
    """Handle agent registration and configuration requests"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            logger.info(f"Agent registration: {data}")
            
            # Extract object information
            obj_uuid = data.get('uuid')
            obj_type = data.get('type', 'system')
            hostname = data.get('hostname')
            imagename = data.get('imagename')
            
            if not obj_uuid:
                return JsonResponse({'error': 'UUID required'}, status=400)
            
            # Create or update monitored object
            obj, created = MonitoredObject.objects.get_or_create(
                uuid=obj_uuid,
                defaults={
                    'object_type': obj_type,
                    'hostname': hostname,
                    'imagename': imagename,
                    'is_active': True
                }
            )
            
            if not created:
                obj.hostname = hostname or obj.hostname
                obj.imagename = imagename or obj.imagename
                obj.is_active = True
                obj.save()
            
            # Return configuration response
            response = {
                'config': {},
                'messages': [],
                'versions': {
                    'current': '1.7.0',
                    'obsolete': '1.0.0',
                    'old': '1.5.0'
                },
                'capabilities': {
                    'phpfpm': True,
                    'mysql': True
                },
                'objects': []
            }
            
            return JsonResponse(response)
            
        except Exception as e:
            logger.error(f"Error in agent registration: {e}")
            return JsonResponse({'error': str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class MetricsUpdateView(View):
    """Handle metrics and data updates"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            logger.info(f"Metrics update received")
            
            with transaction.atomic():
                self._process_payload(data)
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Error processing metrics: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def _process_payload(self, data):
        """Process the complete payload"""
        if isinstance(data, list):
            # Handle array of payloads
            for payload in data:
                self._process_single_payload(payload)
        else:
            # Handle single payload
            self._process_single_payload(data)
    
    def _process_single_payload(self, payload):
        """Process a single payload object"""
        # Get object information
        obj_data = payload.get('object', {})
        obj_uuid = obj_data.get('uuid')
        
        if not obj_uuid:
            logger.warning("No UUID in payload object")
            return
        
        try:
            monitored_obj = MonitoredObject.objects.get(uuid=obj_uuid)
        except MonitoredObject.DoesNotExist:
            logger.warning(f"Object {obj_uuid} not found, creating...")
            monitored_obj = MonitoredObject.objects.create(
                uuid=obj_uuid,
                object_type=obj_data.get('type', 'system'),
                hostname=obj_data.get('hostname'),
                imagename=obj_data.get('imagename')
            )
        
        # Process metrics
        metrics_data = payload.get('metrics', {})
        self._store_metrics(monitored_obj, metrics_data)
        
        # Process metadata
        meta_data = payload.get('meta', {})
        self._store_metadata(monitored_obj, meta_data)
        
        # Process events
        events_data = payload.get('events', [])
        self._store_events(monitored_obj, events_data)
        
        # Process configs
        config_data = payload.get('configs', {})
        if config_data:
            self._store_config(monitored_obj, config_data)
    
    def _store_metrics(self, obj, metrics_data):
        """Store metrics data"""
        metrics_to_create = []
        
        for metric_name, values in metrics_data.items():
            for timestamp, value in values:
                metrics_to_create.append(Metric(
                    object=obj,
                    metric_name=metric_name,
                    metric_value=float(value),
                    timestamp=datetime.fromtimestamp(timestamp)
                ))
        
        if metrics_to_create:
            Metric.objects.bulk_create(metrics_to_create, batch_size=1000)
            logger.info(f"Stored {len(metrics_to_create)} metrics for {obj}")
    
    def _store_metadata(self, obj, meta_data):
        """Store system metadata"""
        system_meta = meta_data.get('system', {})
        if not system_meta:
            return
        
        SystemMetadata.objects.update_or_create(
            object=obj,
            defaults={
                'uname': system_meta.get('uname'),
                'platform': system_meta.get('platform'),
                'architecture': system_meta.get('architecture'),
                'processor': system_meta.get('processor'),
                'python_version': system_meta.get('python_version'),
                'agent_version': system_meta.get('agent_version'),
                'boot_time': datetime.fromtimestamp(system_meta['boot_time']) if system_meta.get('boot_time') else None
            }
        )
    
    def _store_events(self, obj, events_data):
        """Store events"""
        events_to_create = []
        
        for event in events_data:
            events_to_create.append(Event(
                object=obj,
                level=event.get('level', 'INFO'),
                message=event.get('message', ''),
                event_timestamp=datetime.fromtimestamp(event.get('timestamp', 0))
            ))
        
        if events_to_create:
            Event.objects.bulk_create(events_to_create)
    
    def _store_config(self, obj, config_data):
        """Store configuration data"""
        AgentConfig.objects.create(
            object=obj,
            config_data=config_data
        )
```

## URL Configuration

Create `urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('agent/', views.AgentRegistrationView.as_view(), name='agent_registration'),
    path('update/', views.MetricsUpdateView.as_view(), name='metrics_update'),
]
```

## Settings Configuration

Add to `settings.py`:

```python
# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'nginx_monitoring',
        'USER': 'monitoring_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/nginx_monitoring/django.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Allow large request bodies for metrics
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
```

## Startup Script

Create `start_monitoring_system.sh`:

```bash
#!/bin/bash

# NGINX Monitoring System Startup Script
# This script sets up and starts the complete monitoring infrastructure

set -e

# Configuration
PROJECT_DIR="/opt/nginx-monitoring"
VENV_DIR="$PROJECT_DIR/venv"
DB_NAME="nginx_monitoring"
DB_USER="monitoring_user"
DB_PASSWORD="secure_password_here"
DJANGO_PORT="8000"
LOG_DIR="/var/log/nginx_monitoring"

echo "Starting NGINX Monitoring System Setup..."

# Create directories
sudo mkdir -p $PROJECT_DIR
sudo mkdir -p $LOG_DIR
sudo chown $USER:$USER $PROJECT_DIR
sudo chown $USER:$USER $LOG_DIR

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx

# Setup PostgreSQL
echo "Setting up PostgreSQL database..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" || echo "Database already exists"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" || echo "User already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -c "ALTER USER $DB_USER CREATEDB;"

# Setup Python virtual environment
echo "Setting up Python environment..."
cd $PROJECT_DIR
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install django psycopg2-binary gunicorn

# Create Django project if it doesn't exist
if [ ! -d "$PROJECT_DIR/monitoring_project" ]; then
    echo "Creating Django project..."
    django-admin startproject monitoring_project .
    cd monitoring_project
    python manage.py startapp metrics_receiver
fi

# Apply database migrations
echo "Applying database migrations..."
cd $PROJECT_DIR/monitoring_project
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional)
echo "Creating Django superuser..."
echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@example.com', 'admin123') if not User.objects.filter(username='admin').exists() else None" | python manage.py shell

# Setup systemd service
echo "Setting up systemd service..."
sudo tee /etc/systemd/system/nginx-monitoring.service > /dev/null <<EOF
[Unit]
Description=NGINX Monitoring Django Application
After=network.target postgresql.service

[Service]
Type=exec
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR/monitoring_project
Environment=PATH=$VENV_DIR/bin
ExecStart=$VENV_DIR/bin/gunicorn --bind 0.0.0.0:$DJANGO_PORT monitoring_project.wsgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Setup nginx reverse proxy
echo "Setting up NGINX reverse proxy..."
sudo tee /etc/nginx/sites-available/nginx-monitoring > /dev/null <<EOF
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:$DJANGO_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 10M;
    }

    location /static/ {
        alias $PROJECT_DIR/monitoring_project/static/;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/nginx-monitoring /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Enable and start services
echo "Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable nginx-monitoring
sudo systemctl start nginx-monitoring
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create log rotation
sudo tee /etc/logrotate.d/nginx-monitoring > /dev/null <<EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}
EOF

echo "Setup complete!"
echo "Django admin: http://localhost/admin (admin/admin123)"
echo "Metrics endpoint: http://localhost/agent/"
echo "Update endpoint: http://localhost/update/"
echo ""
echo "To configure the NGINX Amplify Agent, update the agent.conf:"
echo "  [cloud]"
echo "  api_url = http://localhost/1.4"
echo ""
echo "Service status:"
systemctl status nginx-monitoring --no-pager
systemctl status nginx --no-pager
systemctl status postgresql --no-pager
```

## Usage Instructions

1. **Run the startup script:**
   ```bash
   chmod +x start_monitoring_system.sh
   sudo ./start_monitoring_system.sh
   ```

2. **Configure the NGINX Amplify Agent:**
   ```ini
   # In agent.conf
   [cloud]
   api_url = http://your-server-ip/1.4
   ```

3. **Start collecting metrics:**
   ```bash
   # Point the agent to your Django receiver
   python3 nginx-amplify-agent.py start --config /path/to/agent.conf
   ```

4. **Monitor the system:**
   - Django Admin: `http://your-server/admin`
   - Logs: `/var/log/nginx_monitoring/`
   - Database: Connect to PostgreSQL to query metrics

## API Endpoints

- `POST /agent/` - Agent registration
- `POST /update/` - Metrics updates
- `GET /admin/` - Django admin interface

## Performance Considerations

1. **Database Indexing:** Ensure proper indexes on timestamp and object_id fields
2. **Bulk Operations:** Use bulk_create for inserting large batches of metrics
3. **Data Retention:** Implement data cleanup for old metrics
4. **Connection Pooling:** Use connection pooling for high-volume deployments

## Monitoring and Alerting

Add monitoring for:
- Database disk usage
- API response times
- Failed metric ingestion
- Agent connectivity status

This setup provides a complete monitoring infrastructure that can receive, store, and manage NGINX Amplify Agent data using Django and PostgreSQL.