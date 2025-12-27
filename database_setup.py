import os
import psycopg2
import logging
import sys

# Make sure this import is included at the top

# configure basic logging for console output during setup
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


# Function to get a database connection object using environment variable
def get_db_connection():
    """
    Connects to the PostgreSQL database using the DATABASE_URL environment variable
    provided by Render.
    """
    # Attempt to get the DATABASE_URL environment variable
    DATABASE_URL = os.environ.get("DATABASE_URL")

    if not DATABASE_URL:
        Logger.error("Error: DATABASE_URL not set. Cannot connect to database.")
        return None

    try:
        # Establish the connection using the URL
        conn = psycopg2.connect(DATABASE_URL)
        Logger.info("Database connection successful.")
        return conn
    except Exception as e:
        Logger.error(f"Database connection failed: {e}")
        return None

# --- End of New/Updated Database Connection Logic ---

# Note: If this file runs SQL commands directly, you must ensure they
# use the 'get_db_connection()' function now. For example:

# if __name__ == "__main__":
#     conn = get_db_connection()
#     if conn:
#         print("Connection established successfully in setup script.")
#         conn.close()
