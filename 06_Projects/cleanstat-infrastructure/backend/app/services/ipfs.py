"""
CleanStat Infrastructure - IPFS Service
IPFS integration using Pinata
"""
import requests
from app.config import settings

def fetch_from_ipfs(cid: str) -> bytes:
    """
    Fetch data from IPFS using Pinata gateway
    
    Args:
        cid: IPFS content identifier
    
    Returns:
        Raw bytes data
    """
    url = f"{settings.PINATA_GATEWAY}/ipfs/{cid}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content

def upload_to_ipfs(data: bytes, filename: str = None) -> str:
    """
    Upload data to IPFS using Pinata
    
    Args:
        data: Raw bytes data
        filename: Optional filename
    
    Returns:
        IPFS content identifier (CID)
    """
    # TODO: Implement Pinata JWT upload
    # This requires Pinata JWT authentication
    raise NotImplementedError("IPFS upload not yet implemented")
