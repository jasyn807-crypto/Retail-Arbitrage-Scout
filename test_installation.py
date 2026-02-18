#!/usr/bin/env python3
"""
Test script to verify Retail Arbitrage Scout installation
"""
import sys
import importlib


def test_import(module_name, description):
    """Test if a module can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✅ {description}")
        return True
    except ImportError as e:
        print(f"❌ {description}: {e}")
        return False


def test_local_modules():
    """Test local module imports"""
    print("\n📦 Testing local modules...")
    
    modules = [
        ('config', 'Configuration module'),
        ('database', 'Database module'),
        ('utils', 'Utilities module'),
        ('profit_calculator', 'Profit calculator'),
    ]
    
    all_passed = True
    for module, desc in modules:
        if not test_import(module, desc):
            all_passed = False
    
    return all_passed


def test_dependencies():
    """Test external dependencies"""
    print("\n📚 Testing external dependencies...")
    
    dependencies = [
        ('fastapi', 'FastAPI framework'),
        ('uvicorn', 'Uvicorn server'),
        ('streamlit', 'Streamlit dashboard'),
        ('playwright', 'Playwright browser automation'),
        ('playwright_stealth', 'Playwright stealth plugin'),
        ('bs4', 'BeautifulSoup HTML parser'),
        ('fake_useragent', 'Fake User-Agent generator'),
        ('pydantic', 'Pydantic data validation'),
        ('sqlalchemy', 'SQLAlchemy ORM'),
        ('pandas', 'Pandas data analysis'),
        ('httpx', 'HTTPX async client'),
    ]
    
    all_passed = True
    for module, desc in dependencies:
        if not test_import(module, desc):
            all_passed = False
    
    return all_passed


def test_database():
    """Test database initialization"""
    print("\n🗄️  Testing database...")
    
    try:
        from database import init_database, get_db_session, Store
        init_database()
        
        with get_db_session() as session:
            # Try a simple query
            count = session.query(Store).count()
            print(f"✅ Database initialized (stores table accessible)")
            return True
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def test_playwright():
    """Test Playwright browser installation"""
    print("\n🎭 Testing Playwright...")
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        
        print("✅ Playwright Chromium browser installed")
        return True
        
    except Exception as e:
        print(f"❌ Playwright error: {e}")
        print("   Run: playwright install chromium")
        return False


def test_calculations():
    """Test profit calculations"""
    print("\n🧮 Testing profit calculator...")
    
    try:
        from profit_calculator import ProfitCalculator
        
        calc = ProfitCalculator()
        analysis = calc.calculate_profit(
            buy_price=10.00,
            sell_price=25.00,
            marketplace='amazon'
        )
        
        print(f"✅ Profit calculator working")
        print(f"   Example: Buy $10 → Sell $25 = ${analysis.net_profit:.2f} profit ({analysis.profit_margin:.1f}% margin)")
        return True
        
    except Exception as e:
        print(f"❌ Calculator error: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("🛒 Retail Arbitrage Scout - Installation Test")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Dependencies", test_dependencies()))
    results.append(("Local Modules", test_local_modules()))
    results.append(("Database", test_database()))
    results.append(("Playwright", test_playwright()))
    results.append(("Calculator", test_calculations()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("-" * 60)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! You're ready to use Retail Arbitrage Scout.")
        print("\nNext steps:")
        print("  1. Configure your .env file with API credentials")
        print("  2. Run: python start.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Install browsers: playwright install chromium")
        return 1


if __name__ == "__main__":
    sys.exit(main())
