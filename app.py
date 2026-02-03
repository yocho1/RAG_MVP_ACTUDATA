"""
Multi-Tenant SaaS - Streamlit Frontend

A simple frontend interface for the multi-tenant document Q&A system.

FEATURES:
- API Key input for tenant authentication
- Question input field
- Display answer with source document
- Error handling for unauthorized access

MULTI-TENANT SECURITY:
- API key is sent in X-API-KEY header (not body)
- Tenant identity is resolved server-side
- Each tenant sees only their own data
"""

import streamlit as st
import requests

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Multi-Tenant SaaS - Document Q&A",
    page_icon="🔐",
    layout="centered"
)

# =============================================================================
# CONSTANTS
# =============================================================================

API_BASE_URL = "http://localhost:8000"
API_KEY_HEADER = "X-API-KEY"

# Predefined API keys for easy testing
DEMO_API_KEYS = {
    "Tenant A": "tenantA_key",
    "Tenant B": "tenantB_key",
    "Custom": ""
}

# =============================================================================
# SIDEBAR - AUTHENTICATION
# =============================================================================

st.sidebar.title("🔐 Authentication")
st.sidebar.markdown("---")

# Tenant selection dropdown
tenant_choice = st.sidebar.selectbox(
    "Select Tenant:",
    options=list(DEMO_API_KEYS.keys()),
    help="Choose a tenant or enter a custom API key"
)

# API Key input
if tenant_choice == "Custom":
    api_key = st.sidebar.text_input(
        "API Key:",
        type="password",
        placeholder="Enter your API key",
        help="Your unique API key for authentication"
    )
else:
    api_key = DEMO_API_KEYS[tenant_choice]
    st.sidebar.text_input(
        "API Key:",
        value=api_key,
        disabled=True,
        help=f"API key for {tenant_choice}"
    )

st.sidebar.markdown("---")
st.sidebar.markdown("""
### API Keys Reference
| Tenant | API Key |
|--------|---------|
| Tenant A | `tenantA_key` |
| Tenant B | `tenantB_key` |
""")

# =============================================================================
# MAIN CONTENT
# =============================================================================

st.title("📄 Multi-Tenant Document Q&A")
st.markdown("""
Ask questions about your documents. The system will search **only within your tenant's documents** 
and provide answers with source references.

**Security Note:** Each tenant can only access their own documents.
""")

st.markdown("---")

# =============================================================================
# QUESTION INPUT
# =============================================================================

question = st.text_area(
    "Your Question:",
    placeholder="What is the procedure for...?",
    height=100,
    help="Enter your question here. The system will search your tenant's documents."
)

# Submit button
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    submit_button = st.button("🔍 Get Answer", type="primary", use_container_width=True)

# =============================================================================
# API REQUEST AND RESPONSE HANDLING
# =============================================================================

if submit_button:
    # Validation
    if not api_key:
        st.error("❌ Please enter an API key in the sidebar.")
    elif not question.strip():
        st.error("❌ Please enter a question.")
    else:
        # Show loading spinner
        with st.spinner("Searching documents..."):
            try:
                # Prepare request
                # SECURITY: API key is sent in header, not body
                headers = {
                    API_KEY_HEADER: api_key,
                    "Content-Type": "application/json"
                }
                data = {"question": question.strip()}
                
                # Make API request
                response = requests.post(
                    f"{API_BASE_URL}/ask",
                    json=data,
                    headers=headers,
                    timeout=30
                )
                
                # Handle response
                if response.status_code == 200:
                    result = response.json()
                    
                    st.markdown("---")
                    
                    # Display answer
                    st.success("✅ Answer found!")
                    
                    # Tenant info
                    st.info(f"**Tenant:** {result.get('tenant', 'Unknown')}")
                    
                    # Answer box
                    st.markdown("### 💬 Answer")
                    st.markdown(f"> {result.get('answer', 'No answer')}")
                    
                    # Source document
                    source = result.get('source')
                    if source:
                        st.markdown("### 📄 Source Document")
                        st.code(source, language=None)
                    else:
                        st.warning("No source document available.")
                        
                elif response.status_code == 401:
                    st.error("🚫 **Unauthorized:** Invalid API key. Please check your credentials.")
                    error_detail = response.json().get('detail', 'Unknown error')
                    st.caption(f"Error: {error_detail}")
                    
                else:
                    st.error(f"❌ **Error:** {response.status_code}")
                    try:
                        error_detail = response.json().get('detail', response.text)
                        st.caption(f"Details: {error_detail}")
                    except:
                        st.caption(f"Response: {response.text}")
                        
            except requests.exceptions.ConnectionError:
                st.error("🔌 **Connection Error:** Cannot connect to the API server.")
                st.caption("Make sure the FastAPI backend is running on http://localhost:8000")
                
            except requests.exceptions.Timeout:
                st.error("⏱️ **Timeout:** The request took too long.")
                
            except Exception as e:
                st.error(f"❌ **Unexpected Error:** {str(e)}")

# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    Multi-Tenant SaaS API Demo | Data isolation guaranteed
</div>
""", unsafe_allow_html=True)
