import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment variables
DEFAULT_SSH_PORT = int(os.getenv('SSH_PORT', 22))
DEFAULT_SSH_USERNAME = os.getenv('SSH_USERNAME', '')
MIN_CPU_CORES = int(os.getenv('MIN_CPU_CORES', 2))
MIN_MEMORY_MIB = int(os.getenv('MIN_MEMORY_MIB', 4096))
MIN_DISK_GIB = int(os.getenv('MIN_DISK_GIB', 30))

def main():
    st.title("Kubernetes Cluster Host Validator")
    st.write("This tool checks if a server meets the minimum requirements to join a Kubernetes cluster.")
    
    # Static text as specified in requirements
    st.write("### Does this server meet minimum cluster requirements?")
    
    # Input fields
    col1, col2 = st.columns(2)
    
    with col1:
        host = st.text_input("Host IP/DNS", placeholder="e.g., 192.168.1.100")
        username = st.text_input("SSH Username", value=DEFAULT_SSH_USERNAME, placeholder="e.g., ubuntu")
        port = st.number_input("SSH Port", value=DEFAULT_SSH_PORT, min_value=1, max_value=65535)
    
    with col2:
        auth_method = st.radio("Authentication Method", ["Password", "SSH Key"])
        
        if auth_method == "Password":
            password = st.text_input("SSH Password", type="password")
            key_path = None
        else:
            password = None
            key_path = st.text_input("SSH Private Key Path", placeholder="e.g., ~/.ssh/id_rsa")
    
    # Display current minimum requirements
    st.write("#### Minimum Requirements:")
    st.write(f"- CPU cores: {MIN_CPU_CORES}")
    st.write(f"- Memory: {MIN_MEMORY_MIB} MiB ({MIN_MEMORY_MIB/1024:.1f} GiB)")
    st.write(f"- Disk space (root /): {MIN_DISK_GIB} GiB free")
    
    # Test button
    if st.button("Test", type="primary"):
        if not host:
            st.error("Please enter a host IP or DNS name.")
            return
        
        if not username:
            st.error("Please enter a SSH username.")
            return
        
        if auth_method == "Password" and not password:
            st.error("Please enter a SSH password.")
            return
        
        if auth_method == "SSH Key" and not key_path:
            st.error("Please enter a SSH private key path.")
            return
        
        # Show spinner while checking
        with st.spinner("Checking server requirements..."):
            try:
                # Import the system check module
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from core.system import check_requirements
                
                # Perform the actual check
                result = check_requirements(
                    host=host,
                    username=username,
                    password=password,
                    key_path=key_path,
                    port=port,
                    min_cpu_cores=MIN_CPU_CORES,
                    min_memory_mib=MIN_MEMORY_MIB,
                    min_disk_gib=MIN_DISK_GIB
                )
                
                # Display results
                st.write("### Test Results")
                
                if result.get('error'):
                    st.error(f"Error: {result['error']}")
                    return
                
                # Show measured values
                st.write("#### Measured Values:")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("CPU Cores", result['cpu_cores'], 
                             delta=result['cpu_cores'] - MIN_CPU_CORES if result['cpu_cores'] >= MIN_CPU_CORES else None)
                with col2:
                    st.metric("Memory (MiB)", result['memory_mib'],
                             delta=result['memory_mib'] - MIN_MEMORY_MIB if result['memory_mib'] >= MIN_MEMORY_MIB else None)
                with col3:
                    st.metric("Disk Free (GiB)", result['disk_gib_free'],
                             delta=result['disk_gib_free'] - MIN_DISK_GIB if result['disk_gib_free'] >= MIN_DISK_GIB else None)
                
                # Show result message (Task 8: Decision Messaging)
                if result['ok']:
                    st.success("✅ **Congratulations, your host meets the minimum server requirements to be part of the cluster.**")
                else:
                    st.error("❌ **Your host doesn't meet minimum server requirements to be part of the cluster. Please ensure:**")
                    st.write(f"- **CPU:** {MIN_CPU_CORES} cores (measured: {result['cpu_cores']})")
                    st.write(f"- **Memory:** {MIN_MEMORY_MIB} MiB ({MIN_MEMORY_MIB/1024:.1f} GiB) (measured: {result['memory_mib']} MiB)")
                    st.write(f"- **Disk space:** {MIN_DISK_GIB} GiB free (measured: {result['disk_gib_free']} GiB)")
                    
                    if result['failures']:
                        st.write("#### Specific Failures:")
                        for failure in result['failures']:
                            st.write(f"- {failure}")
                
            except Exception as e:
                st.error(f"Error during check: {str(e)}")
                st.write("Please check your connection details and try again.")

if __name__ == "__main__":
    main()
