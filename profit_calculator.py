"""
Profit calculator module for retail arbitrage
"""
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

from config import PROFIT_CONFIG


class Marketplace(Enum):
    AMAZON = "amazon"
    EBAY = "ebay"


@dataclass
class ProfitAnalysis:
    """Complete profit analysis for an arbitrage opportunity"""
    # Input costs
    buy_price: float
    sales_tax_rate: float
    sales_tax_amount: float
    total_buy_cost: float
    
    # Selling price
    sell_price: float
    marketplace: str
    
    # Fees breakdown
    platform_fees: float
    payment_processing_fees: float
    fulfillment_fees: float
    total_fees: float
    
    # Shipping
    estimated_shipping: float
    
    # Profit metrics
    gross_revenue: float
    net_profit: float
    profit_margin: float
    roi_percent: float
    
    # Assessment
    is_profitable: bool
    opportunity_score: float
    recommendation: str
    
    # Details
    fee_breakdown: Dict[str, float]


class ProfitCalculator:
    """Calculate profits for retail arbitrage opportunities"""
    
    def __init__(
        self,
        sales_tax_rate: float = None,
        shipping_cost: float = None,
        min_profit_amount: float = None,
        min_profit_margin: float = None
    ):
        self.sales_tax_rate = sales_tax_rate or PROFIT_CONFIG.DEFAULT_SALES_TAX
        self.shipping_cost = shipping_cost or PROFIT_CONFIG.DEFAULT_SHIPPING_COST
        self.min_profit_amount = min_profit_amount or PROFIT_CONFIG.MIN_PROFIT_AMOUNT
        self.min_profit_margin = min_profit_margin or PROFIT_CONFIG.MIN_PROFIT_MARGIN
    
    def calculate_buy_cost(
        self, 
        item_price: float, 
        sales_tax_rate: float = None
    ) -> Dict[str, float]:
        """Calculate total cost to buy item"""
        tax_rate = sales_tax_rate or self.sales_tax_rate
        tax_amount = item_price * tax_rate
        
        return {
            'item_price': item_price,
            'sales_tax_rate': tax_rate,
            'sales_tax_amount': round(tax_amount, 2),
            'total_buy_cost': round(item_price + tax_amount, 2)
        }
    
    def calculate_amazon_fees(
        self, 
        sell_price: float,
        category: str = 'Other'
    ) -> Dict[str, float]:
        """Calculate Amazon selling fees"""
        # Referral fee (varies by category, default 15%)
        referral_rate = PROFIT_CONFIG.CATEGORY_MARGINS.get(category, PROFIT_CONFIG.AMAZON_FEE_PERCENT)
        referral_fee = sell_price * referral_rate
        
        # FBA fulfillment fee (estimated average)
        # In reality, this depends on size and weight
        fba_fee = self._estimate_fba_fee(sell_price)
        
        # Variable closing fee (for media categories)
        closing_fee = 0.0
        if category in ['Books', 'Music', 'DVD']:
            closing_fee = 1.80
        
        total_fees = referral_fee + fba_fee + closing_fee
        
        return {
            'referral_fee': round(referral_fee, 2),
            'fulfillment_fee': round(fba_fee, 2),
            'closing_fee': round(closing_fee, 2),
            'total_fees': round(total_fees, 2)
        }
    
    def calculate_ebay_fees(self, sell_price: float) -> Dict[str, float]:
        """Calculate eBay selling fees"""
        # Final value fee (~13% for most categories)
        final_value_fee = sell_price * PROFIT_CONFIG.EBAY_FEE_PERCENT
        
        # PayPal/Adyen processing fee
        payment_fee = (sell_price * PROFIT_CONFIG.PAYPAL_FEE_PERCENT) + PROFIT_CONFIG.PAYPAL_FEE_FIXED
        
        # Insertion fee (usually free for first 250 listings)
        insertion_fee = 0.0
        
        total_fees = final_value_fee + payment_fee + insertion_fee
        
        return {
            'final_value_fee': round(final_value_fee, 2),
            'payment_processing_fee': round(payment_fee, 2),
            'insertion_fee': round(insertion_fee, 2),
            'total_fees': round(total_fees, 2)
        }
    
    def calculate_profit(
        self,
        buy_price: float,
        sell_price: float,
        marketplace: str = 'amazon',
        category: str = 'Other',
        include_shipping: bool = True
    ) -> ProfitAnalysis:
        """Calculate complete profit analysis"""
        
        # Calculate buy cost with tax
        buy_cost = self.calculate_buy_cost(buy_price)
        total_buy_cost = buy_cost['total_buy_cost']
        
        # Calculate marketplace fees
        if marketplace.lower() == 'amazon':
            fees = self.calculate_amazon_fees(sell_price, category)
        else:
            fees = self.calculate_ebay_fees(sell_price)
        
        total_fees = fees['total_fees']
        
        # Calculate shipping cost
        shipping_cost = self.shipping_cost if include_shipping else 0.0
        
        # Calculate profit metrics
        gross_revenue = sell_price
        total_costs = total_buy_cost + total_fees + shipping_cost
        net_profit = gross_revenue - total_costs
        
        # Calculate margin and ROI
        profit_margin = (net_profit / sell_price) * 100 if sell_price > 0 else 0
        roi_percent = (net_profit / total_buy_cost) * 100 if total_buy_cost > 0 else 0
        
        # Determine if profitable
        is_profitable = (
            net_profit >= self.min_profit_amount and 
            profit_margin >= (self.min_profit_margin * 100)
        )
        
        # Calculate opportunity score (0-100)
        opportunity_score = self._calculate_opportunity_score(
            net_profit, profit_margin, roi_percent
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            is_profitable, net_profit, profit_margin, roi_percent
        )
        
        return ProfitAnalysis(
            buy_price=buy_price,
            sales_tax_rate=buy_cost['sales_tax_rate'],
            sales_tax_amount=buy_cost['sales_tax_amount'],
            total_buy_cost=total_buy_cost,
            sell_price=sell_price,
            marketplace=marketplace,
            platform_fees=fees.get('referral_fee') or fees.get('final_value_fee', 0),
            payment_processing_fees=fees.get('payment_processing_fee', 0),
            fulfillment_fees=fees.get('fulfillment_fee', 0),
            total_fees=total_fees,
            estimated_shipping=shipping_cost,
            gross_revenue=gross_revenue,
            net_profit=round(net_profit, 2),
            profit_margin=round(profit_margin, 2),
            roi_percent=round(roi_percent, 2),
            is_profitable=is_profitable,
            opportunity_score=round(opportunity_score, 2),
            recommendation=recommendation,
            fee_breakdown=fees
        )
    
    def compare_marketplaces(
        self,
        buy_price: float,
        amazon_price: float = None,
        ebay_price: float = None,
        category: str = 'Other'
    ) -> Dict[str, ProfitAnalysis]:
        """Compare profit across marketplaces"""
        results = {}
        
        if amazon_price and amazon_price > 0:
            results['amazon'] = self.calculate_profit(
                buy_price, amazon_price, 'amazon', category
            )
        
        if ebay_price and ebay_price > 0:
            results['ebay'] = self.calculate_profit(
                buy_price, ebay_price, 'ebay', category
            )
        
        return results
    
    def find_best_marketplace(
        self,
        buy_price: float,
        amazon_price: float = None,
        ebay_price: float = None,
        category: str = 'Other'
    ) -> Optional[ProfitAnalysis]:
        """Find the best marketplace for selling"""
        comparisons = self.compare_marketplaces(
            buy_price, amazon_price, ebay_price, category
        )
        
        if not comparisons:
            return None
        
        # Filter to only profitable opportunities
        profitable = {k: v for k, v in comparisons.items() if v.is_profitable}
        
        if not profitable:
            # Return the least unprofitable option
            return min(comparisons.values(), key=lambda x: x.net_profit)
        
        # Return the most profitable
        return max(profitable.values(), key=lambda x: x.net_profit)
    
    def _estimate_fba_fee(self, sell_price: float) -> float:
        """Estimate FBA fulfillment fee based on price tier"""
        # Simplified estimation based on typical FBA fees
        if sell_price < 10:
            return 3.22  # Small standard
        elif sell_price < 20:
            return 4.50  # Standard
        elif sell_price < 50:
            return 5.50  # Standard
        elif sell_price < 100:
            return 6.50  # Large standard
        else:
            return 8.00  # Oversize
    
    def _calculate_opportunity_score(
        self,
        net_profit: float,
        profit_margin: float,
        roi_percent: float
    ) -> float:
        """Calculate composite opportunity score (0-100)"""
        # Normalize each metric
        profit_score = min(net_profit / 20, 40)  # Max 40 points for $20+ profit
        margin_score = min(profit_margin / 2, 30)  # Max 30 points for 60%+ margin
        roi_score = min(roi_percent / 3, 30)  # Max 30 points for 90%+ ROI
        
        total_score = profit_score + margin_score + roi_score
        return min(total_score, 100)
    
    def _generate_recommendation(
        self,
        is_profitable: bool,
        net_profit: float,
        profit_margin: float,
        roi_percent: float
    ) -> str:
        """Generate recommendation based on analysis"""
        if not is_profitable:
            if net_profit < 0:
                return "AVOID: Negative profit potential"
            elif profit_margin < 10:
                return "LOW MARGIN: Insufficient profit margin"
            else:
                return "BELOW THRESHOLD: Doesn't meet minimum criteria"
        
        if net_profit > 20 and roi_percent > 50:
            return "EXCELLENT: High profit and ROI opportunity"
        elif net_profit > 10 and roi_percent > 30:
            return "GOOD: Solid profit potential"
        elif roi_percent > 50:
            return "PROMISING: High ROI, monitor closely"
        else:
            return "ACCEPTABLE: Meets minimum criteria"
    
    def batch_analyze(
        self,
        items: List[Dict],
        min_profit: float = None,
        min_margin: float = None
    ) -> List[ProfitAnalysis]:
        """Analyze multiple items at once"""
        results = []
        
        min_p = min_profit or self.min_profit_amount
        min_m = min_margin or self.min_profit_margin
        
        for item in items:
            try:
                analysis = self.calculate_profit(
                    buy_price=item.get('buy_price', 0),
                    sell_price=item.get('sell_price', 0),
                    marketplace=item.get('marketplace', 'amazon'),
                    category=item.get('category', 'Other')
                )
                
                # Filter by criteria
                if analysis.net_profit >= min_p and analysis.profit_margin >= (min_m * 100):
                    results.append(analysis)
                    
            except Exception as e:
                print(f"Error analyzing item {item}: {e}")
                continue
        
        # Sort by opportunity score
        results.sort(key=lambda x: x.opportunity_score, reverse=True)
        
        return results


# Convenience functions
def calculate_arbitrage_profit(
    buy_price: float,
    sell_price: float,
    marketplace: str = 'amazon',
    sales_tax_rate: float = None
) -> ProfitAnalysis:
    """Quick profit calculation"""
    calculator = ProfitCalculator(sales_tax_rate=sales_tax_rate)
    return calculator.calculate_profit(buy_price, sell_price, marketplace)


def find_best_opportunity(
    buy_price: float,
    amazon_price: float = None,
    ebay_price: float = None
) -> Optional[ProfitAnalysis]:
    """Find best opportunity across marketplaces"""
    calculator = ProfitCalculator()
    return calculator.find_best_marketplace(buy_price, amazon_price, ebay_price)
