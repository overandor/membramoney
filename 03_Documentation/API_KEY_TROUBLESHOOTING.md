# API Key Troubleshooting Guide

## Groq API Key Error (401 Invalid API Key)

### Issue
The Groq API key is returning a 401 error with "Invalid API Key" message.

### Solutions

#### 1. Regenerate Groq API Key
1. Go to https://console.groq.com/
2. Log in to your account
3. Navigate to API Keys section
4. Create a new API key
5. Update your environment variable:
```bash
export GROQ_API_KEY=your_new_groq_key_here
```

#### 2. Check Key Format
Groq API keys should start with `gsk_` and be formatted like:
```
gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 3. Verify Key Permissions
- Ensure the key has the correct permissions
- Check if the key is active (not revoked)
- Verify the key hasn't expired

#### 4. Test the Key
```bash
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY"
```

### Current Status
The application now has **fallback mode** enabled, so it will continue to work even with invalid API keys:
- Trading signals use rule-based fallback
- AI analysis uses pre-programmed responses
- All other features remain functional

## GitHub API Token Error (401 Bad Credentials)

### Issue
GitHub API token is returning 401 "Bad credentials" error.

### Solutions

#### 1. Create New GitHub Personal Access Token
1. Go to GitHub Settings → Developer Settings → Personal Access Tokens
2. Click "Generate new token" (classic)
3. Select scopes: `repo` (for full repository access)
4. Generate and copy the token
5. Update environment variable:
```bash
export GITHUB_TOKEN=your_new_github_token_here
```

#### 2. Verify Token Format
GitHub tokens should start with `ghp_` and be formatted like:
```
ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 3. Check Token Permissions
- Ensure `repo` scope is selected
- Verify token is not expired
- Check if token has been revoked

#### 4. Test the Token
```bash
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user
```

## Hugging Face Token Error

### Issue
Hugging Face API endpoint is returning HTML error instead of JSON.

### Solutions

#### 1. Create Hugging Face Access Token
1. Go to https://huggingface.co/settings/tokens
2. Click "New token"
3. Select token type: "Write" (for creating spaces)
4. Generate and copy the token
5. Update environment variable:
```bash
export HUGGING_FACE_TOKEN=your_new_huggingface_token_here
```

#### 2. Verify Token Format
Hugging Face tokens should start with `hf_` and be formatted like:
```
hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 3. Check Token Permissions
- Ensure token has write access
- Verify token is active
- Check account status

## Quick Fix Script

Run this script to update all your API keys:

```bash
#!/bin/bash
# API Key Update Script

echo "Enter your new Groq API key:"
read -s GROQ_KEY
export GROQ_API_KEY=$GROQ_KEY

echo "Enter your new GitHub token:"
read -s GITHUB_KEY
export GITHUB_TOKEN=$GITHUB_KEY

echo "Enter your new Hugging Face token:"
read -s HF_KEY
export HUGGING_FACE_TOKEN=$HF_KEY

# Add to .env file
echo "GROQ_API_KEY=$GROQ_KEY" >> .env
echo "GITHUB_TOKEN=$GITHUB_KEY" >> .env
echo "HUGGING_FACE_TOKEN=$HF_KEY" >> .env

echo "✅ API keys updated successfully"
```

## Application Status

### Current Functionality
✅ **Working Features:**
- MetaMask wallet connection
- Dashboard display
- Trading signal generation (fallback mode)
- Trade execution
- Portfolio tracking
- Real-time updates

⚠️ **Limited Features (due to API keys):**
- AI-powered analysis (using fallback responses)
- GitHub auto-deployment
- Hugging Face Spaces deployment

### Fallback Mode
The application automatically switches to fallback mode when API keys are invalid:
- **Trading Signals**: Rule-based instead of AI-generated
- **AI Analysis**: Pre-programmed responses based on query keywords
- **Deployment**: Skipped (manual deployment required)

## Testing API Keys

### Test All Keys at Once
```bash
# Test Groq
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY"

# Test GitHub
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user

# Test Hugging Face
curl -H "Authorization: Bearer $HUGGING_FACE_TOKEN" \
  https://huggingface.co/api/whoami
```

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for sensitive data
3. **Rotate keys regularly** (every 90 days)
4. **Use least privilege** access (only needed scopes)
5. **Monitor key usage** for unauthorized access
6. **Revoke compromised keys** immediately

## Next Steps

### Option 1: Fix API Keys (Recommended)
1. Regenerate invalid keys using the solutions above
2. Update environment variables
3. Restart the application
4. Test AI features

### Option 2: Use Fallback Mode
- Continue using the application with fallback responses
- Trading signals still work (rule-based)
- Manual deployment to GitHub/Hugging Face
- All core functionality remains

### Option 3: Disable AI Features
Comment out AI-related code if not needed:
```python
# Set to False to disable AI features
ENABLE_AI = False
```

## Support

If you continue to have issues:
1. Check the respective platform's documentation
2. Verify your account status
3. Contact platform support if keys are valid but still failing
4. Review application logs for specific error messages

---

**Current Application Status**: ✅ Running in fallback mode  
**Affected Features**: AI analysis, auto-deployment  
**Core Functionality**: ✅ Fully operational  
**Recommendation**: Regenerate API keys for full functionality
