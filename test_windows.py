"""
Quick test to verify Windows system detection works
"""
import sys
import os

# Add the project root to the Python path so we can import our modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from core.system import check_requirements

# Test with localhost (should work if SSH is enabled)
if __name__ == "__main__":
    print("Testing Windows system detection...")
    print("Make sure SSH server is running and you know your Windows credentials.")
    print()
    
    # You can update these with your actual credentials
    host = "localhost"  # or your machine's IP
    username = input("Enter your Windows username: ")
    password = input("Enter your Windows password: ")
    
    print(f"\nTesting connection to {host} with user {username}...")
    
    result = check_requirements(
        host=host,
        username=username,
        password=password,
        port=22
    )
    
    print("\n" + "="*50)
    print("RESULTS:")
    print("="*50)
    
    if result.get('error'):
        print(f"❌ Error: {result['error']}")
    else:
        print(f"✅ Connection successful!")
        print(f"CPU Cores: {result['cpu_cores']}")
        print(f"Memory: {result['memory_mib']} MiB ({result['memory_mib']/1024:.1f} GiB)")
        print(f"Disk Free: {result['disk_gib_free']} GiB")
        print(f"Requirements Met: {'✅ YES' if result['ok'] else '❌ NO'}")
        
        if result['failures']:
            print("\nFailures:")
            for failure in result['failures']:
                print(f"  - {failure}")
