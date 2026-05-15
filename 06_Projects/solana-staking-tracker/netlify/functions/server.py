import json
from flask import Flask, request

app = Flask(__name__)

# Import Marinade system
import sys
sys.path.append('.')
from marinade_deploy import MarinadeDeploySystem

# Initialize system
system = MarinadeDeploySystem()

def handler(event, context):
    """Netlify function handler"""
    
    # Create Flask test context
    with app.test_request_context(
        path=event.get('path', '/'),
        method=event.get('httpMethod', 'GET'),
        json=event.get('body', {}) if event.get('body') else None
    ):
        # Route to appropriate handler
        path = event.get('path', '/')
        
        if path == '/':
            return system.app.dispatch_request()
        elif path.startswith('/api/'):
            return system.app.dispatch_request()
        else:
            return {"statusCode": 404, "body": "Not found"}
