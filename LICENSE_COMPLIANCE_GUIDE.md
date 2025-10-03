# BSD License Compliance Guide for NGINX Amplify Agent

This guide shows exactly how to comply with the BSD 2-Clause license requirements when using the NGINX Amplify Agent in your commercial service.

## Requirement 1: Keep Copyright Notice in Agent Source Files

### ✅ What to do:
Keep the original copyright header in any agent source files you modify or distribute.

### Example - Modified Agent File:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (C) Nginx, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.
"""

# Your modifications start here
import sys
import subprocess

def install_if_missing(module):
    # Your custom code...
```

## Requirement 2: Include BSD License Text When Distributing Agent

### ✅ What to do:
Include the complete license text when you distribute the agent (as packages, containers, or installations).

### Option A - Separate LICENSE File:
Create `LICENSE-NGINX-AMPLIFY-AGENT.txt`:
```
Copyright (C) Nginx, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.
```

### Option B - In Installation Documentation:
```bash
# Include in your installation script
cat << 'EOF' > /opt/your-service/THIRD-PARTY-LICENSES.txt
NGINX Amplify Agent
Copyright (C) Nginx, Inc.
Licensed under BSD 2-Clause License

[Full license text here...]
EOF
```

### Option C - In Docker Container:
```dockerfile
# Dockerfile
FROM python:3.11-slim
COPY LICENSE-NGINX-AMPLIFY-AGENT.txt /usr/share/licenses/
COPY modified-agent/ /opt/agent/
```

## Requirement 3: Credit NGINX Inc. in Documentation

### ✅ What to do:
Include attribution in your service documentation, website, or user-facing materials.

### Example - Service Documentation:
```markdown
## Third-Party Components

This monitoring service includes software developed by NGINX Inc.:

- **NGINX Amplify Agent**: Used for collecting system and NGINX metrics
- **Source**: https://github.com/nginxinc/nginx-amplify-agent
- **License**: BSD 2-Clause License
- **Copyright**: Copyright (C) Nginx, Inc.
```

### Example - Website Footer:
```html
<footer>
  <p>Powered by NGINX Amplify Agent technology</p>
  <p>NGINX Amplify Agent © Nginx, Inc. - BSD Licensed</p>
</footer>
```

### Example - API Documentation:
```yaml
# OpenAPI spec
info:
  title: "Your Monitoring API"
  description: |
    This API provides monitoring capabilities using the NGINX Amplify Agent.
    
    **Third-Party Components:**
    - NGINX Amplify Agent (Copyright © Nginx, Inc., BSD 2-Clause License)
```

### Example - README.md:
```markdown
# Your Monitoring Service

## Acknowledgments

This project uses the NGINX Amplify Agent:
- Copyright (C) Nginx, Inc.
- Licensed under BSD 2-Clause License
- Original project: https://github.com/nginxinc/nginx-amplify-agent
```

## Practical Implementation Checklist

### ✅ For Source Code Distribution:
- [ ] Keep copyright headers in all modified agent files
- [ ] Include `LICENSE-NGINX-AMPLIFY-AGENT.txt` in your distribution
- [ ] Add attribution to your project's README

### ✅ For Binary/Package Distribution:
- [ ] Include license file in package (e.g., `/usr/share/licenses/`)
- [ ] Add attribution to package description
- [ ] Include in installation documentation

### ✅ For SaaS/Web Service:
- [ ] Add attribution to website footer or about page
- [ ] Include in API documentation
- [ ] Mention in terms of service or legal notices

### ✅ For Docker/Container Distribution:
- [ ] Copy license file to container
- [ ] Add attribution to container labels
- [ ] Include in container documentation

## Sample Files

### THIRD-PARTY-NOTICES.txt
```
Your Monitoring Service uses the following third-party components:

NGINX Amplify Agent
Copyright (C) Nginx, Inc.
Licensed under BSD 2-Clause License
Source: https://github.com/nginxinc/nginx-amplify-agent

[Full BSD license text follows...]
```

### package.json (if using npm)
```json
{
  "name": "your-monitoring-service",
  "licenses": [
    {
      "type": "BSD-2-Clause",
      "name": "NGINX Amplify Agent",
      "url": "https://github.com/nginxinc/nginx-amplify-agent/blob/master/LICENSE"
    }
  ]
}
```

### Docker Label
```dockerfile
LABEL org.opencontainers.image.licenses="Proprietary (includes BSD-2-Clause components)"
LABEL org.opencontainers.image.vendor="Your Company (includes NGINX Inc. components)"
```

## What You DON'T Need to Do

### ❌ NOT Required:
- Share your receiver/dashboard source code
- Pay royalties to NGINX Inc.
- Get permission before using
- Mention NGINX in your service name
- Make your modifications open source
- Contribute changes back to NGINX

### ✅ Only Required:
- Keep copyright notices in agent files
- Include license text with distributions
- Credit NGINX Inc. in documentation

This simple compliance ensures you can legally use the NGINX Amplify Agent in your commercial monitoring service.