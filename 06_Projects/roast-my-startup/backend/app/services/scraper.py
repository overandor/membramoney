import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import re

class WebScraper:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    
    async def scrape(self, url: str) -> Dict[str, Any]:
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            evidence = {
                "url": url,
                "title": self._extract_title(soup),
                "meta_description": self._extract_meta_description(soup),
                "h1": self._extract_headings(soup, 'h1'),
                "h2": self._extract_headings(soup, 'h2'),
                "cta_text": self._extract_cta_text(soup),
                "pricing_detected": self._detect_pricing(soup),
                "generic_ai_terms_count": self._count_generic_ai_terms(soup),
                "body_text_excerpt": self._extract_body_text(soup),
            }
            return evidence
        except Exception as e:
            raise Exception(f"Scraping failed: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        title = soup.find('title')
        return title.text.strip() if title else ""
    
    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        meta = soup.find('meta', attrs={'name': 'description'})
        return meta.get('content', '') if meta else ""
    
    def _extract_headings(self, soup: BeautifulSoup, tag: str) -> List[str]:
        return [h.text.strip() for h in soup.find_all(tag)]
    
    def _extract_cta_text(self, soup: BeautifulSoup) -> List[str]:
        buttons = soup.find_all(['button', 'a'], class_=re.compile(r'btn|button|cta', re.I))
        return [b.text.strip() for b in buttons if b.text.strip()]
    
    def _detect_pricing(self, soup: BeautifulSoup) -> bool:
        text = soup.get_text().lower()
        pricing_keywords = ['price', 'pricing', '$', 'cost', 'plan', 'subscription']
        return any(keyword in text for keyword in pricing_keywords)
    
    def _count_generic_ai_terms(self, soup: BeautifulSoup) -> int:
        text = soup.get_text().lower()
        ai_terms = ['ai-powered', 'artificial intelligence', 'machine learning', 'ai platform']
        return sum(text.count(term) for term in ai_terms)
    
    def _extract_body_text(self, soup: BeautifulSoup) -> str:
        paragraphs = soup.find_all('p')
        text = ' '.join([p.text.strip() for p in paragraphs[:5]])
        return text[:500]
