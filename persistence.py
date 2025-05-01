import sqlite3

def save_to_db(user, domain):
    conn = sqlite3.connect('shadow_it.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage (user TEXT, domain TEXT)''')
    c.execute('INSERT INTO usage (user, domain) VALUES (?, ?)', (user, domain))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    save_to_db("user1@corp.com", "slack.com")
