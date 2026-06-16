import streamlit as st
import requests
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

# Set page config
st.set_page_config(page_title="RepoScan Q&A Bot", page_icon="🤖", layout="wide")

# Custom CSS for premium dark theme styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* Global settings and fonts */
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    font-family: 'Outfit', sans-serif !important;
    background-color: #0d0e15 !important;
    color: #e2e8f0 !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #12131f !important;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}

/* Custom premium card */
.premium-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
}

/* Title Gradient */
.title-gradient {
    background: linear-gradient(135deg, #a78bfa 0%, #3b82f6 50%, #60a5fa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    font-size: 2.8rem;
    margin-bottom: 5px;
}

/* Custom button style overrides */
div.stButton > button:first-child {
    background: linear-gradient(135deg, #6366f1 0%, #3b82f6 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 12px 28px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3) !important;
    transition: all 0.2s ease-in-out !important;
}

div.stButton > button:first-child:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5) !important;
    background: linear-gradient(135deg, #4f46e5 0%, #2563eb 100%) !important;
}

/* Success and Alert box overrides */
div[data-testid="stNotification"] {
    background-color: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 8px !important;
}

code {
    font-family: 'JetBrains Mono', monospace !important;
    background-color: rgba(255, 255, 255, 0.05) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
}

pre code {
    background-color: transparent !important;
    padding: 0 !important;
}
</style>
""", unsafe_allow_html=True)

# Main Title Header
st.markdown('<div class="title-gradient">🤖 RepoScan Q&A Bot</div>', unsafe_allow_html=True)
st.markdown('<p style="font-size: 1.1rem; color: #94a3b8;">Analyze any GitHub repository using AST-aware chunking and retrieve answers powered by Gemini 2.5 Flash.</p>', unsafe_allow_html=True)
st.write("---")

# Sidebar Configuration
with st.sidebar:
    st.markdown('<div style="font-size: 1.5rem; font-weight: 600; margin-bottom: 15px; color: #a78bfa;">⚙️ Control Panel</div>', unsafe_allow_html=True)
    
    st.markdown('<div style="font-weight: 500; margin-bottom: 5px;">Repository URL</div>', unsafe_allow_html=True)
    repo_url = st.text_input(
        "GitHub URL",
        placeholder="https://github.com/tiangolo/fastapi",
        label_visibility="collapsed"
    )
    
    if st.button("Ingest & Index", type="primary"):
        if not repo_url.strip():
            st.error("Please enter a valid GitHub repository URL.")
        else:
            with st.spinner("Cloning, parsing AST, and indexing chunks..."):
                try:
                    resp = requests.post(f"{API_BASE}/ingest", json={"repo_url": repo_url.strip()})
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"Successfully indexed {data['chunks_stored']} chunks from {data['files_processed']} files!")
                    else:
                        st.error(resp.json().get("detail", "Failed to ingest repository."))
                except Exception as e:
                    st.error(f"Error connecting to backend API: {e}")

    st.write("---")
    st.markdown('<div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 10px; color: #94a3b8;">Settings</div>', unsafe_allow_html=True)
    top_k = st.slider("Top Chunks to Retrieve", min_value=1, max_value=10, value=5)

# Query Section
st.markdown('<div class="premium-card">', unsafe_allow_html=True)
st.markdown('<div style="font-size: 1.4rem; font-weight: 600; margin-bottom: 10px;">Ask anything about the codebase</div>', unsafe_allow_html=True)
question = st.text_input(
    "Your question",
    placeholder="e.g. How does authentication work? or Where is the routing logic?",
    label_visibility="collapsed"
)
st.markdown('</div>', unsafe_allow_html=True)

if question:
    with st.spinner("Scanning codebase and generating answer..."):
        try:
            resp = requests.post(f"{API_BASE}/query", json={"question": question, "top_k": top_k})
            if resp.status_code == 200:
                data = resp.json()
                
                # Render Answer
                st.markdown('<div style="font-size: 1.5rem; font-weight: 600; margin-top: 20px; color: #60a5fa;">💡 Answer</div>', unsafe_allow_html=True)
                st.markdown(data["answer"])
                
                # Render Sources
                st.markdown('<div style="font-size: 1.3rem; font-weight: 600; margin-top: 30px; color: #34d399;">📚 Cited Sources</div>', unsafe_allow_html=True)
                cols = st.columns(2)
                for idx, src in enumerate(data["sources"]):
                    col_idx = idx % 2
                    cols[col_idx].code(src, language="text")
            elif resp.status_code == 404:
                st.warning("No codebase indexed yet. Please ingest a repository in the Control Panel first.")
            else:
                st.error(resp.json().get("detail", "Error processing query."))
        except Exception as e:
            st.error(f"Error connecting to backend API: {e}")

# Footer
st.markdown("<br><br><hr>", unsafe_allow_html=True)
st.markdown('<div style="text-align: center; color: #475569; font-size: 0.9rem;">Built with Tree-sitter · ChromaDB · FastAPI · Gemini API</div>', unsafe_allow_html=True)
