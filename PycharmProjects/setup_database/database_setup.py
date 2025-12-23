import sqlite3
import logging
import sys

# Configure basic logging for console output during setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = 'stockpilot.db'


def setup_database_schema():
    """
    Creates the necessary tables for the StockPilotDev project if they do not exist.
    """
    # SQL statement to create the stocks table
    create_stocks_table_sql = """
                              CREATE TABLE IF NOT EXISTS stocks \
                              ( \
                                  id \
                                  INTEGER \
                                  PRIMARY \
                                  KEY \
                                  AUTOINCREMENT, \
                                  symbol \
                                  TEXT \
                                  NOT \
                                  NULL \
                                  UNIQUE, \
                                  company_name \
                                  TEXT \
                                  NOT \
                                  NULL, \
                                  exchange \
                                  TEXT \
                                  NOT \
                                  NULL, \
                                  created_at \
                                  TEXT \
                                  NOT \
                                  NULL, \
                                  updated_at \
                                  TEXT \
                                  NOT \
                                  NULL
                              ); \
                              """

    # SQL statement to create the prices table
    create_prices_table_sql = """
                              CREATE TABLE IF NOT EXISTS prices \
                              ( \
                                  id \
                                  INTEGER \
                                  PRIMARY \
                                  KEY \
                                  AUTOINCREMENT, \
                                  stock_id \
                                  INTEGER \
                                  NOT \
                                  NULL, \
                                  date \
                                  TEXT \
                                  NOT \
                                  NULL, \
                                  open_price \
                                  REAL \
                                  NOT \
                                  NULL, \
                                  high_price \
                                  REAL \
                                  NOT \
                                  NULL, \
                                  low_price \
                                  REAL \
                                  NOT \
                                  NULL, \
                                  close_price \
                                  REAL \
                                  NOT \
                                  NULL, \
                                  volume \
                                  INTEGER \
                                  NOT \
                                  NULL, \
                                  FOREIGN \
                                  KEY \
                              ( \
                                  stock_id \
                              ) REFERENCES stocks \
                              ( \
                                  id \
                              )
                                  ); \
                              """

    try:
        # Use a context manager to handle the connection securely
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            logger.info("Database connection established.")

            # Create the stocks table
            cursor.execute(create_stocks_table_sql)
            logger.info("Table 'stocks' ensured to exist.")

            # Create the prices table
            cursor.execute(create_prices_table_sql)
            logger.info("Table 'prices' ensured to exist.")

            # Commit changes automatically with the 'with' statement
            logger.info("Database schema setup complete.")

    except sqlite3.Error as e:
        logger.error(f"A database error occurred: {e}")


if __name__ == '__main__':
    setup_database_schema()