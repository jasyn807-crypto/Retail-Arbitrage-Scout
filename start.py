#!/usr/bin/env python3
"""
Startup script for Retail Arbitrage Scout
Starts both the API server and Streamlit dashboard
"""
import subprocess
import sys
import time
import os
import signal
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import streamlit
        import playwright
        print("✅ All required dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\nPlease install dependencies:")
        print("  pip install -r requirements.txt")
        print("  playwright install")
        return False


def start_api():
    """Start the FastAPI server"""
    print("🚀 Starting API server...")
    return subprocess.Popen(
        [sys.executable, "api.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent
    )


def start_dashboard():
    """Start the Streamlit dashboard"""
    print("🖥️  Starting dashboard...")
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless=true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent
    )


def main():
    """Main startup function"""
    print("=" * 60)
    print("🛒 Retail Arbitrage Scout - Startup")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check for .env file
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("\n⚠️  .env file not found!")
        print("Creating from .env.example...")
        example_file = Path(__file__).parent / ".env.example"
        if example_file.exists():
            with open(example_file) as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
            print("✅ Created .env file. Please edit it with your API credentials.")
        else:
            print("❌ .env.example not found!")
    
    # Initialize database
    print("\n📦 Initializing database...")
    try:
        from database import init_database
        init_database()
        print("✅ Database ready")
    except Exception as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    
    # Start services
    api_process = None
    dashboard_process = None
    
    try:
        # Start API
        api_process = start_api()
        time.sleep(3)  # Wait for API to start
        
        # Check if API started successfully
        if api_process.poll() is not None:
            stdout, stderr = api_process.communicate()
            print(f"❌ API failed to start:")
            print(stderr.decode())
            sys.exit(1)
        
        print("✅ API server running at http://localhost:8000")
        print("   API Docs: http://localhost:8000/docs")
        
        # Start Dashboard
        dashboard_process = start_dashboard()
        time.sleep(5)  # Wait for dashboard to start
        
        # Check if dashboard started successfully
        if dashboard_process.poll() is not None:
            stdout, stderr = dashboard_process.communicate()
            print(f"❌ Dashboard failed to start:")
            print(stderr.decode())
            api_process.terminate()
            sys.exit(1)
        
        print("✅ Dashboard running at http://localhost:8501")
        
        print("\n" + "=" * 60)
        print("🎉 Retail Arbitrage Scout is running!")
        print("=" * 60)
        print("\n📱 Open your browser to:")
        print("   Dashboard: http://localhost:8501")
        print("   API Docs:  http://localhost:8000/docs")
        print("\n🛑 Press Ctrl+C to stop all services")
        print("=" * 60 + "\n")
        
        # Wait for interrupt
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if api_process.poll() is not None:
                print("⚠️  API server stopped unexpectedly")
                break
            
            if dashboard_process.poll() is not None:
                print("⚠️  Dashboard stopped unexpectedly")
                break
                
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    finally:
        # Cleanup
        if api_process:
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()
        
        if dashboard_process:
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()
        
        print("✅ All services stopped")
        print("\nThanks for using Retail Arbitrage Scout! 👋")


if __name__ == "__main__":
    main()
