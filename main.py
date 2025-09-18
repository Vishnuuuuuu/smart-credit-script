#!/usr/bin/env python3
"""
main.py — SmartCredit Standalone Script (Exact replica of main_api.py)

Features:
1. Logs into SmartCredit using Playwright (headless by default, set via .env)
2. Fetches JSON data from protected endpoints (exact same as main_api.py)
3. Extracts scores from /member/credit-report/smart-3b/ page
4. Saves raw JSON to data/smartcredit_raw.json
5. Normalizes data exactly like main_api.py and saves to:
   - data/smartcredit_normalized.json (complete normalized structure)
   - data/smartcredit_accounts.csv (accounts only)
   - data/smartcredit_scores.csv (scores only)
"""

import os
import json
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
EMAIL = os.getenv("SMARTCREDIT_EMAIL")
PASSWORD = os.getenv("SMARTCREDIT_PASSWORD")
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"

if not EMAIL or not PASSWORD:
    raise SystemExit("❌ Please set SMARTCREDIT_EMAIL and SMARTCREDIT_PASSWORD in .env")

# URLs
LOGIN_URL = "https://www.smartcredit.com/login"
DASHBOARD_URL_PATTERN = "**/member/**"
CREDIT_REPORT_URL = "https://www.smartcredit.com/member/credit-report/smart-3b/"

# Output paths
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
NORMALIZED_JSON = DATA_DIR / "smartcredit_normalized.json"
ACCOUNTS_CSV = DATA_DIR / "smartcredit_accounts.csv"
SCORES_CSV = DATA_DIR / "smartcredit_scores.csv"

# JSON endpoints (exact same as main_api.py)
ENDPOINTS = {
    "search_results": "https://www.smartcredit.com/member/privacy/search-results",
    "statistics": "https://www.smartcredit.com/member/privacy/search-result-statistics",
    "trades": "https://www.smartcredit.com/member/money-manager/law/trades",
    "credit_report_json": "https://www.smartcredit.com/member/credit-report/3b/simple.htm?format=JSON"
}

def normalize_report(raw: dict, scores: dict):
    """Normalize raw SmartCredit JSON into client's expected structure (exact copy from main_api.py)."""

    def safe_number(val):
        try:
            if val is None or val == "":
                return None
            return float(val)
        except (TypeError, ValueError):
            return None

    def safe_string(val):
        if val is None:
            return None
        return str(val).strip() if str(val).strip() else None

    normalized = {
        "personal_info": {},
        "scores": scores or {},
        "accounts": [],
        "inquiries": [],
        "public_records": [],
        "employers": []
    }

    # --- Parse rawReport for reuse in multiple sections ---
    cr_json = raw.get("credit_report_json", {})
    raw_report_str = None
    borrower = None
    true_link = None
    
    if isinstance(cr_json, dict):
        # Check if the personal info is in rawReport as a JSON string
        raw_report_str = cr_json.get("rawReport")
        
        if raw_report_str:
            try:
                # Parse the JSON string
                raw_report_data = json.loads(raw_report_str)
                
                # Navigate to the borrower data in the parsed structure
                bundle_components = raw_report_data.get("BundleComponents", {})
                if isinstance(bundle_components, dict):
                    bundle_component_list = bundle_components.get("BundleComponent", [])
                    if isinstance(bundle_component_list, dict):
                        bundle_component_list = [bundle_component_list]
                    
                    # Look for the MergeCreditReports type which contains borrower info
                    for comp in bundle_component_list:
                        if comp.get("Type") == "MergeCreditReports":
                            true_link = comp.get("TrueLinkCreditReportType", {})
                            borrower = true_link.get("Borrower", {})
                            break
                            
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                print(f"Warning: Could not parse rawReport JSON: {e}")

    # --- Personal Info ---
    if isinstance(cr_json, dict):
                
        # Fallback: try the original structure in case it's sometimes parsed
        if not borrower:
            bundle_components = cr_json.get("BundleComponents", {})
            if isinstance(bundle_components, dict):
                bundle_component_list = bundle_components.get("BundleComponent", [])
                if isinstance(bundle_component_list, dict):
                    bundle_component_list = [bundle_component_list]
                
                # Look for the MergeCreditReports type which contains borrower info
                for comp in bundle_component_list:
                    if comp.get("Type") == "MergeCreditReports":
                        true_link = comp.get("TrueLinkCreditReportType", {})
                        borrower = true_link.get("Borrower", {})
                        break
        
        if borrower:
            # Extract name - may need to construct from multiple sources
            name = borrower.get("BorrowerName")
            if not name:
                # Try to get name from Name array (SmartCredit format)
                names = borrower.get("Name", [])
                if isinstance(names, list) and names:
                    # Take the first primary name
                    primary_name = None
                    for name_obj in names:
                        name_type = name_obj.get("NameType", {})
                        if name_type.get("abbreviation") == "Primary":
                            primary_name = name_obj
                            break
                    
                    if not primary_name and names:
                        primary_name = names[0]  # Fallback to first name
                    
                    if primary_name:
                        name_data = primary_name.get("Name", {})
                        first = name_data.get("first", "")
                        middle = name_data.get("middle", "")
                        last = name_data.get("last", "")
                        
                        name_parts = [first, middle, last] if middle else [first, last]
                        name = " ".join([p for p in name_parts if p]).strip()
                
                # If we still have raw array data, convert to string as fallback
                if not name and isinstance(names, list) and names:
                    # Just use first name object as fallback
                    first_name_obj = names[0]
                    if isinstance(first_name_obj, dict):
                        name_data = first_name_obj.get("Name", {})
                        if name_data:
                            first = name_data.get("first", "")
                            middle = name_data.get("middle", "")
                            last = name_data.get("last", "")
                            name_parts = [p for p in [first, middle, last] if p]
                            name = " ".join(name_parts).strip()
                
                # Fallback to individual fields
                if not name:
                    first_name = borrower.get("firstName") or borrower.get("FirstName")
                    last_name = borrower.get("lastName") or borrower.get("LastName")
                    if first_name and last_name:
                        name = f"{first_name} {last_name}"
            
            # Ensure name is a string, not an array
            if isinstance(name, list):
                # If we somehow still have array data, extract the first valid name
                for name_item in name:
                    if isinstance(name_item, dict):
                        name_data = name_item.get("Name", {})
                        if name_data:
                            first = name_data.get("first", "")
                            middle = name_data.get("middle", "")
                            last = name_data.get("last", "")
                            name_parts = [p for p in [first, middle, last] if p]
                            name = " ".join(name_parts).strip()
                            break
            
            # Extract SSN
            ssn = (borrower.get("SocialSecurityNumber") or 
                   borrower.get("ssn") or 
                   (borrower.get("SocialPartition") or {}).get("Social"))
            
            # Extract address from BorrowerAddress array
            addresses = borrower.get("BorrowerAddress", [])
            if isinstance(addresses, dict):
                addresses = [addresses]
            
            address_str = None
            if addresses:
                # Take the first/most recent address
                addr_obj = addresses[0]
                credit_addr = addr_obj.get("CreditAddress", {})
                
                # Handle different address formats
                if credit_addr.get("unparsedStreet"):
                    # Unparsed format
                    street = credit_addr.get("unparsedStreet", "").strip()
                    city = credit_addr.get("city", "").strip()
                    state = credit_addr.get("stateCode", "").strip()
                    postal = credit_addr.get("postalCode", "").strip()
                else:
                    # Parsed format
                    house_num = credit_addr.get("houseNumber", "")
                    direction = credit_addr.get("direction", "")
                    street_name = credit_addr.get("streetName", "")
                    street_type = credit_addr.get("streetType", "")
                    
                    street_parts = [p for p in [house_num, direction, street_name, street_type] if p]
                    street = " ".join(street_parts)
                    
                    city = credit_addr.get("city", "").strip()
                    state = credit_addr.get("stateCode", "").strip()
                    postal = credit_addr.get("postalCode", "").strip()
                
                address_parts = [p for p in [street, city, state, postal] if p]
                address_str = ", ".join(address_parts) if address_parts else None
            
            # Extract birth date from Birth array
            birth_dates = borrower.get("Birth", [])
            if isinstance(birth_dates, dict):
                birth_dates = [birth_dates]
            
            birth_date = None
            if birth_dates:
                birth_date = birth_dates[0].get("date")
            
            normalized["personal_info"] = {
                "name": safe_string(name),
                "ssn": safe_string(ssn),
                "dateOfBirth": safe_string(birth_date),
                "address": address_str,
                "previous_addresses": []
            }
            
            # Extract previous addresses
            prev_addresses = borrower.get("PreviousAddress", [])
            if isinstance(prev_addresses, dict):
                prev_addresses = [prev_addresses]
            
            for prev_addr in prev_addresses:
                credit_address = prev_addr.get("CreditAddress", {})
                source = prev_addr.get("Source", {})
                bureau_info = source.get("Bureau", {})
                bureau_name = bureau_info.get("description") or bureau_info.get("symbol")
                
                # Construct address string
                if credit_address.get("unparsedStreet"):
                    addr_str = f"{credit_address.get('unparsedStreet', '')}, {credit_address.get('city', '')}, {credit_address.get('stateCode', '')}, {credit_address.get('postalCode', '')}".strip(', ')
                else:
                    # Construct from individual fields
                    street_parts = []
                    if credit_address.get("houseNumber"):
                        street_parts.append(credit_address.get("houseNumber"))
                    if credit_address.get("direction"):
                        street_parts.append(credit_address.get("direction"))
                    if credit_address.get("streetName"):
                        street_parts.append(credit_address.get("streetName"))
                    if credit_address.get("streetType"):
                        street_parts.append(credit_address.get("streetType"))
                    
                    street = " ".join(street_parts)
                    addr_str = f"{street}, {credit_address.get('city', '')}, {credit_address.get('stateCode', '')}, {credit_address.get('postalCode', '')}".strip(', ')
                
                normalized["personal_info"]["previous_addresses"].append({
                    "address": safe_string(addr_str) if addr_str.strip(', ') else None,
                    "date_reported": safe_string(prev_addr.get("dateReported")),
                    "bureau": safe_string(bureau_name)
                })

    # --- Scores ---
    # First, try to extract scores from BundleComponents (VantageScore components)
    if isinstance(cr_json, dict):
        comps = (cr_json.get("BundleComponents") or {}).get("BundleComponent", [])
        if isinstance(comps, dict):
            comps = [comps]
        for comp in comps:
            bureau = comp.get("Type")
            cs = comp.get("CreditScoreType") or {}
            score = cs.get("riskScore") or cs.get("score")
            if score and bureau:
                if "TUC" in bureau:
                    normalized["scores"]["TransUnion"] = score
                elif "EQF" in bureau:
                    normalized["scores"]["Equifax"] = score
                elif "EXP" in bureau:
                    normalized["scores"]["Experian"] = score
        
        # Also check scores in rawReport JSON - look for CreditScore array in MergeCreditReports
        if raw_report_str and borrower:
            try:
                credit_scores = borrower.get("CreditScore", [])
                if isinstance(credit_scores, list):
                    for credit_score in credit_scores:
                        score_value = credit_score.get("riskScore")
                        source = credit_score.get("Source", {})
                        bureau_info = source.get("Bureau", {})
                        bureau_symbol = bureau_info.get("symbol")
                        bureau_name = bureau_info.get("description")
                        
                        if score_value and bureau_symbol:
                            if bureau_symbol == "TUC" or (bureau_name and "TransUnion" in bureau_name):
                                normalized["scores"]["TransUnion"] = score_value
                            elif bureau_symbol == "EQF" or (bureau_name and "Equifax" in bureau_name):
                                normalized["scores"]["Equifax"] = score_value
                            elif bureau_symbol == "EXP" or (bureau_name and "Experian" in bureau_name):
                                normalized["scores"]["Experian"] = score_value
            except Exception as e:
                print(f"Warning: Could not extract scores from rawReport CreditScore array: {e}")

    # --- Accounts ---
    trades = (raw.get("trades") or {}).get("trades", [])
    if isinstance(trades, dict):
        trades = [trades]
    for trade in trades:
        # Extract institution info
        inst = trade.get("institution") or {}
        institution_name = inst.get("name")
        
        # Extract account type - use the actual field structure from SmartCredit
        account_type_obj = trade.get("accountTypeObj") or {}
        account_type_display = trade.get("accountTypeDisplay")
        account_type_description = account_type_obj.get("description")
        
        # Use the most descriptive name available
        account_type = account_type_display or account_type_description or trade.get("accountType")
        
        # Extract bureau info from nested memberCodeAccount structure
        member_code_account = trade.get("memberCodeAccount") or {}
        creditor_contact = member_code_account.get("creditorContact") or {}
        bureau = creditor_contact.get("creditorContactSource")
        
        # Fallback: try direct creditorContact (in case structure varies)
        if not bureau:
            creditor_contact_direct = trade.get("creditorContact") or {}
            bureau = creditor_contact_direct.get("creditorContactSource")
        
        # Final fallback to other possible bureau fields
        if not bureau:
            bureau = (trade.get("bureau") or 
                     trade.get("source") or
                     trade.get("reportingBureau"))
        
        # Extract account status
        account_status = trade.get("accountStatus") or trade.get("currentAccountRatingDisplay")
        
        # Extract amounts (SmartCredit uses string amounts)
        current_balance = trade.get("currentBalanceAmount")
        credit_limit = trade.get("creditLimitAmount") 
        high_credit = trade.get("highCreditAmount")
        
        # Extract dates
        open_date = trade.get("openDateFormatted") or trade.get("openDate")
        closed_date = trade.get("closedDate")
        
        # Extract account number
        account_number = trade.get("maskedAccountNumber")
        
        # Extract other fields
        payment_amount = trade.get("termsMonthlyPayment") or trade.get("scheduledMonthlyPayment")
        last_reported = trade.get("lastReported")
        member_code = trade.get("memberCode")
        
        # Payment history and delinquencies
        payment_history = trade.get("paymentHistory")
        times_30_late = trade.get("times30Late") 
        times_60_late = trade.get("times60Late")
        times_90_late = trade.get("times90Late")
        
        # Account age calculation (if not directly available)
        account_age = trade.get("accountAge")
        
        # Create the normalized account object matching your expected structure
        acct = {
            "institution": {
                "name": safe_string(institution_name)
            },
            "accountTypeObj": {
                "description": safe_string(account_type)
            } if account_type else None,
            "accountType": safe_string(account_type),
            "accountStatus": safe_string(account_status),
            "currentBalanceAmount": safe_string(current_balance),
            "creditLimitAmount": safe_string(credit_limit),
            "currentAccountRatingDisplay": safe_string(account_status),
            "openDateFormatted": safe_string(open_date),
            "maskedAccountNumber": safe_string(account_number),
            "highCreditAmount": safe_string(high_credit),
            "termsMonthlyPayment": safe_string(payment_amount),
            "paymentHistory": safe_string(payment_history),
            "times30Late": safe_number(times_30_late),
            "times60Late": safe_number(times_60_late),
            "times90Late": safe_number(times_90_late),
            "creditorContactSource": safe_string(bureau),
            "bureau": safe_string(bureau),
            "lastReported": safe_string(last_reported),
            "accountAge": safe_string(account_age),
            "dateClosed": safe_string(closed_date),
            "memberCode": safe_string(member_code),
            
            # Legacy field names for backward compatibility
            "account_type": safe_string(account_type),
            "status": safe_string(account_status),
            "balance": safe_number(current_balance) if current_balance else None,
            "credit_limit": safe_number(credit_limit) if credit_limit else None,
            "high_balance": safe_number(high_credit) if high_credit else None,
            "open_date": safe_string(open_date),
            "closed_date": safe_string(closed_date),
            "payment_amount": safe_number(payment_amount) if payment_amount else None,
            "account_number": safe_string(account_number),
            "last_reported": safe_string(last_reported),
            "account_age": safe_string(account_age)
        }
        normalized["accounts"].append(acct)

    # --- Additional Accounts from TradeLinePartition in rawReport ---
    # Extract accounts from TradeLinePartition which contains multi-bureau data
    if true_link:
        tradeline_partition = true_link.get("TradeLinePartition", [])
        if isinstance(tradeline_partition, dict):
            tradeline_partition = [tradeline_partition]
        
        for partition_item in tradeline_partition:
            tradeline_data = partition_item.get("Tradeline", {})
            
            # Handle cases where tradeline_data might be a list
            if isinstance(tradeline_data, list):
                tradelines = tradeline_data
            else:
                tradelines = [tradeline_data] if tradeline_data else []
            
            for tradeline in tradelines:
                if not isinstance(tradeline, dict):
                    continue
                
                # Extract bureau information from Source
                source = tradeline.get("Source", {})
                bureau_info = source.get("Bureau", {})
                bureau_symbol = bureau_info.get("symbol")
                bureau_name = bureau_info.get("description")
                
                # Extract basic account info
                creditor_name = (tradeline.get("creditorName") or 
                               tradeline.get("creditor_name") or
                               tradeline.get("institutionName") or
                               tradeline.get("institution_name") or
                               tradeline.get("lenderName") or
                               tradeline.get("subscriberName"))
                
                account_number = tradeline.get("accountNumber") or tradeline.get("maskedAccountNumber")
                account_type = (tradeline.get("accountType") or 
                              tradeline.get("accountTypeDescription") or
                              partition_item.get("accountTypeDescription"))
                account_status = (tradeline.get("accountStatus") or 
                                tradeline.get("accountCondition", {}).get("description"))
                current_balance = (tradeline.get("currentBalance") or 
                                 tradeline.get("balanceAmount"))
                credit_limit = (tradeline.get("creditLimit") or 
                              tradeline.get("creditLimitAmount"))
                high_balance = (tradeline.get("highBalance") or 
                              tradeline.get("highCreditAmount"))
                open_date = (tradeline.get("dateOpened") or 
                           tradeline.get("openDate"))
                close_date = (tradeline.get("dateClosed") or 
                            tradeline.get("closedDate"))
                last_reported = (tradeline.get("dateReported") or 
                               tradeline.get("lastReported"))
                
                # Convert dates to readable format if needed
                if open_date and "-" in str(open_date):
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(open_date, "%Y-%m-%d")
                        open_date = dt.strftime("%b %d, %Y")
                    except:
                        pass
                        
                if close_date and "-" in str(close_date):
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(close_date, "%Y-%m-%d")
                        close_date = dt.strftime("%b %d, %Y")
                    except:
                        pass
                
                # Create account entry for this bureau-specific tradeline
                tradeline_acct = {
                    "institution": {
                        "name": safe_string(creditor_name)
                    },
                    "accountTypeObj": {
                        "description": safe_string(account_type)
                    } if account_type else None,
                    "accountType": safe_string(account_type),
                    "accountStatus": safe_string(account_status),
                    "currentBalanceAmount": safe_string(current_balance),
                    "creditLimitAmount": safe_string(credit_limit),
                    "currentAccountRatingDisplay": safe_string(account_status),
                    "openDateFormatted": safe_string(open_date),
                    "maskedAccountNumber": safe_string(account_number),
                    "highCreditAmount": safe_string(high_balance),
                    "termsMonthlyPayment": None,
                    "paymentHistory": None,
                    "times30Late": None,
                    "times60Late": None,
                    "times90Late": None,
                    "creditorContactSource": safe_string(bureau_symbol),
                    "bureau": safe_string(bureau_symbol),
                    "lastReported": safe_string(last_reported),
                    "accountAge": None,
                    "dateClosed": safe_string(close_date),
                    "memberCode": None,
                    
                    # Legacy field names
                    "account_type": safe_string(account_type),
                    "status": safe_string(account_status),
                    "balance": safe_number(current_balance) if current_balance else None,
                    "credit_limit": safe_number(credit_limit) if credit_limit else None,
                    "high_balance": safe_number(high_balance) if high_balance else None,
                    "open_date": safe_string(open_date),
                    "closed_date": safe_string(close_date),
                    "payment_amount": None,
                    "account_number": safe_string(account_number),
                    "last_reported": safe_string(last_reported),
                    "account_age": None
                }
                
                # Avoid duplicates by checking if we already have this account
                is_duplicate = False
                for existing_acct in normalized["accounts"]:
                    if (existing_acct.get("maskedAccountNumber") == account_number and 
                        existing_acct.get("institution", {}).get("name") == creditor_name and
                        existing_acct.get("bureau") == bureau_symbol):
                        is_duplicate = True
                        break
                
                if not is_duplicate and creditor_name and account_number:
                    normalized["accounts"].append(tradeline_acct)

    # --- Additional Accounts from Individual Bureau Reports in rawReport ---
    if raw_report_str:
        try:
            raw_report_data = json.loads(raw_report_str)
            bundle_components = raw_report_data.get("BundleComponents", {})
            if isinstance(bundle_components, dict):
                bundle_component_list = bundle_components.get("BundleComponent", [])
                if isinstance(bundle_component_list, dict):
                    bundle_component_list = [bundle_component_list]
                
                # Look for individual bureau reports
                for comp in bundle_component_list:
                    comp_type = comp.get("Type")
                    if comp_type in ["TUCReportV6", "EQFReportV6", "EXPReportV6"]:
                        bureau_symbol = "TUC" if "TUC" in comp_type else ("EQF" if "EQF" in comp_type else "EXP")
                        bureau_name = "TransUnion" if bureau_symbol == "TUC" else ("Equifax" if bureau_symbol == "EQF" else "Experian")
                        
                        # Extract tradelines from this bureau report
                        report_data = comp.get("CreditReportType", {})
                        tradelines = report_data.get("Tradeline", []) or report_data.get("Trade", []) or report_data.get("Account", [])
                        if isinstance(tradelines, dict):
                            tradelines = [tradelines]
                        
                        for tradeline in tradelines:
                            # Extract basic info
                            creditor_name = (tradeline.get("creditorName") or 
                                           tradeline.get("creditor_name") or
                                           tradeline.get("institutionName") or
                                           tradeline.get("institution_name") or
                                           tradeline.get("lenderName") or
                                           tradeline.get("subscriberName"))
                            
                            account_number = tradeline.get("accountNumber") or tradeline.get("maskedAccountNumber")
                            account_type = tradeline.get("accountType") or tradeline.get("accountTypeDescription")
                            account_status = tradeline.get("accountStatus") or tradeline.get("accountCondition", {}).get("description")
                            current_balance = tradeline.get("currentBalance")
                            credit_limit = tradeline.get("creditLimit")
                            high_balance = tradeline.get("highBalance")
                            open_date = tradeline.get("dateOpened")
                            close_date = tradeline.get("dateClosed")
                            
                            # Create additional account entry
                            additional_acct = {
                                "institution": {
                                    "name": safe_string(creditor_name)
                                },
                                "accountTypeObj": {
                                    "description": safe_string(account_type)
                                } if account_type else None,
                                "accountType": safe_string(account_type),
                                "accountStatus": safe_string(account_status),
                                "currentBalanceAmount": safe_string(current_balance),
                                "creditLimitAmount": safe_string(credit_limit),
                                "currentAccountRatingDisplay": safe_string(account_status),
                                "openDateFormatted": safe_string(open_date),
                                "maskedAccountNumber": safe_string(account_number),
                                "highCreditAmount": safe_string(high_balance),
                                "creditorContactSource": safe_string(bureau_symbol),
                                "bureau": safe_string(bureau_symbol),
                                "dateClosed": safe_string(close_date),
                                
                                # Legacy field names
                                "account_type": safe_string(account_type),
                                "status": safe_string(account_status),
                                "balance": safe_number(current_balance) if current_balance else None,
                                "credit_limit": safe_number(credit_limit) if credit_limit else None,
                                "high_balance": safe_number(high_balance) if high_balance else None,
                                "open_date": safe_string(open_date),
                                "closed_date": safe_string(close_date),
                                "account_number": safe_string(account_number)
                            }
                            
                            # Avoid duplicates by checking if we already have this account
                            is_duplicate = False
                            for existing_acct in normalized["accounts"]:
                                if (existing_acct.get("maskedAccountNumber") == account_number and 
                                    existing_acct.get("institution", {}).get("name") == creditor_name):
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                normalized["accounts"].append(additional_acct)
                        
        except Exception as e:
            print(f"Warning: Could not extract additional accounts from rawReport bureau reports: {e}")

    # --- Inquiries ---
    # Check for inquiries in search_results first
    inqs = (raw.get("search_results") or {}).get("inquiries", [])
    if isinstance(inqs, dict):
        inqs = [inqs]
    for iq in inqs:
        normalized["inquiries"].append({
            "bureau": iq.get("bureau"),
            "business_name": iq.get("subscriberName"),
            "inquiry_date": iq.get("inquiryDate"),
            "type": iq.get("inquiryType"),
        })
    
    # Extract inquiries from InquiryPartition in rawReport
    if true_link:
        inquiry_partition = true_link.get("InquiryPartition", [])
        if isinstance(inquiry_partition, dict):
            inquiry_partition = [inquiry_partition]
        
        for inquiry_item in inquiry_partition:
            inquiry_data = inquiry_item.get("Inquiry", {})
            if inquiry_data:
                bureau_name = inquiry_data.get("bureau")
                # Try to get bureau from Source if not directly available
                if not bureau_name:
                    source = inquiry_data.get("Source", {})
                    bureau_info = source.get("Bureau", {})
                    bureau_name = bureau_info.get("description") or bureau_info.get("abbreviation")
                
                normalized["inquiries"].append({
                    "bureau": bureau_name,
                    "business_name": inquiry_data.get("subscriberName"),
                    "inquiry_date": inquiry_data.get("inquiryDate"),
                    "type": inquiry_data.get("inquiryType"),
                })
    
    # Also check for inquiries in rawReport borrower data (legacy fallback)
    if borrower:
        raw_inquiries = borrower.get("Inquiry", [])
        if isinstance(raw_inquiries, dict):
            raw_inquiries = [raw_inquiries]
        for iq in raw_inquiries:
            source = iq.get("Source", {})
            bureau_info = source.get("Bureau", {})
            bureau_name = bureau_info.get("description") or bureau_info.get("symbol")
            
            normalized["inquiries"].append({
                "bureau": bureau_name,
                "business_name": iq.get("subscriberName") or iq.get("businessName"),
                "inquiry_date": iq.get("inquiryDate") or iq.get("dateReported"),
                "type": iq.get("inquiryType") or iq.get("type"),
            })

    # --- Public Records ---
    prs = (raw.get("search_results") or {}).get("publicRecords", [])
    if isinstance(prs, dict):
        prs = [prs]
    for pr in prs:
        normalized["public_records"].append({
            "type": pr.get("type"),
            "date_filed": pr.get("dateFiled"),
            "status": pr.get("status"),
            "amount": safe_number(pr.get("amount")),
        })

    # --- Employers ---
    # Extract from rawReport borrower data
    if borrower:
        employers = borrower.get("Employer", [])
        if isinstance(employers, dict):
            employers = [employers]
        for emp in employers:
            source = emp.get("Source", {})
            bureau_info = source.get("Bureau", {})
            bureau_name = bureau_info.get("description") or bureau_info.get("symbol")
            
            normalized["employers"].append({
                "name": emp.get("name"),
                "date_reported": emp.get("dateReported") or emp.get("dateUpdated"),
                "bureau": bureau_name,
            })
    
    # Fallback: check old location for employers
    fallback_employers = (cr_json.get("Borrower") or {}).get("Employer", [])
    if isinstance(fallback_employers, dict):
        fallback_employers = [fallback_employers]
    for emp in fallback_employers:
        normalized["employers"].append({
            "name": emp.get("name") or emp.get("employerName"),
            "date_reported": emp.get("dateReported") or emp.get("dateUpdated"),
            "bureau": emp.get("bureau"),
        })

    return normalized


def main():
    aggregated = {}
    scores = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page = context.new_page()

        print("🌐 Opening login page...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("✍️ Filling credentials...")
        page.fill("input#j_username", EMAIL)
        page.fill("input#j_password", PASSWORD)

        print("🔑 Submitting login form...")
        page.click("button[name='loginbttn']")

        try:
            page.wait_for_url(DASHBOARD_URL_PATTERN, timeout=15000)
            print("✅ Login successful! Landed on:", page.url)
        except Exception:
            print("❌ Login failed or CAPTCHA required.")
            browser.close()
            return

        # Fetch JSON endpoints (exact same as main_api.py)
        for key, url in ENDPOINTS.items():
            try:
                resp = page.request.get(url, headers={"Accept": "application/json"})
                if resp.ok:
                    try:
                        data = resp.json()
                        aggregated[key] = data
                        print(f"📥 Fetched {key} from {url}")
                    except Exception:
                        aggregated[key] = {"__raw_text": resp.text()}
                        print(f"📥 Fetched {key} from {url} (as raw text)")
                else:
                    aggregated[key] = {"__http_status": resp.status, "__error": resp.text()}
                    print(f"⚠️ Failed to fetch {url}: {resp.status}")
            except Exception as e:
                aggregated[key] = {"__error_exception": str(e)}
                print(f"⚠️ Error fetching {url}: {e}")

        # Navigate to credit report page for scores
        print("🌐 Navigating to credit report page for scores...")
        page.goto(CREDIT_REPORT_URL, wait_until="domcontentloaded")

        try:
            tu = page.inner_text("div.border-transunion h1.fw-bold")
            exp = page.inner_text("div.border-experian h1.fw-bold")
            eqf = page.inner_text("div.border-equifax h1.fw-bold")

            scores = {
                "TransUnion": tu.strip(),
                "Experian": exp.strip(),
                "Equifax": eqf.strip()
            }
            print(f"✅ Extracted scores: TU={tu.strip()}, EXP={exp.strip()}, EQ={eqf.strip()}")
        except Exception as e:
            print("⚠️ Could not extract scores from page:", e)
            # Try to get scores from credit report JSON if available
            if "credit_report_json" in aggregated:
                cr_json = aggregated["credit_report_json"]
                if isinstance(cr_json, dict):
                    # Try to extract from BundleComponents
                    comps = (cr_json.get("BundleComponents") or {}).get("BundleComponent", [])
                    if isinstance(comps, dict):
                        comps = [comps]
                    for comp in comps:
                        bureau = comp.get("Type")
                        cs = comp.get("CreditScoreType") or {}
                        score = cs.get("riskScore") or cs.get("score")
                        if score and bureau:
                            if "TUC" in bureau:
                                scores["TransUnion"] = score
                            elif "EQF" in bureau:
                                scores["Equifax"] = score
                            elif "EXP" in bureau:
                                scores["Experian"] = score
                    if scores:
                        print("✅ Using scores from JSON data:", scores)

        browser.close()

    # Normalize data (exact same logic as main_api.py)
    normalized = normalize_report(aggregated, scores)
    
    # Save normalized JSON (exactly like response.json structure)
    with open(NORMALIZED_JSON, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)
    print(f"💾 Saved normalized JSON to {NORMALIZED_JSON}")

    # Save accounts CSV only (no XLSX)
    if normalized["accounts"]:
        df = pd.DataFrame(normalized["accounts"])
        df.to_csv(ACCOUNTS_CSV, index=False)
        print(f"📊 Generated {ACCOUNTS_CSV} with {len(normalized['accounts'])} accounts")
    else:
        print("⚠️ No accounts found to export")

    # Save scores CSV only (no XLSX)
    if scores:
        sdf = pd.DataFrame([scores])
        sdf.to_csv(SCORES_CSV, index=False)
        print("📊 Credit Scores:", scores)
    else:
        print("⚠️ No scores found")

    print(f"\n🎉 Complete! Generated files:")
    print(f"   📄 Normalized data: {NORMALIZED_JSON}")
    print(f"   📊 Accounts CSV: {ACCOUNTS_CSV}")
    print(f"   📊 Scores CSV: {SCORES_CSV}")

if __name__ == "__main__":
    main()