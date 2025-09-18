#!/usr/bin/env python3
"""
Debug script to analyze account extraction
"""
import json

# Load the raw data
with open("data/smartcredit_raw.json", "r") as f:
    raw_data = json.load(f)

# Load the normalized data
with open("data/smartcredit_normalized.json", "r") as f:
    normalized_data = json.load(f)

print("=== ACCOUNT ANALYSIS ===")
print(f"Total accounts in normalized data: {len(normalized_data['accounts'])}")

# Count accounts by bureau
bureau_counts = {}
null_institution_count = 0

for account in normalized_data['accounts']:
    bureau = account.get('bureau', 'Unknown')
    institution_name = account.get('institution', {}).get('name')
    
    if bureau not in bureau_counts:
        bureau_counts[bureau] = 0
    bureau_counts[bureau] += 1
    
    if not institution_name or institution_name == "null":
        null_institution_count += 1
        print(f"NULL INSTITUTION: Bureau={bureau}, Account#={account.get('account_number', 'N/A')}, Type={account.get('account_type', 'N/A')}")

print(f"\n=== BUREAU BREAKDOWN ===")
for bureau, count in bureau_counts.items():
    print(f"{bureau}: {count} accounts")

print(f"\nAccounts with null/missing institution names: {null_institution_count}")

# Check if we can find creditor names in raw data
print(f"\n=== RAW DATA CREDITOR NAMES SAMPLE ===")
credit_report = raw_data.get("raw", {}).get("credit_report_json", {})
raw_report_str = credit_report.get("rawReport")

if raw_report_str:
    try:
        raw_report_data = json.loads(raw_report_str)
        
        # Find all creditorName occurrences
        def find_creditor_names(data, path=""):
            names = []
            if isinstance(data, dict):
                for key, value in data.items():
                    if key == "creditorName" and isinstance(value, str) and value:
                        names.append(f"{path}.{key}: {value}")
                    elif isinstance(value, (dict, list)):
                        names.extend(find_creditor_names(value, f"{path}.{key}"))
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    names.extend(find_creditor_names(item, f"{path}[{i}]"))
            return names
        
        creditor_names = find_creditor_names(raw_report_data)
        print(f"Found {len(creditor_names)} creditorName entries in raw data")
        
        # Show first 10 unique creditor names
        unique_names = list(set([name.split(": ")[1] for name in creditor_names]))
        print("Sample creditor names found in raw data:")
        for name in sorted(unique_names)[:15]:
            print(f"  - {name}")
            
    except Exception as e:
        print(f"Error parsing raw report: {e}")

print(f"\n=== ACCOUNTS WITH INSTITUTIONS ===")
institution_accounts = [acc for acc in normalized_data['accounts'] if acc.get('institution', {}).get('name')]
print(f"Accounts with valid institutions: {len(institution_accounts)}")

print(f"\n=== SAMPLE VALID INSTITUTIONS ===")
for acc in institution_accounts[:10]:
    print(f"  - {acc.get('institution', {}).get('name')} ({acc.get('bureau', 'No Bureau')})")