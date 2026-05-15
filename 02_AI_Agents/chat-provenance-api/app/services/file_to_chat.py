from typing import Dict, List
import re

class FileToChatGenerator:
    """Generate ChatGPT conversations from file content"""
    
    def __init__(self, file_content: str, file_name: str, file_type: str):
        self.content = file_content
        self.file_name = file_name
        self.file_type = file_type
    
    def generate_conversation(self) -> Dict:
        """Generate a ChatGPT conversation from file content"""
        
        # Analyze content
        analysis = self._analyze_content()
        
        # Generate conversation
        conversation = self._generate_conversation(analysis)
        
        return {
            "title": f"Analysis: {self.file_name}",
            "model": "gpt-4",
            "messages": conversation,
            "metadata": {
                "source_file": self.file_name,
                "file_type": self.file_type,
                "content_length": len(self.content),
                "analysis": analysis
            }
        }
    
    def _analyze_content(self) -> Dict:
        """Analyze the file content"""
        content = self.content
        
        return {
            "word_count": len(content.split()),
            "line_count": len(content.split('\n')),
            "char_count": len(content),
            "language": self._detect_language(content),
            "key_topics": self._extract_topics(content),
            "structure": self._detect_structure(content),
            "summary": self._generate_summary(content)
        }
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection"""
        # This is a simplified detection
        # In production, use a proper language detection library
        if re.search(r'[\u4e00-\u9fff]', text):
            return "Chinese"
        elif re.search(r'[\u0400-\u04FF]', text):
            return "Russian"
        elif re.search(r'[\u0590-\u05FF]', text):
            return "Hebrew"
        elif re.search(r'[\u0600-\u06FF]', text):
            return "Arabic"
        else:
            return "English"
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract key topics from content"""
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top 5 most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        topics = [word for word, count in sorted_words[:5]]
        
        return topics
    
    def _detect_structure(self, text: str) -> str:
        """Detect document structure"""
        lines = text.split('\n')
        
        # Check for code
        if any(line.strip().startswith(('def ', 'class ', 'function ', 'import ')) for line in lines):
            return "Code"
        
        # Check for markdown
        if any(line.startswith('#') for line in lines):
            return "Markdown"
        
        # Check for JSON
        if text.strip().startswith('{') and text.strip().endswith('}'):
            return "JSON"
        
        # Check for CSV
        if ',' in lines[0] and len(lines) > 1:
            return "CSV/Tabular"
        
        return "Plain Text"
    
    def _generate_summary(self, text: str) -> str:
        """Generate a brief summary of the content"""
        # Take first 200 characters as summary
        summary = text[:200].strip()
        if len(text) > 200:
            summary += "..."
        return summary
    
    def _generate_conversation(self, analysis: Dict) -> List[Dict]:
        """Generate a conversation based on file analysis"""
        
        messages = []
        
        # User uploads file
        messages.append({
            "role": "user",
            "content": f"I've uploaded a file called '{self.file_name}' for analysis. It's a {analysis['structure']} document with {analysis['word_count']} words. Can you help me understand it?"
        })
        
        # Assistant acknowledges
        messages.append({
            "role": "assistant",
            "content": f"I'd be happy to help you analyze '{self.file_name}'. Based on my initial scan, this appears to be a {analysis['structure']} document. Here's what I found:\n\n"
                      f"- **Language**: {analysis['language']}\n"
                      f"- **Word Count**: {analysis['word_count']:,}\n"
                      f"- **Line Count**: {analysis['line_count']:,}\n"
                      f"- **Key Topics**: {', '.join(analysis['key_topics'])}\n\n"
                      f"**Summary**: {analysis['summary']}\n\n"
                      f"Would you like me to dive deeper into any specific aspect of this document?"
        })
        
        # User asks for detailed analysis
        messages.append({
            "role": "user",
            "content": "Yes, please provide a detailed analysis of the content, including the main themes, important points, and any actionable insights."
        })
        
        # Assistant provides detailed analysis
        messages.append({
            "role": "assistant",
            "content": self._generate_detailed_analysis(analysis)
        })
        
        # User asks for recommendations
        messages.append({
            "role": "user",
            "content": "Based on this analysis, what recommendations or next steps would you suggest?"
        })
        
        # Assistant provides recommendations
        messages.append({
            "role": "assistant",
            "content": self._generate_recommendations(analysis)
        })
        
        return messages
    
    def _generate_detailed_analysis(self, analysis: Dict) -> str:
        """Generate detailed analysis response"""
        
        content = self.content[:1000]  # Use first 1000 chars for analysis
        
        response = f"Here's a detailed analysis of '{self.file_name}':\n\n"
        
        response += "## Content Overview\n"
        response += f"The document contains {analysis['word_count']} words and covers several key topics. "
        response += f"The primary themes appear to be: {', '.join(analysis['key_topics'][:3])}.\n\n"
        
        response += "## Key Points\n"
        # Extract some sentences
        sentences = re.split(r'[.!?]+', self.content)
        important_sentences = [s.strip() for s in sentences if len(s.strip()) > 50][:5]
        for i, sentence in enumerate(important_sentences, 1):
            response += f"{i}. {sentence}.\n"
        
        response += "\n## Structure Analysis\n"
        response += f"The document is organized as a {analysis['structure']} file. "
        response += f"It's written in {analysis['language']} and follows a clear structure.\n\n"
        
        response += "## Content Insights\n"
        response += f"Based on the content, this document appears to focus on {analysis['key_topics'][0] if analysis['key_topics'] else 'various topics'}. "
        response += "The content suggests a systematic approach to the subject matter.\n\n"
        
        return response
    
    def _generate_recommendations(self, analysis: Dict) -> str:
        """Generate recommendations based on analysis"""
        
        response = f"Based on my analysis of '{self.file_name}', here are my recommendations:\n\n"
        
        response += "## Immediate Actions\n"
        response += "1. Review the key topics identified and prioritize them based on your goals\n"
        response += "2. Consider creating a summary document highlighting the main points\n"
        response += "3. Extract actionable items from the content\n\n"
        
        response += "## Further Analysis\n"
        response += "1. Perform a deeper dive into the most relevant sections\n"
        response += "2. Cross-reference with related documents or data sources\n"
        response += "3. Consider additional context or background information\n\n"
        
        response += "## Long-term Considerations\n"
        response += "1. Establish a system for tracking updates or changes to this content\n"
        response += "2. Create a knowledge base or repository for similar documents\n"
        response += "3. Set up regular review cycles to ensure the information remains relevant\n\n"
        
        response += "Would you like me to elaborate on any of these recommendations or provide specific guidance for any particular aspect?"
        
        return response
