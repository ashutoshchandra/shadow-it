# app/routes.py
from flask import Blueprint, render_template, jsonify, request, current_app
# Import specific functions needed
from .processing import (
    get_processed_app_data,
    get_summary_stats,
    get_behavior_insights,
    get_spend_by_category,
    get_usage_trends,
    update_app_resolution_status # For workflow simulation
)
import traceback
import os # Need os for the init.py modification below

bp = Blueprint('main', __name__)

# === Page Route ===

@bp.route('/')
@bp.route('/dashboard')
def dashboard():
    """Render the main dashboard page HTML structure."""
    # Explicitly get the needed config value
    try:
        upload_threshold_medium = current_app.config['UPLOAD_MB_THRESHOLDS']['medium']
    except KeyError:
        # Fallback if config isn't loaded correctly yet (shouldn't happen often)
        print("Warning: Config UPLOAD_MB_THRESHOLDS not found, using default.")
        upload_threshold_medium = 100 # Default value matching config.py

    # Pass the value to the template
    return render_template('dashboard.html',
                           upload_mb_threshold=upload_threshold_medium)


# === API Endpoints ===
# ... (rest of the API endpoints remain unchanged) ...

@bp.route('/api/summary_stats')
def api_summary_stats():
    """API endpoint to get summary KPI statistics."""
    try:
        apps = get_processed_app_data()
        stats = get_summary_stats(apps)
        return jsonify(stats)
    except Exception as e:
        print(f"Error in /api/summary_stats: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Could not calculate summary stats"}), 500

@bp.route('/api/apps')
def api_get_apps():
    """API endpoint to get the full list of processed applications."""
    try:
        apps = get_processed_app_data()
         # Maybe add filtering/pagination params here later: ?status=unknown&page=1
        return jsonify(apps)
    except Exception as e:
        print(f"Error in /api/apps: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "Could not retrieve application data"}), 500


@bp.route('/api/behavior_insights')
def api_behavior_insights():
     """API endpoint for user behavior data."""
     try:
        apps = get_processed_app_data()
        insights = get_behavior_insights(apps)
        return jsonify(insights)
     except Exception as e:
         print(f"Error in /api/behavior_insights: {e}\n{traceback.format_exc()}")
         return jsonify({"error": "Could not calculate behavior insights"}), 500


@bp.route('/api/chart_data/risk_distribution')
def api_chart_risk_distribution():
    """API endpoint for risk distribution chart data."""
    try:
        apps = get_processed_app_data()
        stats = get_summary_stats(apps) # Contains counts needed
        cfg = current_app.config
        # Ensure we account for irrelevant/FP if needed or handle appropriately
        # Simplified: directly use risk counts
        data = {
             'labels': ['High', 'Medium', 'Low', 'Info/FP'], # Combined Info/FP for simplicity
             'values': [
                 stats.get('high_risk', 0),
                 stats.get('medium_risk', 0),
                 stats.get('low_risk', 0),
                 stats.get('irrelevant_or_fp', 0) # Get the irrelevant/FP count
                 # Ensure the sum matches total_detected or handle discrepancies
             ]
        }
        return jsonify(data)
    except Exception as e:
         print(f"Error in /api/chart_data/risk_distribution: {e}\n{traceback.format_exc()}")
         return jsonify({"error": "Could not generate risk distribution data"}), 500

@bp.route('/api/chart_data/spend_by_category')
def api_chart_spend_category():
    """API endpoint for spend by category chart data."""
    try:
         apps = get_processed_app_data()
         spend_data = get_spend_by_category(apps)
         return jsonify(spend_data)
    except Exception as e:
         print(f"Error in /api/chart_data/spend_by_category: {e}\n{traceback.format_exc()}")
         return jsonify({"error": "Could not generate spend by category data"}), 500

@bp.route('/api/chart_data/usage_trend')
def api_chart_usage_trend():
    """API endpoint for (simulated) usage trend data."""
    try:
         apps = get_processed_app_data()
         trend_data = get_usage_trends(apps) # Calls the simulation
         return jsonify(trend_data)
    except Exception as e:
         print(f"Error in /api/chart_data/usage_trend: {e}\n{traceback.format_exc()}")
         return jsonify({"error": "Could not generate usage trend data"}), 500

# === Workflow Simulation API ===
@bp.route('/api/apps/<app_id>/resolve', methods=['POST'])
def api_resolve_app(app_id):
    """
    Simulates updating the resolution status of an app.
    Expects JSON payload: {"resolution_status": "Sanctioned" | "Blocked" | "Investigating" | "FalsePositive"}
    """
    data = request.get_json()
    new_status = data.get('resolution_status')

    # Define valid statuses including None to clear it
    valid_statuses = ['Sanctioned', 'Blocked', 'Investigating', 'FalsePositive', None]

    # Check if the provided status is valid OR explicitly None
    is_valid = False
    if new_status is None:
        is_valid = True
    elif isinstance(new_status, str) and new_status in valid_statuses:
        is_valid = True
    # Additional check if the key exists but value is not in list (and not None)
    elif 'resolution_status' in data and new_status not in valid_statuses:
         is_valid = False

    if not is_valid:
        print(f"Invalid status provided: {new_status}")
        return jsonify({"error": f"Invalid resolution_status. Must be one of {valid_statuses} or explicitly null."}), 400

    if not app_id:
         return jsonify({"error": "Missing app_id"}), 400

    # Call the processing function to simulate DB update
    success = update_app_resolution_status(app_id, new_status)

    if success:
         # Return the updated app data (or just success)
        # For simplicity, return success. Frontend should refetch to see change.
         return jsonify({"success": True, "message": f"App '{app_id}' status updated to '{new_status if new_status is not None else 'None'}'"})
    else:
         return jsonify({"error": f"Failed to update status for app '{app_id}'"}), 500