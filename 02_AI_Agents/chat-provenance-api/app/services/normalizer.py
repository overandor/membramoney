from typing import List, Any, Dict


def normalize_chatgpt_export(chat_data: dict) -> List[Dict[str, Any]]:
    """
    Normalize ChatGPT export format to structured message list.
    
    Expected format:
    {
      "mapping": {
        "node_id": {
          "message": {
            "content": {
              "parts": ["text"]
            }
          }
        }
      }
    }
    
    Returns:
        List of message dicts with role and content
    """
    messages = []
    
    if not isinstance(chat_data, dict):
        return messages
    
    mapping = chat_data.get("mapping", {})
    
    if not isinstance(mapping, dict):
        return messages
    
    # Extract messages from nodes
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
            
        msg = node.get("message")
        if not msg or not isinstance(msg, dict):
            continue
            
        # Try to detect role from message metadata
        role = msg.get("author", {}).get("role", "unknown")
        
        content = msg.get("content")
        if not content or not isinstance(content, dict):
            continue
            
        parts = content.get("parts", [])
        if not parts or not isinstance(parts, list):
            continue
            
        # Extract text from first part
        if parts and isinstance(parts[0], str):
            messages.append({
                "role": role,
                "content": parts[0]
            })
    
    return messages


def normalize_generic_chat(chat_data: Any) -> List[Dict[str, Any]]:
    """
    Normalize generic chat format (array of message objects).
    
    Expected format:
    [
      {"role": "user", "content": "text"},
      {"role": "assistant", "content": "text"}
    ]
    
    Or from GPT Bridge extension:
    {
      "title": "...",
      "model": "...",
      "messages": [
        {"role": "user", "content": "...", "timestamp": "..."}
      ]
    }
    """
    messages = []
    
    # Handle GPT Bridge format
    if isinstance(chat_data, dict) and "messages" in chat_data:
        msg_list = chat_data.get("messages", [])
        if isinstance(msg_list, list):
            for msg in msg_list:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown")
                    content = msg.get("content")
                    if content:
                        messages.append({
                            "role": role,
                            "content": content
                        })
            return messages
    
    # Handle array format
    if not isinstance(chat_data, list):
        return messages
    
    for msg in chat_data:
        if not isinstance(msg, dict):
            continue
            
        role = msg.get("role", "unknown")
        content = msg.get("content")
        
        if content:
            messages.append({
                "role": role,
                "content": str(content)
            })
    
    return messages


def detect_and_normalize(chat_data: Any) -> List[Dict[str, Any]]:
    """
    Auto-detect format and normalize accordingly.
    """
    if isinstance(chat_data, dict):
        if "mapping" in chat_data:
            return normalize_chatgpt_export(chat_data)
        elif "messages" in chat_data:
            return normalize_generic_chat(chat_data)
    elif isinstance(chat_data, list):
        return normalize_generic_chat(chat_data)
    
    # Fallback: try to extract as generic
    return normalize_generic_chat(chat_data)
