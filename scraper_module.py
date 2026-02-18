"""
Web scraper module for Walmart and Home Depot
Uses Playwright with stealth plugins to avoid bot detection
"""
import asyncio
import random
import re
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import time

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
import fake_useragent

from config import SCRAPER_CONFIG, STORE_CONFIG, UPC_PATTERNS


@dataclass
class ScrapedItem:
    """Data class for scraped items"""
    product_id: str
    product_name: str
    current_price: float
    original_price: Optional[float] = None
    discount_percent: Optional[float] = None
    upc: Optional[str] = None
    stock_status: str = "Unknown"
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    deal_type: str = "Unknown"
    raw_data: Optional[Dict] = None


class StealthScraper:
    """Base scraper with stealth capabilities"""
    
    def __init__(self):
        self.config = SCRAPER_CONFIG
        self.user_agent = fake_useragent.UserAgent()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.config.HEADLESS,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
            ]
        )
        
        # Create context with random user agent
        self.context = await self.browser.new_context(
            user_agent=random.choice(self.config.USER_AGENTS),
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
        )
        
        # Add init script to mask webdriver
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
        
        self.page = await self.context.new_page()
        await stealth_async(self.page)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def random_delay(self, min_seconds: float = None, max_seconds: float = None):
        """Add random delay between requests"""
        min_sec = min_seconds or self.config.MIN_DELAY
        max_sec = max_seconds or self.config.MAX_DELAY
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def human_like_scroll(self, scroll_amount: int = None):
        """Simulate human-like scrolling"""
        if not scroll_amount:
            scroll_amount = random.randint(300, 800)
        
        await self.page.mouse.wheel(0, scroll_amount)
        await self.random_delay(0.5, 1.5)
    
    async def extract_upc_from_page(self) -> Optional[str]:
        """Extract UPC/GTIN from page content using regex patterns"""
        try:
            # Get page source
            content = await self.page.content()
            
            # Try each regex pattern
            for pattern in UPC_PATTERNS:
                matches = re.findall(pattern, content)
                if matches:
                    # Return first valid match
                    for match in matches:
                        if len(match) >= 12:
                            return match
            
            # Try to find in JSON-LD structured data
            soup = BeautifulSoup(content, 'html.parser')
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Check for GTIN/UPC in product data
                        gtin = data.get('gtin') or data.get('gtin14') or data.get('gtin13') or data.get('gtin12')
                        if gtin:
                            return str(gtin)
                        
                        # Check nested offers
                        offers = data.get('offers', {})
                        if isinstance(offers, dict):
                            gtin = offers.get('gtin') or offers.get('gtin14')
                            if gtin:
                                return str(gtin)
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error extracting UPC: {e}")
            return None
    
    async def handle_captcha(self) -> bool:
        """Handle captcha detection - returns True if captcha found"""
        captcha_indicators = [
            'captcha',
            'recaptcha',
            'robot',
            'verify you are human',
            'security check',
            'access denied'
        ]
        
        page_content = await self.page.content()
        page_content_lower = page_content.lower()
        
        for indicator in captcha_indicators:
            if indicator in page_content_lower:
                print(f"CAPTCHA detected: '{indicator}' found on page")
                return True
        
        return False


class WalmartScraper(StealthScraper):
    """Walmart-specific scraper"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.walmart.com"
        
    async def search_clearance_by_store(self, store_id: str, zip_code: str) -> List[ScrapedItem]:
        """Search clearance items for a specific store"""
        items = []
        
        try:
            # Build URL with store filter
            url = f"{self.base_url}/search?q=clearance&affinityOverride=store_led&store={store_id}"
            
            print(f"Scraping Walmart clearance for store {store_id}...")
            
            await self.page.goto(url, wait_until='networkidle', timeout=self.config.BROWSER_TIMEOUT)
            await self.random_delay(3, 5)
            
            # Check for captcha
            if await self.handle_captcha():
                print("CAPTCHA detected, skipping...")
                return items
            
            # Scroll to load more items
            for _ in range(3):
                await self.human_like_scroll()
            
            # Extract items from page
            page_items = await self._extract_walmart_items('Clearance', store_id)
            items.extend(page_items)
            
            print(f"Found {len(page_items)} clearance items for store {store_id}")
            
        except Exception as e:
            print(f"Error scraping Walmart clearance: {e}")
        
        return items
    
    async def search_rollback_by_store(self, store_id: str, zip_code: str) -> List[ScrapedItem]:
        """Search rollback items for a specific store"""
        items = []
        
        try:
            url = f"{self.base_url}/search?q=rollback&affinityOverride=store_led&store={store_id}"
            
            print(f"Scraping Walmart rollback for store {store_id}...")
            
            await self.page.goto(url, wait_until='networkidle', timeout=self.config.BROWSER_TIMEOUT)
            await self.random_delay(3, 5)
            
            if await self.handle_captcha():
                print("CAPTCHA detected, skipping...")
                return items
            
            for _ in range(3):
                await self.human_like_scroll()
            
            page_items = await self._extract_walmart_items('Rollback', store_id)
            items.extend(page_items)
            
            print(f"Found {len(page_items)} rollback items for store {store_id}")
            
        except Exception as e:
            print(f"Error scraping Walmart rollback: {e}")
        
        return items
    
    async def _extract_walmart_items(self, deal_type: str, store_id: str) -> List[ScrapedItem]:
        """Extract item data from Walmart page"""
        items = []
        
        try:
            # Get all product elements
            product_selectors = [
                '[data-automation-id="product-title"]',
                '[data-testid="product-title"]',
                '.search-result-gridview-item',
                '[data-item-id]',
            ]
            
            for selector in product_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        break
                except:
                    continue
            
            # Extract page data from JSON if available
            content = await self.page.content()
            
            # Try to find Next.js data
            next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
            if next_data_match:
                try:
                    next_data = json.loads(next_data_match.group(1))
                    # Extract products from Next.js data
                    items_data = self._parse_nextjs_data(next_data, deal_type)
                    items.extend(items_data)
                except json.JSONDecodeError:
                    pass
            
            # Fallback to HTML parsing
            if not items:
                soup = BeautifulSoup(content, 'html.parser')
                product_elements = soup.find_all(attrs={'data-item-id': True})
                
                for elem in product_elements[:20]:  # Limit to 20 items
                    try:
                        item = self._parse_walmart_html_element(elem, deal_type)
                        if item:
                            items.append(item)
                    except Exception as e:
                        print(f"Error parsing element: {e}")
                        continue
            
        except Exception as e:
            print(f"Error extracting Walmart items: {e}")
        
        return items
    
    def _parse_nextjs_data(self, data: Dict, deal_type: str) -> List[ScrapedItem]:
        """Parse Next.js data structure"""
        items = []
        
        try:
            # Navigate through Next.js data structure
            props = data.get('props', {})
            page_props = props.get('pageProps', {})
            initial_data = page_props.get('initialData', {})
            search_result = initial_data.get('searchResult', {})
            item_stacks = search_result.get('itemStacks', [])
            
            for stack in item_stacks:
                items_data = stack.get('items', [])
                
                for product in items_data:
                    try:
                        item = self._parse_walmart_product(product, deal_type)
                        if item:
                            items.append(item)
                    except Exception as e:
                        print(f"Error parsing product: {e}")
                        continue
                        
        except Exception as e:
            print(f"Error parsing Next.js data: {e}")
        
        return items
    
    def _parse_walmart_product(self, product: Dict, deal_type: str) -> Optional[ScrapedItem]:
        """Parse individual Walmart product data"""
        try:
            product_id = product.get('id') or product.get('usItemId')
            if not product_id:
                return None
            
            # Get pricing
            price_info = product.get('price', {})
            current_price = price_info.get('currentPrice', {}).get('price', 0)
            original_price = price_info.get('wasPrice', {}).get('price', 0)
            
            if not current_price:
                return None
            
            # Calculate discount
            discount_percent = None
            if original_price and original_price > current_price:
                discount_percent = round(((original_price - current_price) / original_price) * 100, 2)
            
            # Get UPC
            upc = product.get('upc') or product.get('gtin')
            
            # Get other details
            name = product.get('name', 'Unknown Product')
            brand = product.get('brand', '')
            category = product.get('category', '')
            image_url = product.get('imageUrl', '')
            
            # Build product URL
            product_url = f"{self.base_url}/ip/{product_id}"
            
            # Get stock status
            inventory = product.get('inventory', {})
            stock_status = "In Stock" if inventory.get('availableOnline') else "Unknown"
            
            return ScrapedItem(
                product_id=str(product_id),
                product_name=name,
                current_price=float(current_price),
                original_price=float(original_price) if original_price else None,
                discount_percent=discount_percent,
                upc=upc,
                stock_status=stock_status,
                product_url=product_url,
                image_url=image_url,
                brand=brand,
                category=category,
                deal_type=deal_type,
                raw_data=product
            )
            
        except Exception as e:
            print(f"Error parsing Walmart product: {e}")
            return None
    
    def _parse_walmart_html_element(self, elem, deal_type: str) -> Optional[ScrapedItem]:
        """Parse Walmart product from HTML element"""
        try:
            product_id = elem.get('data-item-id')
            if not product_id:
                return None
            
            # Try to find name
            name_elem = elem.find(attrs={'data-automation-id': 'product-title'})
            name = name_elem.text.strip() if name_elem else 'Unknown'
            
            # Try to find price
            price_elem = elem.find(attrs={'data-automation-id': 'product-price'})
            if price_elem:
                price_text = price_elem.text.strip()
                price_match = re.search(r'\$([\d,]+\.?\d*)', price_text)
                current_price = float(price_match.group(1).replace(',', '')) if price_match else 0
            else:
                current_price = 0
            
            # Try to find image
            img_elem = elem.find('img')
            image_url = img_elem.get('src', '') if img_elem else ''
            
            return ScrapedItem(
                product_id=product_id,
                product_name=name,
                current_price=current_price,
                deal_type=deal_type,
                product_url=f"{self.base_url}/ip/{product_id}",
                image_url=image_url
            )
            
        except Exception as e:
            print(f"Error parsing HTML element: {e}")
            return None


class HomeDepotScraper(StealthScraper):
    """Home Depot-specific scraper"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.homedepot.com"
    
    async def search_clearance_by_store(self, store_id: str, zip_code: str) -> List[ScrapedItem]:
        """Search clearance items for a specific Home Depot store"""
        items = []
        
        try:
            # Set store location first
            await self._set_store_location(store_id, zip_code)
            
            # Navigate to clearance section
            url = f"{self.base_url}/b/Clearance/N-5yc1vZ1z0z7d"
            
            print(f"Scraping Home Depot clearance for store {store_id}...")
            
            await self.page.goto(url, wait_until='networkidle', timeout=self.config.BROWSER_TIMEOUT)
            await self.random_delay(3, 5)
            
            if await self.handle_captcha():
                print("CAPTCHA detected, skipping...")
                return items
            
            # Scroll to load items
            for _ in range(3):
                await self.human_like_scroll()
            
            page_items = await self._extract_homedepot_items('Clearance')
            items.extend(page_items)
            
            print(f"Found {len(page_items)} clearance items for store {store_id}")
            
        except Exception as e:
            print(f"Error scraping Home Depot clearance: {e}")
        
        return items
    
    async def search_special_buy_by_store(self, store_id: str, zip_code: str) -> List[ScrapedItem]:
        """Search special buy items for a specific store"""
        items = []
        
        try:
            await self._set_store_location(store_id, zip_code)
            
            url = f"{self.base_url}/c/Special_Buy"
            
            print(f"Scraping Home Depot special buys for store {store_id}...")
            
            await self.page.goto(url, wait_until='networkidle', timeout=self.config.BROWSER_TIMEOUT)
            await self.random_delay(3, 5)
            
            if await self.handle_captcha():
                print("CAPTCHA detected, skipping...")
                return items
            
            for _ in range(3):
                await self.human_like_scroll()
            
            page_items = await self._extract_homedepot_items('Special Buy')
            items.extend(page_items)
            
            print(f"Found {len(page_items)} special buy items for store {store_id}")
            
        except Exception as e:
            print(f"Error scraping Home Depot special buys: {e}")
        
        return items
    
    async def _set_store_location(self, store_id: str, zip_code: str):
        """Set store location for accurate inventory"""
        try:
            # Navigate to store finder
            url = f"{self.base_url}/l/store/{zip_code}"
            await self.page.goto(url, wait_until='networkidle', timeout=10000)
            await self.random_delay(2, 3)
            
            # Look for store selection button
            store_buttons = await self.page.query_selector_all(f'[data-storeid="{store_id}"]')
            if store_buttons:
                await store_buttons[0].click()
                await self.random_delay(2, 3)
                
        except Exception as e:
            print(f"Error setting store location: {e}")
    
    async def _extract_homedepot_items(self, deal_type: str) -> List[ScrapedItem]:
        """Extract item data from Home Depot page"""
        items = []
        
        try:
            content = await self.page.content()
            
            # Try to extract from JSON data
            json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    items_data = self._parse_homedepot_json(data, deal_type)
                    items.extend(items_data)
                except json.JSONDecodeError:
                    pass
            
            # Fallback to HTML parsing
            if not items:
                soup = BeautifulSoup(content, 'html.parser')
                product_elements = soup.find_all(class_=re.compile(r'product\b', re.I))
                
                for elem in product_elements[:20]:
                    try:
                        item = self._parse_homedepot_html_element(elem, deal_type)
                        if item:
                            items.append(item)
                    except Exception as e:
                        print(f"Error parsing element: {e}")
                        continue
            
        except Exception as e:
            print(f"Error extracting Home Depot items: {e}")
        
        return items
    
    def _parse_homedepot_json(self, data: Dict, deal_type: str) -> List[ScrapedItem]:
        """Parse Home Depot JSON data"""
        items = []
        
        try:
            # Navigate through data structure
            search_data = data.get('search', {})
            results = search_data.get('results', [])
            
            for product in results:
                try:
                    item = self._parse_homedepot_product(product, deal_type)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"Error parsing Home Depot product: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error parsing Home Depot JSON: {e}")
        
        return items
    
    def _parse_homedepot_product(self, product: Dict, deal_type: str) -> Optional[ScrapedItem]:
        """Parse individual Home Depot product"""
        try:
            product_id = product.get('productId') or product.get('itemId')
            if not product_id:
                return None
            
            # Get pricing
            pricing = product.get('pricing', {})
            current_price = pricing.get('specialBuy', {}).get('price') or pricing.get('clearance', {}).get('price')
            original_price = pricing.get('originalPrice', {}).get('price')
            
            if not current_price:
                current_price = product.get('price', {}).get('value', 0)
            
            if not current_price:
                return None
            
            # Calculate discount
            discount_percent = None
            if original_price and float(original_price) > float(current_price):
                discount_percent = round(
                    ((float(original_price) - float(current_price)) / float(original_price)) * 100, 2
                )
            
            # Get UPC
            upc = product.get('upc') or product.get('gtin')
            
            # Get other details
            name = product.get('name', 'Unknown Product')
            brand = product.get('brand', {}).get('name', '')
            category = product.get('category', '')
            
            # Get image
            images = product.get('images', [])
            image_url = images[0].get('url') if images else ''
            
            # Build URL
            product_url = f"{self.base_url}/p/{product_id}"
            
            # Get inventory
            inventory = product.get('inventory', {})
            stock_status = "In Stock" if inventory.get('onlineStock', False) else "Unknown"
            
            return ScrapedItem(
                product_id=str(product_id),
                product_name=name,
                current_price=float(current_price),
                original_price=float(original_price) if original_price else None,
                discount_percent=discount_percent,
                upc=upc,
                stock_status=stock_status,
                product_url=product_url,
                image_url=image_url,
                brand=brand,
                category=category,
                deal_type=deal_type,
                raw_data=product
            )
            
        except Exception as e:
            print(f"Error parsing Home Depot product: {e}")
            return None
    
    def _parse_homedepot_html_element(self, elem, deal_type: str) -> Optional[ScrapedItem]:
        """Parse Home Depot product from HTML element"""
        try:
            # Try to find product ID
            product_id = elem.get('data-productid') or elem.get('data-itemid')
            if not product_id:
                return None
            
            # Try to find name
            name_elem = elem.find(class_=re.compile(r'product-title|product-name', re.I))
            name = name_elem.text.strip() if name_elem else 'Unknown'
            
            # Try to find price
            price_elem = elem.find(class_=re.compile(r'price', re.I))
            if price_elem:
                price_text = price_elem.text.strip()
                price_match = re.search(r'\$([\d,]+\.?\d*)', price_text)
                current_price = float(price_match.group(1).replace(',', '')) if price_match else 0
            else:
                current_price = 0
            
            # Try to find image
            img_elem = elem.find('img')
            image_url = img_elem.get('src', '') if img_elem else ''
            
            return ScrapedItem(
                product_id=product_id,
                product_name=name,
                current_price=current_price,
                deal_type=deal_type,
                product_url=f"{self.base_url}/p/{product_id}",
                image_url=image_url
            )
            
        except Exception as e:
            print(f"Error parsing HTML element: {e}")
            return None


class StoreLocator:
    """Find stores by ZIP code"""
    
    @staticmethod
    async def find_walmart_stores(zip_code: str, radius: int = 20) -> List[Dict[str, Any]]:
        """Find Walmart stores near ZIP code"""
        stores = []
        
        try:
            # Use Walmart store finder API
            url = f"https://www.walmart.com/store/finder?location={zip_code}&distance={radius}"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                await page.goto(url, wait_until='networkidle')
                await asyncio.sleep(3)
                
                content = await page.content()
                
                # Try to extract store data from JSON
                json_match = re.search(r'window\.__WML_REDUX_INITIAL_STATE__\s*=\s*({.*?});', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                    stores_data = data.get('storeFinder', {}).get('stores', [])
                    
                    for store in stores_data:
                        stores.append({
                            'store_id': str(store.get('id')),
                            'retailer': 'walmart',
                            'name': store.get('name', ''),
                            'address': store.get('address', {}).get('address1', ''),
                            'city': store.get('address', {}).get('city', ''),
                            'state': store.get('address', {}).get('state', ''),
                            'zip_code': store.get('address', {}).get('zip', ''),
                            'phone': store.get('phone', ''),
                            'latitude': store.get('geoPoint', {}).get('latitude'),
                            'longitude': store.get('geoPoint', {}).get('longitude'),
                            'distance_miles': store.get('distance'),
                        })
                
                await browser.close()
                
        except Exception as e:
            print(f"Error finding Walmart stores: {e}")
        
        return stores
    
    @staticmethod
    async def find_homedepot_stores(zip_code: str, radius: int = 20) -> List[Dict[str, Any]]:
        """Find Home Depot stores near ZIP code"""
        stores = []
        
        try:
            url = f"https://www.homedepot.com/l/store/{zip_code}"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                await page.goto(url, wait_until='networkidle')
                await asyncio.sleep(3)
                
                content = await page.content()
                
                # Try to extract store data
                json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                    stores_data = data.get('storeFinder', {}).get('stores', [])
                    
                    for store in stores_data:
                        stores.append({
                            'store_id': str(store.get('storeId')),
                            'retailer': 'homedepot',
                            'name': f"Home Depot #{store.get('storeId')}",
                            'address': store.get('address', {}).get('street', ''),
                            'city': store.get('address', {}).get('city', ''),
                            'state': store.get('address', {}).get('state', ''),
                            'zip_code': store.get('address', {}).get('zip', ''),
                            'phone': store.get('phone', ''),
                            'latitude': store.get('coordinates', {}).get('lat'),
                            'longitude': store.get('coordinates', {}).get('lng'),
                            'distance_miles': store.get('distance'),
                        })
                
                await browser.close()
                
        except Exception as e:
            print(f"Error finding Home Depot stores: {e}")
        
        return stores


# Convenience functions for direct use
async def scrape_walmart_store(store_id: str, zip_code: str) -> List[ScrapedItem]:
    """Scrape Walmart store for deals"""
    async with WalmartScraper() as scraper:
        clearance_items = await scraper.search_clearance_by_store(store_id, zip_code)
        rollback_items = await scraper.search_rollback_by_store(store_id, zip_code)
        return clearance_items + rollback_items


async def scrape_homedepot_store(store_id: str, zip_code: str) -> List[ScrapedItem]:
    """Scrape Home Depot store for deals"""
    async with HomeDepotScraper() as scraper:
        clearance_items = await scraper.search_clearance_by_store(store_id, zip_code)
        special_items = await scraper.search_special_buy_by_store(store_id, zip_code)
        return clearance_items + special_items


async def find_stores(zip_code: str, radius: int = 20) -> Dict[str, List[Dict]]:
    """Find all stores near ZIP code"""
    walmart_stores = await StoreLocator.find_walmart_stores(zip_code, radius)
    homedepot_stores = await StoreLocator.find_homedepot_stores(zip_code, radius)
    
    return {
        'walmart': walmart_stores,
        'homedepot': homedepot_stores
    }
