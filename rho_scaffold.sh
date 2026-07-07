#!/bin/bash
# Rho — project scaffold
# Run from inside /Users/nic/rho:
#   bash /Users/nic/Documents/Claude/Projects/Co-Pilot/rho_scaffold.sh

set -e
ROOT="/Users/nic/rho"
cd "$ROOT"

echo "🛫  Scaffolding Rho..."

# ── Directory structure ─────────────────────────────────────────────────────
mkdir -p rho/modules rho/db rho/auth rho/utils data tests

# ── .gitignore ──────────────────────────────────────────────────────────────
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
*.egg-info/
dist/
build/

# Environment
.env

# macOS
.DS_Store

# VS Code
.vscode/

# Data (local caches only — real data lives in Supabase)
data/*.db
data/*.csv
EOF

# ── .env.example ────────────────────────────────────────────────────────────
cat > .env.example << 'EOF'
# Copy this file to .env and fill in your values. Never commit .env.

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# OpenAI (for plain-language weather insights)
OPENAI_API_KEY=your-openai-key

# App
RHO_ENV=development
EOF

# ── requirements.txt ────────────────────────────────────────────────────────
cat > requirements.txt << 'EOF'
streamlit>=1.35.0
supabase>=2.4.0
python-dotenv>=1.0.0
requests>=2.31.0
openai>=1.30.0
shapely>=2.0.0
EOF

# ── app.py (Streamlit entry point) ──────────────────────────────────────────
cat > app.py << 'EOF'
"""
Rho — A co-pilot for student pilots
Entry point: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Rho",
    page_icon="✈️",
    layout="wide",
)

st.title("✈️ Rho")
st.subheader("Your co-pilot for student pilots")
st.markdown("---")
st.info("Task 1 complete. Let's build.")
EOF

# ── rho/__init__.py ─────────────────────────────────────────────────────────
cat > rho/__init__.py << 'EOF'
"""Rho core package."""
EOF

# ── rho/modules/__init__.py ─────────────────────────────────────────────────
cat > rho/modules/__init__.py << 'EOF'
"""Rho feature modules."""
EOF

# Module stubs
for mod in airport weather notams routing insights comms diagram; do
cat > rho/modules/${mod}.py << PYEOF
"""
Rho — ${mod} module
Task: to be implemented in a future step.
"""


def placeholder():
    raise NotImplementedError("${mod} module not yet implemented.")
PYEOF
done

# ── rho/db/__init__.py + client.py ──────────────────────────────────────────
cat > rho/db/__init__.py << 'EOF'
"""Database layer (Supabase/PostgreSQL)."""
EOF

cat > rho/db/client.py << 'EOF'
"""
Supabase client initialisation.
Reads SUPABASE_URL and SUPABASE_ANON_KEY from environment / .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set in your .env file."
        )
    from supabase import create_client
    return create_client(url, key)
EOF

# ── rho/auth/__init__.py ────────────────────────────────────────────────────
cat > rho/auth/__init__.py << 'EOF'
"""Authentication helpers (Supabase Auth)."""
EOF

# ── rho/utils/__init__.py ───────────────────────────────────────────────────
cat > rho/utils/__init__.py << 'EOF'
"""Shared utilities."""
EOF

# ── tests/__init__.py ───────────────────────────────────────────────────────
touch tests/__init__.py

# ── data/.gitkeep ───────────────────────────────────────────────────────────
touch data/.gitkeep

# ── First commit ────────────────────────────────────────────────────────────
git add -A
git commit -m "feat: scaffold Rho project structure

- Streamlit entry point (app.py)
- Module stubs: airport, weather, notams, routing, insights, comms, diagram
- Database layer stub (Supabase client)
- Auth stub
- requirements.txt, .gitignore, .env.example"

git push origin main

echo ""
echo "✅  Rho is live on GitHub. Task 1 complete."
echo "    https://github.com/nsacramento/rho"
