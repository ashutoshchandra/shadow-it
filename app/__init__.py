# app/__init__.py
from flask import Flask
import os # Needed by routes now if it wasn't imported already there

def create_app(app_config=None):
    # Changed base path calculation slightly for robustness if instance folder needed relative paths
    app = Flask(__name__, instance_relative_config=False) # False if config is in project root, True if in instance/

    # Load configuration
    if app_config:
        # If config object is passed directly (like from run.py)
         app.config.from_object(app_config)
         # print("Config loaded from object.") # Debug
    else:
        # Fallback or alternative way to load config if needed
        # Assumes config.py is in the parent directory of 'app' folder
         config_path = os.path.join(os.path.dirname(app.root_path), 'config.py')
         if os.path.exists(config_path):
             app.config.from_pyfile(config_path, silent=False)
             # print(f"Config loaded from path: {config_path}") # Debug
         else:
             print(f"Warning: Config file not found at {config_path}")

    # Make sure the instance folder exists (useful for uploads, session files etc. later)
    try:
         os.makedirs(app.instance_path)
    except OSError:
        pass

    # Register Blueprints within the app context if needed, or just import and register
    with app.app_context(): # Ensure app context for imports relying on current_app if any were added
        from . import routes
        app.register_blueprint(routes.bp)

        # Could Initialize extensions (DB, Login Manager etc.) here
        # Example: db.init_app(app)

        print("Flask App Created with Config Keys:") # Print keys to confirm loading
        print(list(app.config.keys())) # Show what config keys were actually loaded

    return app