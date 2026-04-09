import os
import sqlite3

def repair():
    db_path = r'C:\Users\blemley\AppData\Local\DenierAI\users.db'
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Reset stuck jobs
        c.execute("UPDATE jobs SET status='failed' WHERE status='processing' OR status='pending'")
        count = c.rowcount
        conn.commit()
        
        # Also clean up browse requests if any are pending
        c.execute("DELETE FROM browse_requests")
        
        print(f"Success: Reset {count} stuck jobs and cleared browse queue.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    repair()
