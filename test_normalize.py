#!/usr/bin/env python3
"""
Test script to verify the normalization function works with your actual data
"""

import json
import pandas as pd

def normalize_and_export_test(raw: dict, scores: dict):
    """Test version of normalize function"""
    
    accounts = []

    # Extract accounts from the actual data structure
    account_data = []
    
    # Try to get from 'accounts' key (direct structure)
    if "accounts" in raw and isinstance(raw["accounts"], list):
        account_data = raw["accounts"]
    # Try to get from nested structures
    elif "normalized" in raw and "accounts" in raw["normalized"]:
        account_data = raw["normalized"]["accounts"]
    elif "raw" in raw and "accounts" in raw["raw"]:
        account_data = raw["raw"]["accounts"]
    
    print(f"Found {len(account_data)} accounts to process")
    
    # Process each account
    for i, acct in enumerate(account_data):
        if not isinstance(acct, dict):
            continue
            
        # Extract account information
        institution_name = "Unknown"
        if acct.get("institution") and isinstance(acct.get("institution"), dict):
            institution_name = acct["institution"].get("name") or "Unknown"
        elif acct.get("creditorName"):
            institution_name = acct.get("creditorName")
        
        # Create account record
        account_record = {
            "account_name": institution_name,
            "account_number": acct.get("maskedAccountNumber") or acct.get("account_number", "Unknown"),
            "account_type": acct.get("accountType") or acct.get("account_type", "Unknown"),
            "status": acct.get("accountStatus") or acct.get("status", "Unknown"),
            "balance": acct.get("balance", 0),
            "credit_limit": acct.get("creditLimitAmount") or acct.get("credit_limit", 0),
            "high_balance": acct.get("highCreditAmount") or acct.get("high_balance", 0),
            "open_date": acct.get("openDateFormatted") or acct.get("open_date", "Unknown"),
            "monthly_payment": acct.get("termsMonthlyPayment") or acct.get("payment_amount", 0),
            "bureau": acct.get("bureau", "Unknown"),
            "member_code": acct.get("memberCode", "Unknown")
        }
        
        # Clean up credit limit (convert string to float if needed)
        try:
            if isinstance(account_record["credit_limit"], str):
                account_record["credit_limit"] = float(account_record["credit_limit"])
        except (ValueError, TypeError):
            account_record["credit_limit"] = 0
            
        # Clean up high balance
        try:
            if isinstance(account_record["high_balance"], str):
                account_record["high_balance"] = float(account_record["high_balance"])
        except (ValueError, TypeError):
            account_record["high_balance"] = 0
            
        # Clean up monthly payment
        try:
            if isinstance(account_record["monthly_payment"], str):
                account_record["monthly_payment"] = float(account_record["monthly_payment"])
        except (ValueError, TypeError):
            account_record["monthly_payment"] = 0
        
        accounts.append(account_record)
        print(f"Account {i+1}: {institution_name} - {account_record['account_type']} - ${account_record['balance']}")

    # Save accounts CSV
    if accounts:
        df = pd.DataFrame(accounts)
        df.to_csv("test_smartcredit_accounts.csv", index=False)
        print(f"\n✅ Generated test_smartcredit_accounts.csv with {len(accounts)} accounts")
        print("\nSample data:")
        print(df.head())
    else:
        print("❌ No accounts found!")

    # Save scores
    if scores:
        sdf = pd.DataFrame([scores])
        sdf.to_csv("test_smartcredit_scores.csv", index=False)
        print(f"\n✅ Generated test_smartcredit_scores.csv")
        print("Scores:", scores)

# Test with your response.json data
test_data = {
    "accounts": [
        {
            "accountAge": None,
            "accountStatus": "OPEN",
            "accountType": "Flexible Spending Credit Card",
            "account_number": "438854XXXXXXXXXX",
            "balance": 887.0,
            "bureau": "TUC",
            "creditLimitAmount": "5000",
            "institution": {
                "name": "Chase Bank"
            },
            "maskedAccountNumber": "438854XXXXXXXXXX",
            "memberCode": "026QK001",
            "openDateFormatted": "Jul 23, 2025",
            "termsMonthlyPayment": "40",
            "highCreditAmount": "887"
        },
        {
            "accountStatus": "OPEN",
            "accountType": "Credit Card",
            "account_number": "517805XXXXXX",
            "balance": 375.0,
            "bureau": "TUC",
            "creditLimitAmount": "750",
            "institution": {
                "name": "Capital One"
            },
            "maskedAccountNumber": "517805XXXXXX",
            "memberCode": "01DTV001",
            "openDateFormatted": "Apr 29, 2025",
            "termsMonthlyPayment": "25",
            "highCreditAmount": "375"
        },
        {
            "accountStatus": "OPEN",
            "accountType": "Automobile",
            "account_number": "413944XX",
            "balance": 8867.0,
            "bureau": "TUC",
            "creditLimitAmount": "0",
            "institution": {
                "name": "CarMax Auto Finance"
            },
            "maskedAccountNumber": "413944XX",
            "memberCode": "045WK001",
            "openDateFormatted": "Jul 11, 2021",
            "termsMonthlyPayment": "653",
            "highCreditAmount": "31388"
        }
    ]
}

test_scores = {
    "TransUnion": "640",
    "Experian": "648",
    "Equifax": "581"
}

if __name__ == "__main__":
    normalize_and_export_test(test_data, test_scores)