"""
Marketplace price checker module
Checks prices on Amazon and eBay for given UPCs
"""
import asyncio
import random
import re
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import base64

import httpx
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
import fake_useragent

from config import SCRAPER_CONFIG, MARKETPLACE_CONFIG


@dataclass
class MarketplaceListing:
    """Data class for marketplace listings"""
    marketplace: str  # 'amazon' or 'ebay'
    listing_id: Optional[str] = None
    listing_title: Optional[str] = None
    listing_url: Optional[str] = None
    price: float = 0.0
    shipping_cost: float = 0.0
    total_price: float = 0.0
    condition: str = "New"
    seller_rating: Optional[float] = None
    is_buy_box: bool = False
    available: bool = True
    raw_data: Optional[Dict] = None


class eBayAPIClient:
    """eBay API client for price lookups"""
    
    def __init__(self):
        self.config = MARKETPLACE_CONFIG
        self.base_url = "https://api.ebay.com/buy/browse/v1"
        self.access_token = None
        
    async def _get_access_token(self) -> str:
        """Get OAuth access token"""
        if self.access_token:
            return self.access_token
        
        try:
            # OAuth credentials
            credentials = base64.b64encode(
                f"{self.config.EBAY_APP_ID}:{self.config.EBAY_CERT_ID}".encode()
            ).decode()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.ebay.com/identity/v1/oauth2/token",
                    headers={
                        "Authorization": f"Basic {credentials}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "grant_type": "client_credentials",
                        "scope": "https://api.ebay.com/oauth/api_scope/buy.item.search"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get('access_token')
                    return self.access_token
                else:
                    print(f"eBay auth error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Error getting eBay access token: {e}")
            return None
    
    async def search_by_upc(self, upc: str) -> List[MarketplaceListing]:
        """Search eBay by UPC"""
        listings = []
        
        try:
            token = await self._get_access_token()
            if not token:
                print("No eBay access token available")
                return listings
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/item_summary/search",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
                    },
                    params={
                        "q": upc,
                        "filter": "buyingOptions:{FIXED_PRICE}",
                        "sort": "-price",
                        "limit": 10
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    item_summaries = data.get('itemSummaries', [])
                    
                    for item in item_summaries:
                        listing = self._parse_ebay_item(item)
                        if listing:
                            listings.append(listing)
                else:
                    print(f"eBay API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            print(f"Error searching eBay: {e}")
        
        return listings
    
    async def search_by_keyword(self, keyword: str, limit: int = 5) -> List[MarketplaceListing]:
        """Search eBay by keyword (fallback when UPC not available)"""
        listings = []
        
        try:
            token = await self._get_access_token()
            if not token:
                return listings
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/item_summary/search",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
                    },
                    params={
                        "q": keyword,
                        "filter": "buyingOptions:{FIXED_PRICE}",
                        "sort": "price",
                        "limit": limit
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    item_summaries = data.get('itemSummaries', [])
                    
                    for item in item_summaries:
                        listing = self._parse_ebay_item(item)
                        if listing:
                            listings.append(listing)
                            
        except Exception as e:
            print(f"Error searching eBay by keyword: {e}")
        
        return listings
    
    def _parse_ebay_item(self, item: Dict) -> Optional[MarketplaceListing]:
        """Parse eBay item summary"""
        try:
            price_data = item.get('price', {})
            price = float(price_data.get('value', 0))
            currency = price_data.get('currency', 'USD')
            
            shipping_data = item.get('shippingOptions', [{}])[0]
            shipping_cost = float(shipping_data.get('shippingCost', {}).get('value', 0))
            
            return MarketplaceListing(
                marketplace='ebay',
                listing_id=item.get('itemId'),
                listing_title=item.get('title'),
                listing_url=item.get('itemWebUrl'),
                price=price,
                shipping_cost=shipping_cost,
                total_price=price + shipping_cost,
                condition=item.get('condition', 'New'),
                seller_rating=item.get('seller', {}).get('feedbackPercentage'),
                raw_data=item
            )
            
        except Exception as e:
            print(f"Error parsing eBay item: {e}")
            return None


class AmazonScraper:
    """Amazon scraper for price lookups (uses scraping due to API restrictions)"""
    
    def __init__(self):
        self.config = SCRAPER_CONFIG
        self.base_url = "https://www.amazon.com"
        self.user_agent = fake_useragent.UserAgent()
    
    async def search_by_upc(self, upc: str) -> List[MarketplaceListing]:
        """Search Amazon by UPC"""
        listings = []
        
        try:
            search_url = f"{self.base_url}/s?k={upc}"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.config.HEADLESS,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                context = await browser.new_context(
                    user_agent=random.choice(self.config.USER_AGENTS),
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                await stealth_async(page)
                
                # Add delay before request
                await asyncio.sleep(random.uniform(2, 4))
                
                await page.goto(search_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(random.uniform(2, 3))
                
                # Check for captcha
                if await self._check_captcha(page):
                    print("Amazon CAPTCHA detected, skipping...")
                    await browser.close()
                    return listings
                
                content = await page.content()
                listings = self._parse_amazon_search_results(content, upc)
                
                await browser.close()
                
        except Exception as e:
            print(f"Error scraping Amazon: {e}")
        
        return listings
    
    async def search_by_keyword(self, keyword: str, limit: int = 5) -> List[MarketplaceListing]:
        """Search Amazon by keyword"""
        listings = []
        
        try:
            search_url = f"{self.base_url}/s?k={keyword.replace(' ', '+')}"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.config.HEADLESS,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                context = await browser.new_context(
                    user_agent=random.choice(self.config.USER_AGENTS),
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                await stealth_async(page)
                
                await asyncio.sleep(random.uniform(2, 4))
                await page.goto(search_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(random.uniform(2, 3))
                
                if await self._check_captcha(page):
                    print("Amazon CAPTCHA detected, skipping...")
                    await browser.close()
                    return listings
                
                content = await page.content()
                listings = self._parse_amazon_search_results(content, keyword)[:limit]
                
                await browser.close()
                
        except Exception as e:
            print(f"Error searching Amazon by keyword: {e}")
        
        return listings
    
    async def get_product_details(self, asin: str) -> Optional[MarketplaceListing]:
        """Get detailed product info by ASIN"""
        try:
            product_url = f"{self.base_url}/dp/{asin}"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.config.HEADLESS,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                context = await browser.new_context(
                    user_agent=random.choice(self.config.USER_AGENTS),
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                await stealth_async(page)
                
                await asyncio.sleep(random.uniform(2, 4))
                await page.goto(product_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(random.uniform(2, 3))
                
                if await self._check_captcha(page):
                    await browser.close()
                    return None
                
                content = await page.content()
                listing = self._parse_amazon_product_page(content, asin)
                
                await browser.close()
                return listing
                
        except Exception as e:
            print(f"Error getting Amazon product details: {e}")
            return None
    
    async def _check_captcha(self, page) -> bool:
        """Check if page shows captcha"""
        captcha_indicators = [
            'captcha',
            'recaptcha',
            'robot check',
            'verify you are human',
            'security check',
            'enter the characters'
        ]
        
        content = await page.content()
        content_lower = content.lower()
        
        for indicator in captcha_indicators:
            if indicator in content_lower:
                return True
        
        return False
    
    def _parse_amazon_search_results(self, content: str, query: str) -> List[MarketplaceListing]:
        """Parse Amazon search results page"""
        listings = []
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find product containers
            product_elements = soup.find_all(attrs={'data-component-type': 's-search-result'})
            
            for elem in product_elements[:10]:  # Limit to 10 results
                try:
                    listing = self._parse_amazon_product_element(elem)
                    if listing and listing.price > 0:
                        listings.append(listing)
                except Exception as e:
                    print(f"Error parsing Amazon product element: {e}")
                    continue
            
            # If no results found with standard selector, try alternative
            if not listings:
                # Try finding by class patterns
                alt_elements = soup.find_all(class_=re.compile(r's-result-item|product', re.I))
                for elem in alt_elements[:10]:
                    try:
                        listing = self._parse_amazon_product_element(elem)
                        if listing and listing.price > 0:
                            listings.append(listing)
                    except Exception:
                        continue
                        
        except Exception as e:
            print(f"Error parsing Amazon search results: {e}")
        
        return listings
    
    def _parse_amazon_product_element(self, elem) -> Optional[MarketplaceListing]:
        """Parse individual Amazon product element"""
        try:
            # Get ASIN
            asin = elem.get('data-asin')
            if not asin:
                return None
            
            # Get title
            title_elem = elem.find('h2') or elem.find(attrs={'data-cy': 'title-recipe-title'})
            title = title_elem.get_text(strip=True) if title_elem else 'Unknown'
            
            # Get price - try multiple selectors
            price = 0.0
            price_selectors = [
                '.a-price-whole',
                '.a-price .a-offscreen',
                '.a-price-symbol + .a-price-whole',
                '[data-cy="price-recipe"]'
            ]
            
            for selector in price_selectors:
                price_elem = elem.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        price = float(price_match.group())
                        break
            
            # Get URL
            link_elem = elem.find('a', class_=re.compile(r'a-link-normal', re.I))
            product_url = f"{self.base_url}{link_elem['href']}" if link_elem and link_elem.get('href') else f"{self.base_url}/dp/{asin}"
            
            # Check if buy box (usually first result)
            is_buy_box = elem.get('data-index') == '0'
            
            return MarketplaceListing(
                marketplace='amazon',
                listing_id=asin,
                listing_title=title,
                listing_url=product_url,
                price=price,
                total_price=price,
                is_buy_box=is_buy_box
            )
            
        except Exception as e:
            print(f"Error parsing Amazon element: {e}")
            return None
    
    def _parse_amazon_product_page(self, content: str, asin: str) -> Optional[MarketplaceListing]:
        """Parse Amazon product detail page"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Get title
            title_elem = soup.find(id='productTitle') or soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else 'Unknown'
            
            # Get price
            price = 0.0
            price_elem = soup.find(id='priceblock_ourprice') or soup.find(id='priceblock_dealprice')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                if price_match:
                    price = float(price_match.group())
            
            return MarketplaceListing(
                marketplace='amazon',
                listing_id=asin,
                listing_title=title,
                listing_url=f"{self.base_url}/dp/{asin}",
                price=price,
                total_price=price,
                is_buy_box=True
            )
            
        except Exception as e:
            print(f"Error parsing Amazon product page: {e}")
            return None


class PriceComparisonEngine:
    """Main engine for comparing prices across marketplaces"""
    
    def __init__(self):
        self.ebay_client = eBayAPIClient()
        self.amazon_scraper = AmazonScraper()
    
    async def compare_prices(
        self, 
        upc: str = None, 
        product_name: str = None,
        check_ebay: bool = True,
        check_amazon: bool = True
    ) -> Dict[str, List[MarketplaceListing]]:
        """Compare prices across marketplaces"""
        results = {
            'ebay': [],
            'amazon': []
        }
        
        tasks = []
        
        # eBay search
        if check_ebay:
            if upc:
                tasks.append(('ebay', self.ebay_client.search_by_upc(upc)))
            elif product_name:
                tasks.append(('ebay', self.ebay_client.search_by_keyword(product_name)))
        
        # Amazon search
        if check_amazon:
            if upc:
                tasks.append(('amazon', self.amazon_scraper.search_by_upc(upc)))
            elif product_name:
                tasks.append(('amazon', self.amazon_scraper.search_by_keyword(product_name)))
        
        # Execute all searches concurrently
        if tasks:
            results_list = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
            
            for (marketplace, _), result in zip(tasks, results_list):
                if isinstance(result, list):
                    results[marketplace] = result
                else:
                    print(f"Error in {marketplace} search: {result}")
        
        return results
    
    async def get_best_price(
        self, 
        upc: str = None, 
        product_name: str = None
    ) -> Optional[MarketplaceListing]:
        """Get the best price across all marketplaces"""
        results = await self.compare_prices(upc, product_name)
        
        all_listings = []
        for marketplace_listings in results.values():
            all_listings.extend(marketplace_listings)
        
        if not all_listings:
            return None
        
        # Sort by total price (price + shipping)
        all_listings.sort(key=lambda x: x.total_price)
        
        return all_listings[0] if all_listings else None
    
    def calculate_fees(self, listing: MarketplaceListing) -> Dict[str, float]:
        """Calculate estimated fees for a listing"""
        from config import PROFIT_CONFIG
        
        price = listing.price
        
        if listing.marketplace == 'amazon':
            # Amazon fees: ~15% referral fee
            referral_fee = price * PROFIT_CONFIG.AMAZON_FEE_PERCENT
            # FBA fees (estimated average)
            fba_fee = 5.50  # Approximate for standard size
            total_fees = referral_fee + fba_fee
            
            return {
                'referral_fee': referral_fee,
                'fulfillment_fee': fba_fee,
                'total_fees': total_fees
            }
        
        elif listing.marketplace == 'ebay':
            # eBay fees: ~13% final value fee
            final_value_fee = price * PROFIT_CONFIG.EBAY_FEE_PERCENT
            # PayPal fees
            paypal_fee = (price * PROFIT_CONFIG.PAYPAL_FEE_PERCENT) + PROFIT_CONFIG.PAYPAL_FEE_FIXED
            total_fees = final_value_fee + paypal_fee
            
            return {
                'final_value_fee': final_value_fee,
                'paypal_fee': paypal_fee,
                'total_fees': total_fees
            }
        
        return {'total_fees': 0.0}


# Convenience functions
async def check_marketplace_prices(
    upc: str = None,
    product_name: str = None,
    check_ebay: bool = True,
    check_amazon: bool = True
) -> Dict[str, List[MarketplaceListing]]:
    """Check prices on marketplaces"""
    engine = PriceComparisonEngine()
    return await engine.compare_prices(upc, product_name, check_ebay, check_amazon)


async def get_best_selling_price(
    upc: str = None,
    product_name: str = None
) -> Optional[MarketplaceListing]:
    """Get best selling price across marketplaces"""
    engine = PriceComparisonEngine()
    return await engine.get_best_price(upc, product_name)
