#!/usr/bin/env python3
"""
Netlify Function Handler for Real Solana Miner
Deploy real Solana mining to Netlify Functions
"""

import json
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

from real_solana_miner import app, real_miner

def handler(event, context):
    """Netlify function handler"""
    try:
        # Parse the event
        path = event.get('path', '/')
        method = event.get('httpMethod', 'GET')
        headers = event.get('headers', {})
        body = event.get('body', '{}')
        
        if body and headers.get('content-type', '').startswith('application/json'):
            body = json.loads(body)
        
        # Create Flask test request context
        with app.test_request_context(
            path=path,
            method=method,
            headers=headers,
            json=body if body != '{}' else None
        ):
            # Route the request
            if path == '/':
                response = app.dispatch_request()
            elif path.startswith('/api/'):
                response = app.dispatch_request()
            else:
                response = app.dispatch_request()
            
            # Convert Flask response to Netlify format
            return {
                'statusCode': response.status_code,
                'headers': dict(response.headers),
                'body': response.get_data(as_text=True)
            }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
