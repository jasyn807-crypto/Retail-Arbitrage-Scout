"""
Utility functions for Retail Arbitrage Scout
"""
import re
import random
import string
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import hashlib


def clean_upc(upc: str) -> Optional[str]:
    """Clean and validate UPC code"""
    if not upc:
        return None
    
    # Remove non-numeric characters
    cleaned = re.sub(r'[^0-9]', '', str(upc))
    
    # Validate length (UPC-A is 12 digits, EAN-13 is 13, GTIN-14 is 14)
    if len(cleaned) in [12, 13, 14]:
        return cleaned
    
    return None


def validate_upc_checksum(upc: str) -> bool:
    """Validate UPC checksum"""
    if not upc or len(upc) != 12:
        return False
    
    try:
        digits = [int(d) for d in upc]
        
        # Calculate checksum
        odd_sum = sum(digits[i] for i in range(0, 11, 2))
        even_sum = sum(digits[i] for i in range(1, 11, 2))
        
        total = (odd_sum * 3) + even_sum
        check_digit = (10 - (total % 10)) % 10
        
        return check_digit == digits[11]
    except (ValueError, IndexError):
        return False


def format_price(price: float) -> str:
    """Format price as currency string"""
    return f"${price:,.2f}"


def format_percent(value: float, decimals: int = 1) -> str:
    """Format value as percentage"""
    return f"{value:.{decimals}f}%"


def calculate_discount_percent(original: float, current: float) -> Optional[float]:
    """Calculate discount percentage"""
    if not original or original <= 0 or current >= original:
        return None
    
    discount = ((original - current) / original) * 100
    return round(discount, 2)


def generate_random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> float:
    """Generate random delay between requests"""
    return random.uniform(min_seconds, max_seconds)


def rotate_user_agent(user_agents: List[str]) -> str:
    """Rotate user agent string"""
    return random.choice(user_agents)


def generate_request_headers() -> Dict[str, str]:
    """Generate random request headers"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]
    
    return {
        'User-Agent': rotate_user_agent(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


def fuzzy_match_products(product_name1: str, product_name2: str) -> float:
    """Calculate fuzzy match score between two product names (0-1)"""
    # Simple word-based matching
    words1 = set(product_name1.lower().split())
    words2 = set(product_name2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text"""
    # Remove special characters and split
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    
    # Filter by length and remove common words
    stop_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'has', 'had'}
    keywords = [w for w in words if len(w) >= min_length and w not in stop_words]
    
    return keywords


def generate_product_hash(product_data: Dict[str, Any]) -> str:
    """Generate unique hash for product data"""
    # Create string from key fields
    hash_input = f"{product_data.get('product_name', '')}_{product_data.get('upc', '')}_{product_data.get('current_price', 0)}"
    
    return hashlib.md5(hash_input.encode()).hexdigest()


def parse_store_hours(hours_string: str) -> Dict[str, str]:
    """Parse store hours string into structured format"""
    hours = {}
    
    # Common patterns
    patterns = [
        r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[-–]?(Mon|Tue|Wed|Thu|Fri|Sat|Sun)?:?\s*(\d{1,2}:\d{2})\s*(AM|PM)?\s*[-–]\s*(\d{1,2}:\d{2})\s*(AM|PM)?'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, hours_string, re.IGNORECASE)
        for match in matches:
            day = match[0]
            open_time = match[2]
            close_time = match[4]
            hours[day] = f"{open_time} - {close_time}"
    
    return hours


def is_business_hours() -> bool:
    """Check if current time is within typical business hours"""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    
    # Business hours: 9 AM - 9 PM, Monday-Saturday
    if weekday < 6 and 9 <= hour < 21:
        return True
    
    return False


def get_best_time_to_scrape() -> datetime:
    """Get recommended time for scraping (low traffic hours)"""
    now = datetime.now()
    
    # Best times: early morning (3-6 AM) or late night (11 PM - 2 AM)
    if now.hour < 3:
        # Late night, good to scrape now
        return now
    elif now.hour < 6:
        # Early morning, good to scrape now
        return now
    else:
        # Schedule for next early morning
        next_morning = now + timedelta(days=1)
        return next_morning.replace(hour=4, minute=0, second=0, microsecond=0)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """Sanitize string for use as filename"""
    # Remove invalid characters
    sanitized = re.sub(r'[^\w\s-]', '', filename)
    # Replace spaces with underscores
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Limit length
    return sanitized[:100]


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size"""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def retry_with_backoff(
    func,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Retry function with exponential backoff"""
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise
            
            import time
            time.sleep(delay)
            delay *= backoff_factor
    
    return None


def calculate_opportunity_tier(score: float) -> str:
    """Determine opportunity tier based on score"""
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Fair"
    elif score >= 20:
        return "Poor"
    else:
        return "Avoid"


def get_tier_color(tier: str) -> str:
    """Get color code for tier"""
    colors = {
        "Excellent": "#28a745",  # Green
        "Good": "#6fbf73",       # Light green
        "Fair": "#ffc107",       # Yellow
        "Poor": "#fd7e14",       # Orange
        "Avoid": "#dc3545"       # Red
    }
    return colors.get(tier, "#6c757d")  # Default gray


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window  # seconds
        self.calls = []
    
    def can_call(self) -> bool:
        """Check if a call can be made"""
        now = datetime.now()
        
        # Remove old calls outside time window
        self.calls = [c for c in self.calls if (now - c).total_seconds() < self.time_window]
        
        return len(self.calls) < self.max_calls
    
    def record_call(self):
        """Record a new call"""
        self.calls.append(datetime.now())
    
    def wait_time(self) -> float:
        """Get seconds to wait before next call"""
        if self.can_call():
            return 0
        
        now = datetime.now()
        oldest_call = min(self.calls)
        wait = self.time_window - (now - oldest_call).total_seconds()
        
        return max(0, wait)


class Cache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, default_ttl: int = 3600):
        self.data = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Any:
        """Get value from cache"""
        if key not in self.data:
            return None
        
        entry = self.data[key]
        if datetime.now() > entry['expires']:
            del self.data[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache"""
        expires = datetime.now() + timedelta(seconds=ttl or self.default_ttl)
        self.data[key] = {'value': value, 'expires': expires}
    
    def delete(self, key: str):
        """Delete key from cache"""
        if key in self.data:
            del self.data[key]
    
    def clear(self):
        """Clear all cache entries"""
        self.data.clear()
    
    def cleanup(self):
        """Remove expired entries"""
        now = datetime.now()
        expired = [k for k, v in self.data.items() if now > v['expires']]
        for k in expired:
            del self.data[k]


# Global cache instance
cache = Cache()
