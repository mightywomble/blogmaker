#!/usr/bin/env python3
"""
Test script for GitHub API connectivity
This script helps troubleshoot GitHub API issues before saving files.
"""

import json
import requests
import sys
from datetime import datetime

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Error: config.json not found")
        print("Please run the main application first to create the configuration file.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ Error: Invalid JSON in config.json")
        sys.exit(1)

def get_headers(token):
    """Get GitHub API headers"""
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'BlogCreator-Test/1.0'
    }

def test_github_api(config):
    """Test GitHub API connectivity and rate limits"""
    print("🔍 Testing GitHub API connectivity...")
    
    token = config.get('GITHUB_TOKEN')
    if not token:
        print("❌ No GitHub token configured")
        return False
    
    headers = get_headers(token)
    
    try:
        # Test rate limit endpoint
        print("  📊 Checking rate limits...")
        response = requests.get('https://api.github.com/rate_limit', headers=headers, timeout=10)
        
        if response.status_code == 200:
            rate_data = response.json()
            core = rate_data['resources']['core']
            remaining = core['remaining']
            limit = core['limit']
            reset_time = datetime.fromtimestamp(core['reset'])
            
            print(f"  ✅ API Rate Limit: {remaining}/{limit} remaining")
            print(f"  🕐 Resets at: {reset_time}")
            
            if remaining < 10:
                print("  ⚠️  WARNING: Very few requests remaining!")
                return False
            elif remaining < 100:
                print("  ⚠️  WARNING: Low on API requests")
                
        else:
            print(f"  ❌ Rate limit check failed: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("  ❌ Request timed out")
        return False
    except requests.exceptions.ConnectionError:
        print("  ❌ Connection error - check internet connection")
        return False
    
    return True

def test_repository_access(config):
    """Test access to the configured repository"""
    print("🔍 Testing repository access...")
    
    username = config.get('GITHUB_USERNAME')
    repo = config.get('GITHUB_REPO')
    token = config.get('GITHUB_TOKEN')
    
    if not all([username, repo, token]):
        print("❌ Repository configuration incomplete")
        return False
    
    headers = get_headers(token)
    repo_url = f"https://api.github.com/repos/{username}/{repo}"
    
    try:
        print(f"  🌐 Testing access to {username}/{repo}...")
        response = requests.get(repo_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            repo_data = response.json()
            permissions = repo_data.get('permissions', {})
            
            print(f"  ✅ Repository found: {repo_data['full_name']}")
            print(f"  📖 Read access: {'✅' if permissions.get('pull') else '❌'}")
            print(f"  ✏️  Write access: {'✅' if permissions.get('push') else '❌'}")
            print(f"  👑 Admin access: {'✅' if permissions.get('admin') else '❌'}")
            
            if not permissions.get('push'):
                print("  ⚠️  WARNING: No write permissions - saving will fail!")
                return False
                
        elif response.status_code == 404:
            print("  ❌ Repository not found or no access")
            return False
        elif response.status_code == 403:
            print("  ❌ Access forbidden - check token permissions")
            return False
        else:
            print(f"  ❌ Unexpected status: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("  ❌ Request timed out")
        return False
    except requests.exceptions.ConnectionError:
        print("  ❌ Connection error")
        return False
    
    return True

def test_file_operation(config):
    """Test a simple file operation"""
    print("🔍 Testing file operations...")
    
    username = config.get('GITHUB_USERNAME')
    repo = config.get('GITHUB_REPO')
    branch = config.get('GITHUB_BRANCH', 'main')
    token = config.get('GITHUB_TOKEN')
    
    headers = get_headers(token)
    contents_url = f"https://api.github.com/repos/{username}/{repo}/contents?ref={branch}"
    
    try:
        print(f"  📁 Listing repository contents on {branch} branch...")
        response = requests.get(contents_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            contents = response.json()
            md_files = [f for f in contents if f['name'].endswith('.md')]
            
            print(f"  ✅ Found {len(contents)} total files")
            print(f"  📝 Found {len(md_files)} markdown files")
            
            if md_files:
                print("  📄 Markdown files:")
                for f in md_files[:5]:  # Show first 5
                    print(f"    - {f['name']}")
                if len(md_files) > 5:
                    print(f"    ... and {len(md_files) - 5} more")
                    
        else:
            print(f"  ❌ Failed to list contents: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("  ❌ Request timed out")
        return False
    except requests.exceptions.ConnectionError:
        print("  ❌ Connection error")
        return False
    
    return True

def main():
    """Main test function"""
    print("🧪 GitHub API Test Suite")
    print("=" * 40)
    
    config = load_config()
    
    print(f"📋 Configuration:")
    print(f"  Username: {config.get('GITHUB_USERNAME', 'Not set')}")
    print(f"  Repository: {config.get('GITHUB_REPO', 'Not set')}")
    print(f"  Branch: {config.get('GITHUB_BRANCH', 'main')}")
    print(f"  Token: {'✅ Set' if config.get('GITHUB_TOKEN') else '❌ Not set'}")
    print()
    
    success = True
    
    # Test API connectivity
    if not test_github_api(config):
        success = False
    print()
    
    # Test repository access
    if not test_repository_access(config):
        success = False
    print()
    
    # Test file operations
    if not test_file_operation(config):
        success = False
    print()
    
    print("=" * 40)
    if success:
        print("🎉 All tests passed! GitHub integration should work.")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        
    print("\n💡 Tips:")
    print("- Make sure your GitHub Personal Access Token has 'repo' permissions")
    print("- Check that the repository name and username are correct")
    print("- Ensure you have write access to the repository")
    print("- If rate limited, wait for the reset time shown above")

if __name__ == "__main__":
    main()
