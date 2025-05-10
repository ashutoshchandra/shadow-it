# config.py
import os

# --- Data File Paths ---
# Determine base directory assuming run.py is in the project root
# Adjust if your execution context is different
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

NETWORK_LOG_FILE = os.path.join(DATA_DIR, 'network_log_enhanced.csv')
KNOWN_APPS_FILE = os.path.join(DATA_DIR, 'known_apps_enhanced.csv')
EXPENSES_FILE = os.path.join(DATA_DIR, 'expenses.csv')

# --- Risk Scoring Configuration ---
RISK_THRESHOLDS = {
    'high': 75,
    'medium': 40,
    'low': 0
}

# Points assigned for various risk factors (adjust weights as needed)
RISK_POINTS = {
    'inherent_risk_multiplier': 5,
    'user_count_medium': 10,      # Points if user count > 3
    'user_count_high': 20,        # Points if user count > 10
    'access_count_high': 10,      # Points if access count > 50
    'upload_mb_medium': 15,       # Points if upload > 100 MB
    'upload_mb_high': 30,         # Points if upload > 1000 MB
    'missing_gdpr_penalty': 10,
    'known_breach_penalty': 15,
    'unapproved_spend_penalty': 25,
}

# User count thresholds corresponding to medium/high points
USER_COUNT_THRESHOLDS = {
    'medium': 3,
    'high': 10
}
ACCESS_COUNT_THRESHOLD_HIGH = 50
UPLOAD_MB_THRESHOLDS = {
    'medium': 100,
    'high': 1000
}

# --- App Status Definitions ---
# Define which statuses are considered "Shadow IT" for counts/filtering
SHADOW_STATUSES = ['unknown', 'unsanctioned']
SANCTIONED_STATUSES = ['sanctioned', 'conditionally_approved']
IRRELEVANT_STATUS = 'irrelevant'


# --- Trend Analysis ---
# Number of days to simulate for trend chart
TREND_SIMULATION_DAYS = 7

# --- Frontend Configuration ---
# Number of top users/apps to show in insights
BEHAVIOR_INSIGHTS_LIMIT = 5