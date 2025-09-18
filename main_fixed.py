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
RAW_JSON = DATA_DIR / "smartcredit_raw.json"
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

    # --- Inquiries ---
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

    # Save raw JSON
    with open(RAW_JSON, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2)
    print(f"💾 Saved raw JSON to {RAW_JSON}")

    # Normalize data (exact same logic as main_api.py)
    normalized = normalize_report(aggregated, scores)
    
    # Save normalized JSON
    with open(NORMALIZED_JSON, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)
    print(f"💾 Saved normalized JSON to {NORMALIZED_JSON}")

    # Save accounts CSV
    if normalized["accounts"]:
        df = pd.DataFrame(normalized["accounts"])
        df.to_csv(ACCOUNTS_CSV, index=False)
        try:
            df.to_excel(str(ACCOUNTS_CSV.with_suffix(".xlsx")), index=False)
        except Exception as e:
            print("⚠️ Could not save XLSX for accounts:", e)
        print(f"📊 Generated {ACCOUNTS_CSV} with {len(normalized['accounts'])} accounts")
    else:
        print("⚠️ No accounts found to export")

    # Save scores CSV
    if scores:
        sdf = pd.DataFrame([scores])
        sdf.to_csv(SCORES_CSV, index=False)
        try:
            sdf.to_excel(str(SCORES_CSV.with_suffix(".xlsx")), index=False)
        except Exception as e:
            print("⚠️ Could not save XLSX for scores:", e)
        print("📊 Credit Scores:", scores)
    else:
        print("⚠️ No scores found")

    print(f"\n🎉 Complete! Generated files:")
    print(f"   📄 Raw data: {RAW_JSON}")
    print(f"   📄 Normalized data: {NORMALIZED_JSON}")
    print(f"   📊 Accounts CSV: {ACCOUNTS_CSV}")
    print(f"   📊 Scores CSV: {SCORES_CSV}")

if __name__ == "__main__":
    main()