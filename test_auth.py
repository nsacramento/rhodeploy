"""Quick smoke test for the auth module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.auth import sign_up, sign_in, sign_out, get_current_user, get_user_id

SEP = "=" * 55

EMAIL    = "nic@rho-test.com"
PASSWORD = "Rho2026!"

print(f"\n{SEP}")
print(f"  AUTH TEST")
print(f"{SEP}")

# Sign up
print(f"\nSigning up as {EMAIL}...")
try:
    user = sign_up(EMAIL, PASSWORD)
    print(f"  Created: {user['email']}  (id: {user['id'][:8]}...)")
except Exception as e:
    print(f"  Already exists or error: {e}")

# Sign in
print(f"\nSigning in...")
user = sign_in(EMAIL, PASSWORD)
print(f"  Signed in: {user['email']}")
print(f"  User ID  : {user['id']}")

# Get current user
print(f"\nChecking session...")
current = get_current_user()
print(f"  Current user: {current['email']}")
print(f"  User ID     : {get_user_id()[:8]}...")

# Sign out
print(f"\nSigning out...")
sign_out()
current = get_current_user()
print(f"  After sign-out: {current}")

print(f"\n{SEP}\n")
