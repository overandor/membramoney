#!/usr/bin/env python3
"""
Vercel Serverless Function for Real Solana Miner
Deploy real Solana mining to Vercel
"""

import json
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

from real_solana_miner import app, real_miner

def handler(request):
    """Vercel serverless function handler"""
    try:
        # Parse the request
        method = request.method
        path = request.path
        headers = dict(request.headers)
        body = request.body
        
        if body and headers.get('content-type', '').startswith('application/json'):
            body = json.loads(body.decode('utf-8'))
        else:
            body = None
        
        # Create Flask test request context
        with app.test_request_context(
            path=path,
            method=method,
            headers=headers,
            json=body
        ):
            # Route the request
            response = app.dispatch_request()
            
            # Return response
            return response
    
    except Exception as e:
        return json.dumps({'error': str(e)}), 500, {'Content-Type': 'application/json'}
