from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

# Connect to the database
conn = sqlite3.connect('applications.db')
cursor = conn.cursor()

# Create a table to store application data
cursor.execute('''
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        description TEXT
    )
''')

# Route to display the dashboard
@app.route('/')
def dashboard():
    # Fetch application data from the database
    cursor.execute('SELECT * FROM applications')
    applications = cursor.fetchall()

    # Render the dashboard template with the application data
    return render_template('dashboard.html', applications=applications)

if __name__ == '__main__':
    app.run()