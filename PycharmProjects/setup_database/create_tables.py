import os
import psycopg2
import sys

def create_tables():
    """Connects to the PostgreSQL DB using the environment variable and creates the tables."""
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable not set.")
        sys.exit(1) # Exit if no URL is found

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # NOTE: If your table name has a space, you MUST use double quotes around it
        create_table_query = """
        CREATE TABLE IF NOT EXISTS "stock_data" (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL,
            price NUMERIC(10, 2) NOT NULL,
            timestamp TIMESTAMP NOT NULL
            -- Add the rest of your column definitions here if you have more columns
        );
        """
        cur.execute(create_table_query)
        conn.commit()
        print("Table 'stock_data' ensured to exist.")
        cur.close()
        conn.close()

    except Exception as e:
        print(f"An error occurred during table creation: {e}")
        sys.exit(1) # Exit with an error code if creation fails

if __name__ == "__main__":
    create_tables()