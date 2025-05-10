# run.py
from app import create_app
import config # Import config to ensure it's loaded/accessible if needed globally

app = create_app(config) # Pass config to the factory

if __name__ == '__main__':
    app.run(debug=True, port=5006)