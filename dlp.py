import re

class PIIInterceptor:
    """
    A lightweight, regex-based PII masker for gateway demonstration.
    In a true enterprise environment, this would be replaced with Microsoft Presidio.
    """
    def __init__(self):
        self.ssn_regex = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
        self.email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
        self.phone_regex = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')
        self.mappings = {}

    def redact(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
            
        redacted_text = text
        
        # Redact SSNs
        for match in set(self.ssn_regex.findall(redacted_text)):
            token = f"<REDACTED_SSN_{len(self.mappings)}>"
            self.mappings[token] = match
            redacted_text = redacted_text.replace(match, token)
            
        # Redact Emails
        for match in set(self.email_regex.findall(redacted_text)):
            token = f"<REDACTED_EMAIL_{len(self.mappings)}>"
            self.mappings[token] = match
            redacted_text = redacted_text.replace(match, token)
            
        # Redact Phones
        for match in set(self.phone_regex.findall(redacted_text)):
            token = f"<REDACTED_PHONE_{len(self.mappings)}>"
            self.mappings[token] = match
            redacted_text = redacted_text.replace(match, token)
            
        return redacted_text

    def restore(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
            
        restored_text = text
        for token, original_val in self.mappings.items():
            restored_text = restored_text.replace(token, original_val)
            
        return restored_text
