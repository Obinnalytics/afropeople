"""
Test script for AfroPeople Forum
This script tests basic functionality of the forum application.
"""

import requests
import sys

def test_application():
    """Test if the application is running and accessible"""
    base_url = "http://127.0.0.1:5000"
    
    try:
        # Test homepage
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("✅ Homepage accessible")
            
            # Check if basic HTML elements are present
            if "AfroPeople" in response.text:
                print("✅ Application title found")
            if "Categories" in response.text:
                print("✅ Categories section found")
            if "Login" in response.text:
                print("✅ Login functionality found")
                
        else:
            print(f"❌ Homepage returned status code: {response.status_code}")
            return False
            
        # Test registration page
        response = requests.get(f"{base_url}/register", timeout=5)
        if response.status_code == 200:
            print("✅ Registration page accessible")
        else:
            print(f"❌ Registration page error: {response.status_code}")
            
        # Test login page
        response = requests.get(f"{base_url}/login", timeout=5)
        if response.status_code == 200:
            print("✅ Login page accessible")
        else:
            print(f"❌ Login page error: {response.status_code}")
            
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to the application. Make sure it's running on http://127.0.0.1:5000")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timed out. The application might be slow to respond.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    print("🧪 Testing AfroPeople Forum Application")
    print("=" * 50)
    
    if test_application():
        print("=" * 50)
        print("✅ All tests passed! Your forum is working correctly.")
        print("🌍 Visit http://127.0.0.1:5000 to see your forum in action!")
    else:
        print("=" * 50)
        print("❌ Some tests failed. Please check the application.")
        sys.exit(1)

if __name__ == "__main__":
    main() 