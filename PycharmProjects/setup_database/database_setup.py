import sqlite3
import logging
import sys
# Make sure this import is included at the top
import os

# Configure basic logging for console output during setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

Logger = logging.getLogger(__name__)

# --- Start of New/Updated Database Connection Logic ---

# 1. Dynamically find the directory where THIS script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Get the DB filename from Render's Environment Variable (default to 'stockpilot.db')
#    This matches the environment variable you will set in Render's dashboard.
DB_NAME = os.environ.get('DATABASE_NAME', 'stockpilot.db')

# 3. Create the full absolute path to the database within your project folder
DB_PATH = os.path.join(BASE_DIR, DB_NAME)


def get_db_connection():
    """Returns a connection to the SQLite database using the dynamic DB_PATH."""
    # This connects to the database file; it will be created if it doesn't exist
    conn = sqlite3.connect(DB_PATH)
    # Recommended: this allows you to access columns by name like row['id']
    conn.row_factory = sqlite3.Row
    return conn


# --- End of New/Updated Database Connection Logic ---


def setup_database_schema():
    """
    Example of how to use the new get_db_connection() function.
    Your original logic for creating tables goes here.
    """
    conn = get_db_connection()  # Use the new function here
    cursor = conn.cursor()

    # Example: Ensure 'stocks' table exists
    Logger.info("Database connection established.")
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS stocks
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY,
                       symbol
                       TEXT
                       NOT
                       NULL
                       UNIQUE
                   )
                   ''')
    Logger.info("Table 'stocks' ensured to exist.")

    # Example: Ensure 'prices' table exists
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS prices
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY,
                       stock_id
                       INTEGER,
                       date
                       TEXT
                       NOT
                       NULL,
                       price
                       REAL
                       NOT
                       NULL,
                       FOREIGN
                       KEY
                   (
                       stock_id
                   ) REFERENCES stocks
                   (
                       id
                   )
                       )
                   ''')
    Logger.info("Table 'prices' ensured to exist.")

    conn.commit()
    conn.close()
    Logger.info("Database schema setup complete.")


# When you run this file directly, it sets up the schema
if __name__ == "__main__":
    setup_database_schema()