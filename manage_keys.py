#!/usr/bin/env python3
"""
RIGEL API Key Management Script
Copyright (C) 2025 Zerone Laboratories

This script helps manage API keys for the RIGEL Web Service.
"""

import sqlite3
import hashlib
import secrets
import sys
from datetime import datetime
from typing import Optional

DB_PATH = "rigel_usage.db"

def create_api_key(name: str, plan: str = "free") -> str:
    """Create a new API key for a tenant"""
    api_key = f"rigel_{secrets.token_urlsafe(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    quotas = {
        "free": {"monthly": 1000, "daily": 100},
        "pro": {"monthly": 20000, "daily": 1000},
        "enterprise": {"monthly": 100000, "daily": 5000}
    }
    
    quota = quotas.get(plan, quotas["free"])
    
    try:
        cursor.execute("""
            INSERT INTO tenants (name, api_key_hash, plan, monthly_quota, daily_quota)
            VALUES (?, ?, ?, ?, ?)
        """, (name, api_key_hash, plan, quota["monthly"], quota["daily"]))
        
        conn.commit()
        print(f"✓ Created API key for '{name}' with '{plan}' plan")
        print(f"API Key: {api_key}")
        print("⚠️  Save this key securely - it won't be shown again!")
        
    except sqlite3.IntegrityError:
        print("❌ Error: API key already exists (very unlikely)")
        return None
    finally:
        conn.close()
    
    return api_key

def list_tenants():
    """List all tenants"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, plan, active, created_at, monthly_quota, daily_quota
        FROM tenants ORDER BY created_at DESC
    """)
    
    tenants = cursor.fetchall()
    conn.close()
    
    if not tenants:
        print("No tenants found.")
        return
    
    print(f"{'ID':<4} {'Name':<20} {'Plan':<12} {'Active':<8} {'Monthly Quota':<15} {'Daily Quota':<12} {'Created':<20}")
    print("-" * 100)
    
    for tenant in tenants:
        tenant_id, name, plan, active, created_at, monthly_quota, daily_quota = tenant
        status = "✓" if active else "✗"
        print(f"{tenant_id:<4} {name:<20} {plan:<12} {status:<8} {monthly_quota:<15} {daily_quota:<12} {created_at:<20}")

def get_usage_stats(tenant_id: int):
    """Get usage statistics for a tenant"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute("""
        SELECT name, plan, monthly_quota, daily_quota FROM tenants WHERE id = ?
    """, (tenant_id,))
    
    tenant_row = cursor.fetchone()
    if not tenant_row:
        print(f"❌ Tenant with ID {tenant_id} not found")
        conn.close()
        return
    
    name, plan, monthly_quota, daily_quota = tenant_row
    
    # Get usage statistics
    cursor.execute("""
        SELECT COUNT(*) FROM usage 
        WHERE tenant_id = ? AND timestamp >= date('now', '-30 days')
    """, (tenant_id,))
    monthly_usage = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM usage 
        WHERE tenant_id = ? AND date(timestamp) = date('now')
    """, (tenant_id,))
    daily_usage = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM usage WHERE tenant_id = ?
    """, (tenant_id,))
    total_requests = cursor.fetchone()[0]
    
    # Get endpoint breakdown
    cursor.execute("""
        SELECT endpoint, COUNT(*) FROM usage 
        WHERE tenant_id = ? GROUP BY endpoint ORDER BY COUNT(*) DESC
    """, (tenant_id,))
    endpoint_stats = cursor.fetchall()
    
    conn.close()
    
    print(f"\n📊 Usage Statistics for '{name}' (ID: {tenant_id})")
    print(f"Plan: {plan}")
    print(f"Monthly Usage: {monthly_usage}/{monthly_quota} ({monthly_usage/monthly_quota*100:.1f}%)")
    print(f"Daily Usage: {daily_usage}/{daily_quota} ({daily_usage/daily_quota*100:.1f}%)")
    print(f"Total Requests: {total_requests}")
    
    if endpoint_stats:
        print("\nEndpoint Breakdown:")
        for endpoint, count in endpoint_stats:
            print(f"  {endpoint}: {count} requests")

def deactivate_tenant(tenant_id: int):
    """Deactivate a tenant"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE tenants SET active = 0 WHERE id = ?", (tenant_id,))
    
    if cursor.rowcount > 0:
        print(f"✓ Deactivated tenant ID {tenant_id}")
    else:
        print(f"❌ Tenant ID {tenant_id} not found")
    
    conn.commit()
    conn.close()

def activate_tenant(tenant_id: int):
    """Activate a tenant"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE tenants SET active = 1 WHERE id = ?", (tenant_id,))
    
    if cursor.rowcount > 0:
        print(f"✓ Activated tenant ID {tenant_id}")
    else:
        print(f"❌ Tenant ID {tenant_id} not found")
    
    conn.commit()
    conn.close()

def main():
    if len(sys.argv) < 2:
        print("RIGEL API Key Management")
        print("\nUsage:")
        print("  python manage_keys.py create <name> [plan]     - Create new API key")
        print("  python manage_keys.py list                     - List all tenants")
        print("  python manage_keys.py usage <tenant_id>        - Show usage stats")
        print("  python manage_keys.py deactivate <tenant_id>   - Deactivate tenant")
        print("  python manage_keys.py activate <tenant_id>     - Activate tenant")
        print("\nPlans: free, pro, enterprise")
        return
    
    command = sys.argv[1].lower()
    
    if command == "create":
        if len(sys.argv) < 3:
            print("❌ Usage: python manage_keys.py create <name> [plan]")
            return
        
        name = sys.argv[2]
        plan = sys.argv[3] if len(sys.argv) > 3 else "free"
        
        if plan not in ["free", "pro", "enterprise"]:
            print("❌ Invalid plan. Choose from: free, pro, enterprise")
            return
        
        create_api_key(name, plan)
    
    elif command == "list":
        list_tenants()
    
    elif command == "usage":
        if len(sys.argv) < 3:
            print("❌ Usage: python manage_keys.py usage <tenant_id>")
            return
        
        try:
            tenant_id = int(sys.argv[2])
            get_usage_stats(tenant_id)
        except ValueError:
            print("❌ Invalid tenant ID. Must be a number.")
    
    elif command == "deactivate":
        if len(sys.argv) < 3:
            print("❌ Usage: python manage_keys.py deactivate <tenant_id>")
            return
        
        try:
            tenant_id = int(sys.argv[2])
            deactivate_tenant(tenant_id)
        except ValueError:
            print("❌ Invalid tenant ID. Must be a number.")
    
    elif command == "activate":
        if len(sys.argv) < 3:
            print("❌ Usage: python manage_keys.py activate <tenant_id>")
            return
        
        try:
            tenant_id = int(sys.argv[2])
            activate_tenant(tenant_id)
        except ValueError:
            print("❌ Invalid tenant ID. Must be a number.")
    
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
