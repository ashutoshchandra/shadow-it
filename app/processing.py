# app/processing.py
import pandas as pd
import os
import datetime
from collections import Counter, defaultdict
import numpy as np  # Import numpy to check types if needed, or just cast
from flask import current_app
import traceback # For detailed error logging

# --- Data Caching (Simple simulation for PoC) ---
_cached_data = None
_data_load_time = None
_cache_ttl = datetime.timedelta(minutes=5) # Cache data for 5 mins

def load_and_cache_data(force_reload=False):
    """Loads data from sources, using a simple time-based cache."""
    global _cached_data, _data_load_time

    now = datetime.datetime.now()
    if not force_reload and _cached_data and _data_load_time and (now - _data_load_time < _cache_ttl):
        return _cached_data

    try:
        cfg = current_app.config
        network_df = pd.read_csv(cfg['NETWORK_LOG_FILE'])
        expenses_df = pd.read_csv(cfg['EXPENSES_FILE'])
        known_apps_df = pd.read_csv(cfg['KNOWN_APPS_FILE'], keep_default_na=False, na_values=['']) # Read blank as NaN

        # --- Basic Data Cleaning/Preparation ---
        if 'timestamp' in network_df.columns:
            network_df['timestamp'] = pd.to_datetime(network_df['timestamp']).dt.tz_localize(None)
        if 'date' in expenses_df.columns:
            expenses_df['date'] = pd.to_datetime(expenses_df['date'])

        # Drop duplicates in known_apps_df if any, keeping the first entry for a domain
        if 'domain' in known_apps_df.columns:
            known_apps_df = known_apps_df.drop_duplicates(subset='domain', keep='first')

            # Handle boolean cols potentially read as objects - ensure they are real bools or None
            for col in ['compliance_gdpr', 'compliance_hipaa', 'known_breach']:
                if col in known_apps_df.columns:
                    # Map various 'truthy'/'falsy' representations to bool, keeping NaN/None as None
                    map_dict = {
                        'True': True, 'true': True, 'TRUE': True, True: True, 1: True, '1': True,
                        'False': False, 'false': False, 'FALSE': False, False: False, 0: False, '0': False,
                        np.nan: None, None: None, '': None # Map blanks/NaN/None to None
                    }
                    known_apps_df[col] = known_apps_df[col].map(map_dict)
                    # Explicitly convert to nullable boolean only if necessary, None is usually sufficient
                    # try:
                    #     known_apps_df[col] = known_apps_df[col].astype('boolean')
                    # except Exception: # Handle mixed types or other conversion errors
                    #     pass # Keep original or map to None on error if desired


            # Set index *after* potential type conversion
            known_apps_df.set_index('domain', inplace=True, drop=False)

            # Handle resolution_status potential NaN/None correctly
            if 'resolution_status' not in known_apps_df.columns:
                known_apps_df['resolution_status'] = pd.Series(dtype='object')
            # Ensure it's treated as string or None, replace NaN from read with None
            known_apps_df['resolution_status'] = known_apps_df['resolution_status'].fillna(value=np.nan).replace([np.nan], [None]).astype(object)

        else:
             print("Warning: 'domain' column missing from known_apps.csv. Index not set.")


        _cached_data = {
            'network': network_df,
            'expenses': expenses_df,
            'known_apps': known_apps_df
        }
        _data_load_time = now
        return _cached_data

    except FileNotFoundError as e:
        print(f"Error loading data file: {e}\n{traceback.format_exc()}")
        raise # Re-raise the exception
    except Exception as e:
        print(f"An unexpected error occurred loading data: {e}\n{traceback.format_exc()}")
        raise

# --- Safe Type Conversion Helpers ---
def safe_int(value, default=0):
    """Safely convert value to int, handling potential NaN/None/errors."""
    if pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """Safely convert value to float, handling potential NaN/None/errors."""
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_bool(value, default=None):
    """
    Safely convert value to Python bool or None.
    Handles various 'truthy'/'falsy' representations including pd.NA.
    Default is None if conversion is ambiguous or value is NA.
    """
    if pd.isna(value) or value == '':
        return default # Default for missing/empty

    true_vals = {True, 'true', 'True', 'TRUE', '1', 1}
    false_vals = {False, 'false', 'False', 'FALSE', '0', 0}

    if value in true_vals:
        return True
    elif value in false_vals:
        return False
    else:
         # Handle unexpected types more gracefully, log maybe?
        # print(f"Warning: Ambiguous boolean value '{value}', treating as default ({default}).")
         return default # Or raise an error if strict conversion needed


# --- Main Processing Function ---
def get_processed_app_data():
    """
    Main function to get the processed application data. Uses cached raw data.
    Ensures final dict has JSON-serializable types.
    """
    try:
        cached = load_and_cache_data()
        network_df = cached.get('network', pd.DataFrame())
        expenses_df = cached.get('expenses', pd.DataFrame())
        known_apps_db = cached.get('known_apps', pd.DataFrame())

        # Check if essential DataFrames are usable
        if network_df.empty:
            print("Warning: Network log data is empty.")
            return [] # Return empty if no network data

        discovered_apps = discover_applications(network_df)
        processed_apps = calculate_risk_and_status(discovered_apps, known_apps_db, expenses_df)
        return processed_apps
    except Exception as e:
        print(f"FATAL Error during application data processing: {e}\n{traceback.format_exc()}")
        return [] # Return empty list on major error

# --- Discovery Logic ---
def discover_applications(network_df):
    """Initial discovery based ONLY on network logs. Ensures standard types."""
    discovered = {}
    required_cols = ['destination_domain', 'user_id', 'timestamp', 'data_uploaded_mb', 'data_downloaded_mb']

    # Basic checks upfront
    if network_df.empty or not all(col in network_df.columns for col in required_cols):
        print("Warning: Network log empty or missing required columns. Discovery cannot proceed fully.")
        missing = [col for col in required_cols if col not in network_df.columns]
        if missing: print(f"   Missing: {missing}")
        return [] # Cannot discover without essential columns

    try:
        grouped = network_df.groupby('destination_domain', dropna=False)
        for domain, group in grouped:
             if pd.isna(domain) or not isinstance(domain, str) or domain.strip() == '': # Skip invalid domains
                 continue
             domain = str(domain).strip() # Ensure clean string domain

             valid_timestamps = group['timestamp'].dropna()
             first_seen = valid_timestamps.min() if not valid_timestamps.empty else pd.NaT
             last_seen = valid_timestamps.max() if not valid_timestamps.empty else pd.NaT

             total_uploaded = safe_float(group['data_uploaded_mb'].sum())
             total_downloaded = safe_float(group['data_downloaded_mb'].sum())
             access_count = len(group) # Standard int

             # Get unique users, ensuring they are strings
             unique_users = list(group['user_id'].astype(str).unique())

             discovered[domain] = {
                 'id': domain,
                 'domain': domain,
                 'network_access_count': access_count,
                 'unique_users_network': unique_users,
                 'total_data_uploaded_mb': total_uploaded,
                 'total_data_downloaded_mb': total_downloaded,
                 'first_seen_network': first_seen.isoformat() if pd.notna(first_seen) else None,
                 'last_seen_network': last_seen.isoformat() if pd.notna(last_seen) else None,
                 'app_name': 'Unknown', 'category': 'Unknown', 'status': 'unknown',
                 'resolution_status': None, 'inherent_risk_score': 10,
                 'compliance_gdpr': None, 'compliance_hipaa': None, 'known_breach': None,
                 'expense_keywords': [], 'linked_expense_count': 0, 'linked_expense_total': 0.0,
                 'calculated_risk_score': 0, 'calculated_risk_level': 'High', 'risk_factors': []
             }
    except Exception as e:
         print(f"Error during application discovery grouping/iteration: {e}\n{traceback.format_exc()}")
         return list(discovered.values()) # Return what was discovered so far

    return list(discovered.values())

# --- Risk Calculation ---
def calculate_risk_and_status(discovered_apps, known_apps_db, expenses_df):
    """Calculates risk, status, links expenses. Ensures JSON serializable types."""
    processed_apps = []
    cfg = current_app.config
    if known_apps_db.empty:
         print("Warning: Known apps database is empty. Risk assessment may be inaccurate.")

    for app_dict in discovered_apps:
        domain = app_dict['domain']
        risk_score = 0
        risk_factors = []

        # --- Section 1: Enrich with Known Apps ---
        if not known_apps_db.empty and domain in known_apps_db.index:
            try:
                known_info = known_apps_db.loc[domain].to_dict()
                app_dict.update({
                    'app_name': str(known_info.get('app_name', app_dict['app_name'])),
                    'category': str(known_info.get('category', app_dict['category'])),
                    'status': str(known_info.get('status', app_dict['status'])),
                    'inherent_risk_score': safe_int(known_info.get('inherent_risk_score'), default=10),
                    # Pass value directly to safe_bool, which handles conversion
                    'compliance_gdpr': safe_bool(known_info.get('compliance_gdpr'), default=None),
                    'compliance_hipaa': safe_bool(known_info.get('compliance_hipaa'), default=None),
                    'known_breach': safe_bool(known_info.get('known_breach'), default=None),
                    'expense_keywords': [str(kw).strip() for kw in str(known_info.get('expense_keywords', '')).split(',') if str(kw).strip()]
                })
                # Get resolution status safely, ensuring None if missing/NA
                res_status = known_info.get('resolution_status')
                app_dict['resolution_status'] = str(res_status) if pd.notna(res_status) else None

            except Exception as e:
                 print(f"Error processing known_app data for domain '{domain}': {e}")
                 app_dict.update({'status':'unknown', 'inherent_risk_score': 10, 'resolution_status':None}) # Reset relevant fields
                 risk_factors.append(f"Error processing Known Apps DB entry: {e}")
        else: # Domain not found
            app_dict.update({'status':'unknown', 'inherent_risk_score': 10, 'resolution_status':None})
            risk_factors.append("Application domain not found in known database")

        # --- Section 1b: Handle Resolution Status ---
        current_resolution = app_dict['resolution_status']
        if current_resolution == 'FalsePositive':
            app_dict.update({
                'status': cfg.get('IRRELEVANT_STATUS', 'irrelevant'),
                'calculated_risk_level': 'Info',
                'calculated_risk_score': 0,
                'risk_factors': ["Marked as False Positive by Admin."] # Overwrite
            })
            processed_apps.append(app_dict)
            continue # Skip remaining risk calc
        elif current_resolution == 'Sanctioned':
            app_dict['status'] = 'sanctioned'
            risk_factors.append("Manually sanctioned by Admin.")

        # --- Section 1c: Skip Irrelevant ---
        if app_dict['status'] == cfg.get('IRRELEVANT_STATUS', 'irrelevant'):
            app_dict.update({
                'calculated_risk_score': 1,
                'calculated_risk_level': 'Info',
                'risk_factors': ["Marked as irrelevant traffic (e.g., blog, news)."]
            })
            processed_apps.append(app_dict)
            continue

        # --- Section 2: Calculate Risk Score ---
        try: # Wrap calculation in try/except for robustness
            # Inherent Risk
            inherent_score = app_dict.get('inherent_risk_score', 10) # Safe get
            inherent_multiplier = cfg.get('RISK_POINTS', {}).get('inherent_risk_multiplier', 5)
            base_score = safe_int(inherent_score) * safe_int(inherent_multiplier)
            risk_score += base_score
            risk_factors.append(f"Inherent risk score: {inherent_score}/10 ({base_score} pts)")

            # User Count Risk
            user_count = len(app_dict.get('unique_users_network', [])) # Safe get list
            user_thresholds = cfg.get('USER_COUNT_THRESHOLDS', {'high': 10, 'medium': 3})
            user_points = cfg.get('RISK_POINTS', {})
            if user_count > user_thresholds.get('high', 10):
                pts = safe_int(user_points.get('user_count_high', 20))
                risk_score += pts
                risk_factors.append(f"High user count ({user_count}) (+{pts} pts)")
            elif user_count > user_thresholds.get('medium', 3):
                pts = safe_int(user_points.get('user_count_medium', 10))
                risk_score += pts
                risk_factors.append(f"Moderate user count ({user_count}) (+{pts} pts)")

            # Access Count Risk
            access_count = app_dict.get('network_access_count', 0) # Safe get
            access_threshold = cfg.get('ACCESS_COUNT_THRESHOLD_HIGH', 50)
            if access_count > access_threshold:
                pts = safe_int(user_points.get('access_count_high', 10))
                risk_score += pts
                risk_factors.append(f"High access count ({access_count}) (+{pts} pts)")

            # Data Upload Risk
            upload_mb = app_dict.get('total_data_uploaded_mb', 0.0) # Safe get
            upload_thresholds = cfg.get('UPLOAD_MB_THRESHOLDS', {'high': 1000, 'medium': 100})
            if upload_mb > upload_thresholds.get('high', 1000):
                pts = safe_int(user_points.get('upload_mb_high', 30))
                risk_score += pts
                risk_factors.append(f"Very High data upload ({upload_mb:.1f} MB) (+{pts} pts)")
            elif upload_mb > upload_thresholds.get('medium', 100):
                pts = safe_int(user_points.get('upload_mb_medium', 15))
                risk_score += pts
                risk_factors.append(f"High data upload ({upload_mb:.1f} MB) (+{pts} pts)")

            # Compliance/Breach Risk (only if effectively shadow/unapproved)
            is_effectively_shadow = (app_dict.get('status') in cfg.get('SHADOW_STATUSES',[])) or \
                                     (app_dict.get('status') == 'conditionally_approved' and current_resolution != 'Sanctioned')

            if is_effectively_shadow:
                if app_dict.get('compliance_gdpr') == False:
                    pts = safe_int(user_points.get('missing_gdpr_penalty', 10))
                    risk_score += pts
                    risk_factors.append(f"Lacks GDPR compliance (+{pts} pts)")
                if app_dict.get('known_breach') == True:
                    pts = safe_int(user_points.get('known_breach_penalty', 15))
                    risk_score += pts
                    risk_factors.append(f"Vendor has known historical breaches (+{pts} pts)")

            # --- Section 3: Link Expenses ---
            linked_count = 0
            linked_total = 0.0
            keywords = app_dict.get('expense_keywords', [])
            if keywords and not expenses_df.empty and 'vendor_name' in expenses_df.columns and 'amount' in expenses_df.columns:
                pattern = r'\b(?:' + '|'.join(map(re.escape, keywords)) + r')\b' # Escape special chars
                try:
                    matched_expenses = expenses_df[
                        expenses_df['vendor_name'].astype(str).str.contains(pattern, case=False, na=False, regex=True)
                    ]
                    if not matched_expenses.empty:
                        linked_count = len(matched_expenses)
                        linked_total = safe_float(matched_expenses['amount'].sum())
                except Exception as e:
                    print(f"Regex error linking expenses for {domain} with pattern '{pattern}': {e}")

            app_dict['linked_expense_count'] = linked_count
            app_dict['linked_expense_total'] = linked_total

            # Spend Penalty (if Shadow IT)
            if linked_total > 0 and (app_dict.get('status') in cfg.get('SHADOW_STATUSES',[])) and current_resolution != 'Sanctioned':
                pts = safe_int(user_points.get('unapproved_spend_penalty', 25))
                risk_score += pts
                risk_factors.append(f"Detected Shadow IT spend: ${linked_total:.2f} (+{pts} pts)")

            # --- Section 4: Finalize Risk Level ---
            final_risk_score = max(0, risk_score) # Ensure non-negative
            app_dict['calculated_risk_score'] = safe_int(final_risk_score)
            app_dict['risk_factors'] = risk_factors

            risk_thresholds = cfg.get('RISK_THRESHOLDS', {'high': 75, 'medium': 40})
            calculated_level = 'Low'
            if app_dict.get('status') in cfg.get('SANCTIONED_STATUSES', []) and current_resolution == 'Sanctioned':
                calculated_level = 'Low'
            elif final_risk_score >= risk_thresholds.get('high', 75):
                calculated_level = 'High'
            elif final_risk_score >= risk_thresholds.get('medium', 40):
                calculated_level = 'Medium'

            # Boost if unknown and not already high/resolved FP
            if app_dict.get('status') == 'unknown' and calculated_level != 'High' and current_resolution != 'FalsePositive':
                calculated_level = 'Medium'
                if not any("Risk boosted" in factor for factor in app_dict['risk_factors']):
                     app_dict['risk_factors'].append("Risk boosted: Application status is Unknown.")

            app_dict['calculated_risk_level'] = calculated_level

        except Exception as e:
            print(f"Error calculating risk for {domain}: {e}\n{traceback.format_exc()}")
            app_dict['calculated_risk_score'] = -1 # Indicate error state
            app_dict['calculated_risk_level'] = "Error"
            app_dict['risk_factors'] = [f"Error during risk calculation: {e}"]


        processed_apps.append(app_dict)

    return processed_apps


# --- Analysis Functions for APIs ---

def get_summary_stats(processed_apps):
    """Calculates KPI stats based on processed app data. Returns standard types."""
    cfg = current_app.config
    stats = defaultdict(int) # Values will be standard ints
    total_spend = 0.0 # Standard float

    app_count_total = 0 # Count relevant apps
    for app in processed_apps:
         # Ignore explicitly irrelevant/FP for *risk* and *shadow* counts
         # Use .get with default values for safety
        status = app.get('status', 'unknown')
        resolution = app.get('resolution_status')
        risk_level = app.get('calculated_risk_level', 'Low') # Handle error state or missing level

        if status == cfg.get('IRRELEVANT_STATUS', 'irrelevant') or resolution == 'FalsePositive':
            stats['irrelevant_or_fp'] += 1
        else:
             app_count_total += 1 # Count relevant apps
             if status in cfg.get('SHADOW_STATUSES', []) and resolution != 'Sanctioned':
                stats['shadow_count'] += 1

             if risk_level == 'High':
                stats['high_risk'] += 1
             elif risk_level == 'Medium':
                 stats['medium_risk'] += 1
             elif risk_level == 'Low':
                 stats['low_risk'] += 1
             # Ignore 'Error' or 'Info' in risk counts maybe? Or add categories.

             # Sum linked spend only for non-FP/Irrelevant
             total_spend += app.get('linked_expense_total', 0.0)

    stats['total_detected'] = app_count_total # Assign count of relevant apps
    stats['linked_spend'] = round(total_spend, 2) # Standard float

    # Convert defaultdict to dict with standard ints
    final_stats = {'linked_spend': stats['linked_spend']}
    for k, v in stats.items():
         if k != 'linked_spend':
             final_stats[k] = int(v)

    return final_stats


def get_behavior_insights(processed_apps):
    """Generates user behavior insights. Returns standard types."""
    cfg = current_app.config
    insights = {'top_shadow_users_by_app_count': [], 'top_shadow_users_by_access_count': [], 'apps_with_high_data_upload': []}

    try:
        shadow_status_list = cfg.get('SHADOW_STATUSES', [])
        shadow_apps_data = [
            app for app in processed_apps
            if app.get('status') in shadow_status_list
            and app.get('resolution_status') not in ['Sanctioned', 'FalsePositive']
        ]
        if not shadow_apps_data: return insights

        cached = load_and_cache_data()
        network_df = cached.get('network', pd.DataFrame())
        if network_df.empty or 'destination_domain' not in network_df.columns or 'user_id' not in network_df.columns:
            print("Warning: Network data insufficient for behavior insights.")
            return insights

        shadow_domains = {app['domain'] for app in shadow_apps_data}
        shadow_traffic = network_df[network_df['destination_domain'].isin(shadow_domains)].copy() # Use .copy()

        # --- Analysis on shadow_traffic ---
        if not shadow_traffic.empty:
            # Use cfg.get with default for limit
            limit = cfg.get('BEHAVIOR_INSIGHTS_LIMIT', 5)

            # Grouping can fail if user_id has NA/mixed types - coerce to string first
            shadow_traffic['user_id'] = shadow_traffic['user_id'].astype(str)

            # Top users by distinct app count
            user_app_counts = shadow_traffic.groupby('user_id')['destination_domain'].nunique().sort_values(ascending=False)
            insights['top_shadow_users_by_app_count'] = [(str(user), int(count)) for user, count in user_app_counts.head(limit).items()]

            # Top users by access count
            user_access_counts = shadow_traffic['user_id'].value_counts().sort_values(ascending=False)
            insights['top_shadow_users_by_access_count'] = [(str(user), int(count)) for user, count in user_access_counts.head(limit).items()]

        # Apps with high data upload
        upload_thresholds = cfg.get('UPLOAD_MB_THRESHOLDS', {})
        high_upload_threshold = safe_float(upload_thresholds.get('medium', 100.0))
        high_upload_apps = sorted(
            [app for app in shadow_apps_data if safe_float(app.get('total_data_uploaded_mb', 0.0)) > high_upload_threshold],
            key=lambda x: safe_float(x.get('total_data_uploaded_mb', 0.0)), reverse=True
        )
        insights['apps_with_high_data_upload'] = [{
            'domain': str(app.get('domain', 'N/A')),
            'app_name': str(app.get('app_name', 'Unknown')),
            'uploaded_mb': safe_float(app.get('total_data_uploaded_mb', 0.0))
        } for app in high_upload_apps[:limit]]

    except Exception as e:
         print(f"Error during behavior insights calculation: {e}\n{traceback.format_exc()}")
         # Return empty insights on error

    return insights


def get_spend_by_category(processed_apps):
    """Aggregates linked spend by application category. Returns standard types."""
    cfg = current_app.config
    spend_by_cat = defaultdict(float)
    irrelevant_status = cfg.get('IRRELEVANT_STATUS', 'irrelevant')
    for app in processed_apps:
        if app.get('status') != irrelevant_status and app.get('resolution_status') != 'FalsePositive':
            category = str(app.get('category', 'Unknown'))
            spend = safe_float(app.get('linked_expense_total', 0.0))
            if spend > 0: spend_by_cat[category] += spend

    sorted_data = sorted(spend_by_cat.items(), key=lambda item: item[1], reverse=True)
    labels = [str(item[0]) for item in sorted_data]
    values = [float(round(item[1], 2)) for item in sorted_data]
    return {'labels': labels, 'values': values}


def get_usage_trends(processed_apps):
    """Simulates daily access trend data. Returns standard types."""
    cfg = current_app.config
    trend_data = defaultdict(int)
    today = datetime.date.today()
    trend_days = cfg.get('TREND_SIMULATION_DAYS', 7)
    if trend_days <= 0: trend_days = 7 # Basic sanity check

    date_range = [(today - datetime.timedelta(days=i)).isoformat() for i in range(trend_days - 1, -1, -1)]

    import random
    total_apps = len(processed_apps) if processed_apps else 1 # Avoid division by zero if no apps
    base_count = max(1, total_apps) * 5 # Ensure base is at least 5
    for day_iso in date_range:
        daily_accesses = base_count + random.randint(-total_apps // 2, total_apps) # Fluctuate less wildly maybe
        trend_data[day_iso] = max(0, daily_accesses)

    labels = list(trend_data.keys())
    values = list(trend_data.values())
    return {'labels': labels, 'values': values}


# --- Simulation of updating data (for workflow) ---
def update_app_resolution_status(app_id, new_status):
    """Simulates updating the resolution status in known_apps CSV."""
    print(f"Simulating update for app '{app_id}' to status '{new_status}'")
    cfg = current_app.config
    file_path = cfg.get('KNOWN_APPS_FILE')
    if not file_path or not os.path.exists(file_path):
        print(f"      > Error: Known apps file path missing/invalid: {file_path}")
        return False
    try:
        # Use na_filter=False only if you are absolutely sure blanks != NaN
        df = pd.read_csv(file_path, keep_default_na=False, na_values=['']) # Treat blanks as NaN
        if 'domain' not in df.columns:
            print(f"      > Error: 'domain' column missing in {file_path}")
            return False
        if 'resolution_status' not in df.columns:
            df['resolution_status'] = pd.Series(dtype='object')

        # Ensure domain column is suitable type for comparison (usually string)
        df['domain'] = df['domain'].astype(str)
        app_id = str(app_id) # Ensure ID is string for comparison

        if app_id in df['domain'].values:
            status_to_save = new_status if new_status is not None else np.nan # Use NaN for DB/Pandas representation of NULL
            df.loc[df['domain'] == app_id, 'resolution_status'] = status_to_save
            # Write back NaN as empty string
            df.to_csv(file_path, index=False, na_rep='')
            print(f"      > CSV Updated for {app_id}")
            global _cached_data # Invalidate cache
            _cached_data = None
            return True
        else:
            print(f"      > Error: App ID {app_id} not found in {file_path} for update.")
            return False
    except Exception as e:
        print(f"      > Error reading/writing CSV file ({file_path}): {e}\n{traceback.format_exc()}")
        return False

# Need re module for regex compile in risk calculation expense linking
import re