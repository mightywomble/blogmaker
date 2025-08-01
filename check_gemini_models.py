#!/usr/bin/env python3
"""
Script to check available Gemini models and their correct names.
"""

import google.generativeai as genai
import os

def main():
    # Check for API key
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ No API key found!")
        print("Please set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        print("You can get an API key from: https://aistudio.google.com/apikey")
        print("\nTo set it temporarily:")
        print("export GEMINI_API_KEY='your-api-key-here'")
        return
    
    try:
        genai.configure(api_key=api_key)
        
        print("✅ Available Gemini models for generateContent:")
        print("=" * 50)
        
        models = []
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                models.append(model.name)
                print(f"  • {model.name}")
        
        if not models:
            print("No models found!")
        else:
            print(f"\n📝 Current recommended models:")
            print("  • gemini-1.5-pro (latest stable)")
            print("  • gemini-1.5-flash (faster, cheaper)")
            print("  • gemini-2.0-flash-exp (experimental)")
            
            print(f"\n⚠️  Note: 'gemini-pro' is deprecated.")
            print("   Use 'gemini-1.5-pro' instead.")
            
            print(f"\n🔧 For your AI rewrite tool, update to use:")
            print("   'gemini-1.5-pro' or 'gemini-2.0-flash-exp'")
            
    except Exception as e:
        print(f"❌ Error connecting to Gemini API: {e}")
        print("Check your API key and internet connection.")

if __name__ == "__main__":
    main()
