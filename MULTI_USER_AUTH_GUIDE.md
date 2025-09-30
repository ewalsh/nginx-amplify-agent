# Multi-User Authentication for NGINX Monitoring System

This guide extends the Django receiver to support multiple users with proper data isolation.

## Updated Database Schema

```sql
-- User organizations/tenants
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API keys for agent authentication
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    organization_id INTEGER REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);

-- User memberships
CREATE TABLE organization_memberships (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id),
    organization_id INTEGER REFERENCES organizations(id),
    role VARCHAR(50) DEFAULT 'member', -- 'admin', 'member', 'viewer'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, organization_id)
);

-- Add organization to monitored objects
ALTER TABLE monitored_objects ADD COLUMN organization_id INTEGER REFERENCES organizations(id);
CREATE INDEX idx_objects_org ON monitored_objects(organization_id);
```

## Updated Django Models

```python
from django.db import models
from django.contrib.auth.models import User
import hashlib
import secrets

class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class ApiKey(models.Model):
    key_hash = models.CharField(max_length=255, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    @classmethod
    def generate_key(cls, organization, name):
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = cls.objects.create(
            key_hash=key_hash,
            organization=organization,
            name=name
        )
        return raw_key, api_key
    
    @classmethod
    def authenticate(cls, raw_key):
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            return cls.objects.get(key_hash=key_hash, is_active=True)
        except cls.DoesNotExist:
            return None

class OrganizationMembership(models.Model):
    ROLES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=ROLES, default='member')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'organization']

class MonitoredObject(models.Model):
    # ... existing fields ...
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'monitored_objects'
        indexes = [
            models.Index(fields=['uuid']),
            models.Index(fields=['object_type']),
            models.Index(fields=['organization']),
        ]
```

## Authentication Middleware

```python
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from .models import ApiKey
import logging

logger = logging.getLogger(__name__)

class ApiKeyAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Skip auth for admin and non-API endpoints
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return None
        
        # Extract API key from URL path or header
        api_key = None
        
        # Method 1: From URL path (e.g., /api_key/agent/)
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) > 0 and len(path_parts[0]) == 43:  # API key length
            api_key = path_parts[0]
            # Remove API key from path for routing
            request.path_info = '/' + '/'.join(path_parts[1:])
        
        # Method 2: From Authorization header
        if not api_key:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                api_key = auth_header[7:]
        
        if not api_key:
            return JsonResponse({'error': 'API key required'}, status=401)
        
        # Authenticate API key
        api_key_obj = ApiKey.authenticate(api_key)
        if not api_key_obj:
            return JsonResponse({'error': 'Invalid API key'}, status=401)
        
        # Update last used timestamp
        from django.utils import timezone
        api_key_obj.last_used = timezone.now()
        api_key_obj.save(update_fields=['last_used'])
        
        # Attach organization to request
        request.organization = api_key_obj.organization
        request.api_key = api_key_obj
        
        return None
```

## Updated Views with Organization Filtering

```python
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class AgentRegistrationView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Get organization from middleware
            organization = request.organization
            
            obj_uuid = data.get('uuid')
            if not obj_uuid:
                return JsonResponse({'error': 'UUID required'}, status=400)
            
            # Create or update monitored object with organization
            obj, created = MonitoredObject.objects.get_or_create(
                uuid=obj_uuid,
                organization=organization,
                defaults={
                    'object_type': data.get('type', 'system'),
                    'hostname': data.get('hostname'),
                    'imagename': data.get('imagename'),
                    'is_active': True
                }
            )
            
            return JsonResponse({
                'config': {},
                'messages': [],
                'versions': {'current': '1.7.0', 'obsolete': '1.0.0', 'old': '1.5.0'},
                'capabilities': {'phpfpm': True, 'mysql': True},
                'objects': []
            })
            
        except Exception as e:
            logger.error(f"Error in agent registration: {e}")
            return JsonResponse({'error': str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class MetricsUpdateView(View):
    def _process_single_payload(self, payload):
        obj_data = payload.get('object', {})
        obj_uuid = obj_data.get('uuid')
        
        if not obj_uuid:
            return
        
        # Only access objects within the authenticated organization
        try:
            monitored_obj = MonitoredObject.objects.get(
                uuid=obj_uuid,
                organization=self.request.organization
            )
        except MonitoredObject.DoesNotExist:
            logger.warning(f"Object {obj_uuid} not found in organization {self.request.organization}")
            return
        
        # Process metrics, metadata, events as before...
```

## User Dashboard Views

```python
@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        # Get user's organizations
        memberships = OrganizationMembership.objects.filter(user=request.user)
        organizations = [m.organization for m in memberships]
        
        # Get objects for user's organizations
        objects = MonitoredObject.objects.filter(
            organization__in=organizations,
            is_active=True
        )
        
        context = {
            'organizations': organizations,
            'objects': objects,
        }
        return render(request, 'dashboard.html', context)

@method_decorator(login_required, name='dispatch')
class MetricsAPIView(View):
    def get(self, request, object_uuid):
        # Ensure user has access to this object
        membership = get_object_or_404(
            OrganizationMembership,
            user=request.user
        )
        
        monitored_obj = get_object_or_404(
            MonitoredObject,
            uuid=object_uuid,
            organization__in=[m.organization for m in 
                OrganizationMembership.objects.filter(user=request.user)]
        )
        
        # Get recent metrics
        metrics = Metric.objects.filter(
            object=monitored_obj,
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-timestamp')[:1000]
        
        return JsonResponse({
            'object': {
                'uuid': monitored_obj.uuid,
                'hostname': monitored_obj.hostname,
                'type': monitored_obj.object_type
            },
            'metrics': [
                {
                    'name': m.metric_name,
                    'value': m.metric_value,
                    'timestamp': m.timestamp.isoformat()
                }
                for m in metrics
            ]
        })
```

## URL Configuration

```python
from django.urls import path, include
from . import views

urlpatterns = [
    # Agent endpoints (with API key in path)
    path('<str:api_key>/agent/', views.AgentRegistrationView.as_view()),
    path('<str:api_key>/update/', views.MetricsUpdateView.as_view()),
    
    # User dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('api/metrics/<str:object_uuid>/', views.MetricsAPIView.as_view()),
    
    # Admin
    path('admin/', admin.site.urls),
]
```

## Management Commands

```python
# management/commands/create_organization.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from myapp.models import Organization, OrganizationMembership, ApiKey

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--name', required=True)
        parser.add_argument('--slug', required=True)
        parser.add_argument('--admin-email', required=True)
    
    def handle(self, *args, **options):
        # Create organization
        org = Organization.objects.create(
            name=options['name'],
            slug=options['slug']
        )
        
        # Create admin user if doesn't exist
        user, created = User.objects.get_or_create(
            email=options['admin_email'],
            defaults={'username': options['admin_email']}
        )
        
        # Create membership
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role='admin'
        )
        
        # Generate API key
        raw_key, api_key = ApiKey.generate_key(org, 'Default Key')
        
        self.stdout.write(f"Organization created: {org.name}")
        self.stdout.write(f"API Key: {raw_key}")
        self.stdout.write(f"Agent URL: http://yourserver/{raw_key}/agent/")
```

## Agent Configuration

Configure each agent with organization-specific API key:

```ini
# agent.conf for Organization A
[cloud]
api_url = http://yourserver/abc123def456.../1.4

# agent.conf for Organization B  
[cloud]
api_url = http://yourserver/xyz789uvw012.../1.4
```

## Usage

1. **Create organizations:**
   ```bash
   python manage.py create_organization --name "Company A" --slug "company-a" --admin-email "admin@company-a.com"
   ```

2. **Configure agents:**
   Each organization gets unique API keys for their agents

3. **Data isolation:**
   - Users only see data from their organizations
   - API keys only access their organization's data
   - Database queries automatically filter by organization

This ensures complete data isolation between different users and organizations while maintaining the same monitoring functionality.