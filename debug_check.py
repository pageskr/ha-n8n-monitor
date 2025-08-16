"""Debug script for n8n Monitor integration.

This script helps identify issues with the integration setup.
Run this from the Home Assistant custom_components directory.
"""

import sys
import json

def check_manifest():
    """Check if manifest.json is valid."""
    try:
        with open('n8n_monitor/manifest.json', 'r') as f:
            manifest = json.load(f)
            print("✓ manifest.json is valid JSON")
            print(f"  Domain: {manifest.get('domain')}")
            print(f"  Name: {manifest.get('name')}")
            print(f"  Version: {manifest.get('version')}")
            print(f"  Config flow: {manifest.get('config_flow')}")
            return True
    except Exception as e:
        print(f"✗ Error reading manifest.json: {e}")
        return False

def check_imports():
    """Check if all Python files can be imported."""
    modules = [
        'n8n_monitor',
        'n8n_monitor.const',
        'n8n_monitor.config_flow',
        'n8n_monitor.api',
        'n8n_monitor.coordinator',
        'n8n_monitor.sensor',
    ]
    
    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module} imported successfully")
        except Exception as e:
            print(f"✗ Error importing {module}: {e}")
            all_ok = False
    
    return all_ok

def check_translations():
    """Check if translation files are valid."""
    files = [
        'n8n_monitor/strings.json',
        'n8n_monitor/translations/en.json',
        'n8n_monitor/translations/ko.json',
    ]
    
    all_ok = True
    for file in files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                json.load(f)
                print(f"✓ {file} is valid JSON")
        except Exception as e:
            print(f"✗ Error reading {file}: {e}")
            all_ok = False
    
    return all_ok

def main():
    """Run all checks."""
    print("n8n Monitor Integration Debug Check")
    print("=" * 40)
    
    print("\n1. Checking manifest.json...")
    manifest_ok = check_manifest()
    
    print("\n2. Checking Python imports...")
    imports_ok = check_imports()
    
    print("\n3. Checking translation files...")
    translations_ok = check_translations()
    
    print("\n" + "=" * 40)
    if manifest_ok and imports_ok and translations_ok:
        print("✓ All checks passed!")
        print("\nIf you're still getting errors, check:")
        print("- Home Assistant logs for detailed error messages")
        print("- File permissions (should be readable by HA)")
        print("- No syntax errors in Python files")
    else:
        print("✗ Some checks failed. Fix the issues above and try again.")

if __name__ == "__main__":
    main()
