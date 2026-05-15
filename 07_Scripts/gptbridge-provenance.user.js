// ==UserScript==
// @name         GPT Bridge - Chat Provenance
// @namespace    gptbridge
// @version      1.0.0
// @description  Export ChatGPT conversations to your Chat Provenance API
// @author       Your Name
// @match        https://chat.openai.com/*
// @match        https://chatgpt.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @connect      localhost
// @connect      your-api-domain.com
// ==/UserScript==

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        API_BASE_URL: GM_getValue('api_base_url', 'http://localhost:8003/api'),
        API_TOKEN: GM_getValue('api_token', null),
    };

    // State
    let currentChatData = null;
    let currentChatId = null;
    let panelVisible = false;

    // Initialize
    function init() {
        console.log('[GPT Bridge] Initializing...');
        
        // Wait for ChatGPT to load
        waitForChatGPT().then(() => {
            checkChatGPTAuth();
            injectUI();
            observeChatChanges();
        });
    }

    // Wait for ChatGPT interface to load
    function waitForChatGPT() {
        return new Promise((resolve) => {
            const check = setInterval(() => {
                if (document.querySelector('[data-testid="conversation-turn"]') ||
                    document.querySelector('main') ||
                    document.querySelector('.text-base')) {
                    clearInterval(check);
                    resolve();
                }
            }, 100);
            
            setTimeout(() => {
                clearInterval(check);
                resolve();
            }, 10000);
        });
    }

    // Check ChatGPT authentication state
    function checkChatGPTAuth() {
        // Try to detect if user is logged into ChatGPT
        const loginButton = document.querySelector('button[aria-label*="Log in"]');
        const sidebar = document.querySelector('[class*="sidebar"]');
        const newChatButton = document.querySelector('[data-testid="new-chat-button"]');
        const userAvatar = document.querySelector('[class*="avatar"]');

        const isLoggedIn = !loginButton && (sidebar || newChatButton || userAvatar);

        if (isLoggedIn) {
            console.log('[GPT Bridge] User is logged into ChatGPT');
            showStatus('Connected to ChatGPT', 'success');
            notifyWebUI('connected');
        } else {
            console.log('[GPT Bridge] User is not logged into ChatGPT');
            showStatus('Please log into ChatGPT first', 'info');
            notifyWebUI('disconnected');
        }

        return isLoggedIn;
    }

    // Notify web UI about ChatGPT connection status
    function notifyWebUI(status) {
        try {
            // Send message to the web UI if it's open
            window.postMessage({
                type: 'GPT_BRIDGE_STATUS',
                status: status,
                timestamp: new Date().toISOString()
            }, '*');

            // Also try to communicate via localStorage for cross-tab communication
            localStorage.setItem('gptbridge_status', JSON.stringify({
                status: status,
                timestamp: new Date().toISOString()
            }));
        } catch (e) {
            console.log('[GPT Bridge] Could not notify web UI:', e);
        }
    }

    // Listen for messages from web UI
    window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'GPT_BRIDGE_PING') {
            // Respond with current status
            const isLoggedIn = checkChatGPTAuth();
            event.source.postMessage({
                type: 'GPT_BRIDGE_PONG',
                status: isLoggedIn ? 'connected' : 'disconnected'
            }, event.origin);
        }
    });

    // Inject UI
    function injectUI() {
        // Create floating action button
        const fab = document.createElement('div');
        fab.id = 'gptbridge-fab';
        fab.innerHTML = `
            <button id="gptbridge-toggle" title="GPT Bridge">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
            </button>
        `;
        fab.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
        `;
        
        const toggleBtn = fab.querySelector('#gptbridge-toggle');
        toggleBtn.style.cssText = `
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
        `;
        toggleBtn.querySelector('svg').style.cssText = 'color: white;';
        
        toggleBtn.addEventListener('click', () => togglePanel());
        toggleBtn.addEventListener('mouseenter', () => toggleBtn.style.transform = 'scale(1.1)');
        toggleBtn.addEventListener('mouseleave', () => toggleBtn.style.transform = 'scale(1)');
        
        document.body.appendChild(fab);
        
        // Create main panel
        const panel = document.createElement('div');
        panel.id = 'gptbridge-panel';
        panel.innerHTML = getPanelHTML();
        panel.style.cssText = `
            position: fixed;
            bottom: 90px;
            right: 20px;
            width: 350px;
            max-height: 500px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            z-index: 10000;
            display: none;
            flex-direction: column;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;
        
        document.body.appendChild(panel);
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = getPanelStyles();
        document.head.appendChild(style);
        
        // Attach event listeners
        attachEventListeners();
    }

    function getPanelHTML() {
        const isLoggedIn = CONFIG.API_TOKEN;
        
        return `
            <div class="gptbridge-header">
                <h3>GPT Bridge</h3>
                <button id="gptbridge-close">×</button>
            </div>
            
            <div class="gptbridge-content">
                <div id="gptbridge-auth-section" style="display: ${isLoggedIn ? 'none' : 'block'};">
                    <p>Login to GPT Bridge API</p>
                    <input type="text" id="gptbridge-api-url" placeholder="API URL" value="${CONFIG.API_BASE_URL}">
                    <input type="email" id="gptbridge-email" placeholder="Email">
                    <input type="password" id="gptbridge-password" placeholder="Password">
                    <button id="gptbridge-login">Login</button>
                    <button id="gptbridge-register">Register</button>
                </div>
                
                <div id="gptbridge-main-section" style="display: ${isLoggedIn ? 'block' : 'none'};">
                    <div class="gptbridge-chat-info">
                        <p id="gptbridge-chat-title">Current Chat: Loading...</p>
                        <p id="gptbridge-chat-count">Messages: 0</p>
                    </div>
                    
                    <div class="gptbridge-actions">
                        <button id="gptbridge-export">Export Current Chat</button>
                        <button id="gptbridge-publish">Publish</button>
                        <button id="gptbridge-my-chats">My Chats</button>
                        <button id="gptbridge-public-chats">Public Chats</button>
                    </div>
                    
                    <div class="gptbridge-publish-settings">
                        <label>
                            <input type="checkbox" id="gptbridge-public-toggle">
                            Make public
                        </label>
                    </div>
                    
                    <div id="gptbridge-status"></div>
                    
                    <button id="gptbridge-logout" style="background: #e53e3e; color: white; margin-top: 10px;">Logout</button>
                </div>
            </div>
        `;
    }

    function getPanelStyles() {
        return `
            #gptbridge-panel .gptbridge-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                color: white;
                margin: 0;
            }
            #gptbridge-panel .gptbridge-header h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 600;
            }
            #gptbridge-panel .gptbridge-header button {
                background: none;
                border: none;
                color: white;
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            #gptbridge-panel .gptbridge-content {
                padding: 16px;
                overflow-y: auto;
            }
            #gptbridge-panel input {
                width: 100%;
                padding: 10px;
                margin: 8px 0;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                box-sizing: border-box;
                font-size: 14px;
            }
            #gptbridge-panel button {
                width: 100%;
                padding: 10px;
                margin: 8px 0;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: background 0.2s;
            }
            #gptbridge-panel #gptbridge-login {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            #gptbridge-panel #gptbridge-register {
                background: #f7fafc;
                color: #4a5568;
                border: 1px solid #e2e8f0;
            }
            #gptbridge-panel #gptbridge-export {
                background: #48bb78;
                color: white;
            }
            #gptbridge-panel #gptbridge-publish {
                background: #4299e1;
                color: white;
            }
            #gptbridge-panel #gptbridge-my-chats {
                background: #ed8936;
                color: white;
            }
            #gptbridge-panel #gptbridge-public-chats {
                background: #9f7aea;
                color: white;
            }
            #gptbridge-panel .gptbridge-chat-info {
                background: #f7fafc;
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 12px;
            }
            #gptbridge-panel .gptbridge-chat-info p {
                margin: 4px 0;
                font-size: 13px;
                color: #4a5568;
            }
            #gptbridge-panel .gptbridge-publish-settings {
                margin: 12px 0;
                padding: 10px;
                background: #f7fafc;
                border-radius: 6px;
            }
            #gptbridge-panel .gptbridge-publish-settings label {
                display: flex;
                align-items: center;
                font-size: 14px;
                color: #4a5568;
                cursor: pointer;
            }
            #gptbridge-panel .gptbridge-publish-settings input[type="checkbox"] {
                width: auto;
                margin-right: 8px;
            }
            #gptbridge-panel #gptbridge-status {
                margin-top: 12px;
                padding: 10px;
                border-radius: 6px;
                font-size: 13px;
                display: none;
            }
            #gptbridge-panel #gptbridge-status.success {
                background: #c6f6d5;
                color: #22543d;
                display: block;
            }
            #gptbridge-panel #gptbridge-status.error {
                background: #fed7d7;
                color: #742a2a;
                display: block;
            }
            #gptbridge-panel #gptbridge-status.info {
                background: #bee3f8;
                color: #2a4365;
                display: block;
            }
        `;
    }

    function attachEventListeners() {
        document.getElementById('gptbridge-close').addEventListener('click', () => togglePanel());
        document.getElementById('gptbridge-login').addEventListener('click', () => handleLogin());
        document.getElementById('gptbridge-register').addEventListener('click', () => handleRegister());
        document.getElementById('gptbridge-logout').addEventListener('click', () => handleLogout());
        document.getElementById('gptbridge-export').addEventListener('click', () => handleExport());
        document.getElementById('gptbridge-publish').addEventListener('click', () => handlePublish());
        document.getElementById('gptbridge-my-chats').addEventListener('click', () => handleMyChats());
        document.getElementById('gptbridge-public-chats').addEventListener('click', () => handlePublicChats());
    }

    function togglePanel() {
        panelVisible = !panelVisible;
        document.getElementById('gptbridge-panel').style.display = panelVisible ? 'flex' : 'none';
    }

    // API calls
    function apiCall(endpoint, method = 'GET', data = null) {
        return new Promise((resolve, reject) => {
            const headers = {
                'Content-Type': 'application/json',
            };
            
            if (CONFIG.API_TOKEN) {
                headers['Authorization'] = `Bearer ${CONFIG.API_TOKEN}`;
            }
            
            GM_xmlhttpRequest({
                method: method,
                url: `${CONFIG.API_BASE_URL}${endpoint}`,
                headers: headers,
                data: data ? JSON.stringify(data) : null,
                onload: (response) => {
                    try {
                        const result = JSON.parse(response.responseText);
                        if (response.status >= 200 && response.status < 300) {
                            resolve(result);
                        } else {
                            reject(result);
                        }
                    } catch (e) {
                        reject({ error: 'Invalid response' });
                    }
                },
                onerror: (error) => reject({ error: 'Network error' })
            });
        });
    }

    async function handleLogin() {
        const email = document.getElementById('gptbridge-email').value;
        const password = document.getElementById('gptbridge-password').value;
        const apiUrl = document.getElementById('gptbridge-api-url').value;
        
        if (!email || !password) {
            showStatus('Please fill in all fields', 'error');
            return;
        }
        
        // Save API URL
        GM_setValue('api_base_url', apiUrl);
        CONFIG.API_BASE_URL = apiUrl;
        
        showStatus('Logging in...', 'info');
        
        try {
            const result = await apiCall('/auth/login', 'POST', { email, password });
            
            if (result.access_token) {
                GM_setValue('api_token', result.access_token);
                CONFIG.API_TOKEN = result.access_token;
                showStatus('Login successful!', 'success');
                refreshPanel();
            } else {
                showStatus('Login failed', 'error');
            }
        } catch (error) {
            showStatus(error.error || 'Login failed', 'error');
        }
    }

    async function handleRegister() {
        const email = document.getElementById('gptbridge-email').value;
        const password = document.getElementById('gptbridge-password').value;
        const apiUrl = document.getElementById('gptbridge-api-url').value;
        
        if (!email || !password) {
            showStatus('Please fill in all fields', 'error');
            return;
        }
        
        GM_setValue('api_base_url', apiUrl);
        CONFIG.API_BASE_URL = apiUrl;
        
        showStatus('Registering...', 'info');
        
        try {
            await apiCall('/auth/register', 'POST', { email, password });
            showStatus('Registration successful! Please login.', 'success');
        } catch (error) {
            showStatus(error.error || 'Registration failed', 'error');
        }
    }

    function handleLogout() {
        GM_deleteValue('api_token');
        CONFIG.API_TOKEN = null;
        showStatus('Logged out', 'info');
        refreshPanel();
    }

    async function handleExport() {
        const chatData = await extractCurrentChat();
        
        if (!chatData || chatData.messages.length === 0) {
            showStatus('No chat data found', 'error');
            return;
        }
        
        showStatus('Exporting chat...', 'info');
        
        try {
            const result = await apiCall('/chats/upload', 'POST', {
                title: chatData.title,
                file: chatData
            });
            
            if (result.id) {
                currentChatId = result.id;
                showStatus('Chat exported successfully!', 'success');
                document.getElementById('gptbridge-publish').disabled = false;
            }
        } catch (error) {
            showStatus(error.error || 'Export failed', 'error');
        }
    }

    async function handlePublish() {
        if (!currentChatId) {
            showStatus('Please export the chat first', 'error');
            return;
        }
        
        const isPublic = document.getElementById('gptbridge-public-toggle').checked;
        
        showStatus('Publishing chat...', 'info');
        
        try {
            await apiCall(`/chats/${currentChatId}/publish`, 'POST', { is_public: isPublic });
            showStatus(isPublic ? 'Chat published publicly!' : 'Chat unpublished', 'success');
        } catch (error) {
            showStatus(error.error || 'Publish failed', 'error');
        }
    }

    async function handleMyChats() {
        showStatus('Loading your chats...', 'info');
        
        try {
            const chats = await apiCall('/chats');
            console.log('[GPT Bridge] Your chats:', chats);
            showStatus(`Found ${chats.length} chats (check console)`, 'success');
        } catch (error) {
            showStatus(error.error || 'Failed to load chats', 'error');
        }
    }

    async function handlePublicChats() {
        showStatus('Loading public chats...', 'info');
        
        try {
            const chats = await apiCall('/chats/public');
            console.log('[GPT Bridge] Public chats:', chats);
            showStatus(`Found ${chats.length} public chats (check console)`, 'success');
        } catch (error) {
            showStatus(error.error || 'Failed to load public chats', 'error');
        }
    }

    // Extract current chat from ChatGPT
    async function extractCurrentChat() {
        const messages = [];
        
        // Method 1: Try ChatGPT's internal data structure (most reliable)
        try {
            const conversationData = extractFromReactFiber();
            if (conversationData && conversationData.length > 0) {
                console.log('[GPT Bridge] Extracted from React Fiber');
                return formatChatData(conversationData);
            }
        } catch (e) {
            console.log('[GPT Bridge] React Fiber extraction failed:', e);
        }
        
        // Method 2: Parse DOM with role detection
        const turns = document.querySelectorAll('[data-testid="conversation-turn"]');
        
        if (turns.length > 0) {
            turns.forEach(turn => {
                const role = detectRole(turn);
                const content = extractContent(turn);
                
                if (content) {
                    messages.push({
                        role: role,
                        content: content,
                        timestamp: extractTimestamp(turn)
                    });
                }
            });
        }
        
        // Method 3: Alternative selectors for different UI versions
        if (messages.length === 0) {
            const mainContent = document.querySelector('main');
            if (mainContent) {
                const messageGroups = mainContent.querySelectorAll('[class*="group"]');
                messageGroups.forEach(group => {
                    const role = detectRole(group);
                    const content = extractContent(group);
                    
                    if (content) {
                        messages.push({
                            role: role,
                            content: content,
                            timestamp: new Date().toISOString()
                        });
                    }
                });
            }
        }
        
        // Method 4: Fallback - grab all text blocks
        if (messages.length === 0) {
            const textBlocks = document.querySelectorAll('.text-base, .markdown, [class*="prose"]');
            textBlocks.forEach(block => {
                const content = block.innerText?.trim();
                if (content && content.length > 10) {
                    messages.push({
                        role: 'unknown',
                        content: content,
                        timestamp: new Date().toISOString()
                    });
                }
            });
        }
        
        // Get chat title with multiple methods
        const title = extractChatTitle();
        
        // Get model info if available
        const model = extractModelInfo();
        
        return {
            title: title,
            model: model,
            messages: messages,
            message_count: messages.length,
            timestamp: new Date().toISOString(),
            source: 'gptbridge-extension'
        };
    }
    
    // Extract from React Fiber (ChatGPT's internal state)
    function extractFromReactFiber() {
        const messages = [];
        
        // Try to access React's internal state
        const root = document.querySelector('#__next');
        if (!root) return null;
        
        // Walk the React fiber tree to find conversation data
        const fiberKey = Object.keys(root).find(key => key.startsWith('__reactFiber'));
        if (!fiberKey) return null;
        
        let fiber = root[fiberKey];
        let depth = 0;
        const maxDepth = 50;
        
        while (fiber && depth < maxDepth) {
            // Look for conversation data in state or props
            if (fiber.memoizedState && fiber.memoizedState.conversation) {
                const conversation = fiber.memoizedState.conversation;
                if (conversation.messages) {
                    return conversation.messages;
                }
            }
            
            if (fiber.pendingProps && fiber.pendingProps.conversation) {
                const conversation = fiber.pendingProps.conversation;
                if (conversation.messages) {
                    return conversation.messages;
                }
            }
            
            fiber = fiber.return || fiber.child;
            depth++;
        }
        
        return null;
    }
    
    // Detect if a message is from user or assistant
    function detectRole(element) {
        // Check for user indicators
        const userIndicators = [
            '[data-testid="user"]',
            '[data-message-author-role="user"]',
            '[class*="user"]',
            '[class*="User"]'
        ];
        
        for (const selector of userIndicators) {
            if (element.querySelector(selector) || element.matches(selector)) {
                return 'user';
            }
        }
        
        // Check for assistant indicators
        const assistantIndicators = [
            '[data-testid="assistant"]',
            '[data-message-author-role="assistant"]',
            '[class*="assistant"]',
            '[class*="Assistant"]',
            '[class*="gpt"]',
            '[class*="GPT"]'
        ];
        
        for (const selector of assistantIndicators) {
            if (element.querySelector(selector) || element.matches(selector)) {
                return 'assistant';
            }
        }
        
        // Try to infer from position/structure
        const parent = element.parentElement;
        if (parent) {
            const siblings = Array.from(parent.children);
            const index = siblings.indexOf(element);
            // Even/odd pattern often indicates role alternation
            if (index % 2 === 0) return 'user';
            return 'assistant';
        }
        
        return 'unknown';
    }
    
    // Extract content from a message element
    function extractContent(element) {
        // Try multiple content selectors
        const contentSelectors = [
            '.markdown',
            '.prose',
            '[class*="messageContent"]',
            '[class*="text-message"]',
            '[data-message-author-role]'
        ];
        
        for (const selector of contentSelectors) {
            const contentEl = element.querySelector(selector);
            if (contentEl) {
                return cleanContent(contentEl);
            }
        }
        
        // Fallback to innerText
        const text = element.innerText?.trim();
        return text ? cleanContent(element) : null;
    }
    
    // Clean and format content
    function cleanContent(element) {
        // Clone to avoid modifying original
        const clone = element.cloneNode(true);
        
        // Remove unwanted elements
        const unwanted = clone.querySelectorAll('button, .hidden, [style*="display: none"]');
        unwanted.forEach(el => el.remove());
        
        // Handle code blocks
        const codeBlocks = clone.querySelectorAll('pre, code');
        codeBlocks.forEach(block => {
            block.setAttribute('data-code', 'true');
        });
        
        // Get text content
        let content = clone.innerText || clone.textContent;
        
        // Clean up whitespace
        content = content.replace(/\s+/g, ' ').trim();
        
        return content;
    }
    
    // Extract timestamp if available
    function extractTimestamp(element) {
        const timeElement = element.querySelector('time, [datetime], [class*="time"]');
        if (timeElement) {
            const datetime = timeElement.getAttribute('datetime');
            if (datetime) return datetime;
        }
        return new Date().toISOString();
    }
    
    // Extract chat title with multiple methods
    function extractChatTitle() {
        // Method 1: Page title
        const pageTitle = document.title;
        if (pageTitle && pageTitle !== 'ChatGPT') {
            return pageTitle.replace('ChatGPT', '').replace(' - ', '').trim();
        }
        
        // Method 2: Conversation title element
        const titleSelectors = [
            '[data-testid="conversation-title"]',
            '[class*="conversation-title"]',
            '[class*="chat-title"]',
            'h1',
            '.text-xl'
        ];
        
        for (const selector of titleSelectors) {
            const titleEl = document.querySelector(selector);
            if (titleEl) {
                const text = titleEl.innerText?.trim();
                if (text && text.length > 0 && text.length < 100) {
                    return text;
                }
            }
        }
        
        // Method 3: First user message as title
        const firstUserMessage = document.querySelector('[data-testid="conversation-turn"]:first-child');
        if (firstUserMessage) {
            const text = firstUserMessage.innerText?.trim();
            if (text) {
                return text.substring(0, 50) + (text.length > 50 ? '...' : '');
            }
        }
        
        return 'Untitled Chat';
    }
    
    // Extract model information
    function extractModelInfo() {
        const modelSelectors = [
            '[class*="model"]',
            '[data-testid="model-selector"]',
            '[class*="gpt-"]'
        ];
        
        for (const selector of modelSelectors) {
            const modelEl = document.querySelector(selector);
            if (modelEl) {
                const text = modelEl.innerText?.trim();
                if (text && text.includes('GPT')) {
                    return text;
                }
            }
        }
        
        return 'unknown';
    }
    
    // Format extracted data to match ChatGPT export structure
    function formatChatData(rawMessages) {
        const formatted = [];
        
        rawMessages.forEach(msg => {
            if (msg.content) {
                formatted.push({
                    role: msg.role || 'unknown',
                    content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content),
                    timestamp: msg.timestamp || new Date().toISOString()
                });
            }
        });
        
        return formatted;
    }

    // Observe chat changes
    function observeChatChanges() {
        const observer = new MutationObserver(() => {
            updateChatInfo();
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        updateChatInfo();
    }

    async function updateChatInfo() {
        const chatData = await extractCurrentChat();
        currentChatData = chatData;
        
        const titleEl = document.getElementById('gptbridge-chat-title');
        const countEl = document.getElementById('gptbridge-chat-count');
        const modelEl = document.getElementById('gptbridge-model');
        
        if (titleEl) titleEl.textContent = `Current Chat: ${chatData.title}`;
        if (countEl) countEl.textContent = `Messages: ${chatData.message_count || chatData.messages?.length || 0}`;
        
        // Update model info if element exists
        if (chatData.model) {
            if (!modelEl) {
                const chatInfo = document.querySelector('.gptbridge-chat-info');
                if (chatInfo) {
                    const modelP = document.createElement('p');
                    modelP.id = 'gptbridge-model';
                    chatInfo.appendChild(modelP);
                }
            }
            const newModelEl = document.getElementById('gptbridge-model');
            if (newModelEl) newModelEl.textContent = `Model: ${chatData.model}`;
        }
    }

    function refreshPanel() {
        document.getElementById('gptbridge-panel').innerHTML = getPanelHTML();
        attachEventListeners();
    }

    function showStatus(message, type) {
        const statusEl = document.getElementById('gptbridge-status');
        if (statusEl) {
            statusEl.textContent = message;
            statusEl.className = type;
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 5000);
        }
    }

    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${type === 'success' ? '#48bb78' : type === 'error' ? '#e53e3e' : '#4299e1'};
            color: white;
            border-radius: 8px;
            z-index: 10001;
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    // Start
    init();
})();
