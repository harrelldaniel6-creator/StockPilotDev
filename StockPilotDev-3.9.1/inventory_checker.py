import requests
import sqlite3
import pandas as pd
from requests.auth import HTTPBasicAuth
from datetime import datetime

# --- CONFIGURATION ---
SHOPIFY_SHOP_URL = "stockpilotdev.myshopify.com"
SHOPIFY_API_KEY = "f2b14664e55eba76e5d2aefae8903b21"
SHOPIFY_API_PASSWORD = "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"
INVENTORY_THRESHOLD = 10  # Set your minimum inventory threshold here
DB_PATH = 'stockpilot.db'


def fetch_all_products_with_inventory():
    print("Fetching product and inventory data from Shopify...")
    products_url = f"https://{SHOPIFY_SHOP_URL}/admin/api/2024-04/products.json"
    auth = HTTPBasicAuth(SHOPIFY_API_KEY, SHOPIFY_API_PASSWORD)
    products_list = []

    # Simple pagination loop (handles up to ~1000 products)
    while products_url:
        response = requests.get(products_url, auth=auth, timeout=10)
        response.raise_for_status()
        data = response.json()
        products_list.extend(data.get('products', []))
        # Get next page URL from headers if available
        products_url = None
        link_header = response.headers.get('Link')
        if link_header:
            for link in link_header.split(','):
                if 'rel="next"' in link:
                    products_url = link.split(';')[0].strip('<> ')
                    break

    variants_data = []
    for product in products_list:
        for variant in product.get('variants', []):
            variants_data.append({
                'product_name': product.get('title'),
                'variant_title': variant.get('title'),
                'inventory_quantity': variant.get('inventory_quantity'),
                'variant_id': variant.get('id')
            })
    return pd.DataFrame(variants_data)


def generate_reorder_alerts(df_inventory, threshold):
    alerts = df_inventory[df_inventory['inventory_quantity'] <= threshold]
    alerts['alert_date'] = datetime.now().isoformat()
    return alerts[['product_name', 'variant_title', 'inventory_quantity', 'alert_date']]


def save_alerts_to_db(df_alerts):
    print(f"Saving {len(df_alerts)} alerts to database...")
    conn = sqlite3.connect(DB_PATH)
    # This replaces old alerts entirely every time the script runs
    df_alerts.to_sql('reorder_alerts', conn, if_exists='replace', index=False)
    conn.close()
    print("Alerts saved successfully.")


if __name__ == "__main__":
    try:
        inventory_df = fetch_all_products_with_inventory()
        if not inventory_df.empty:
            alerts_df = generate_reorder_alerts(inventory_df, INVENTORY_THRESHOLD)
            save_alerts_to_db(alerts_df)
            print(f"Inventory check complete. {len(alerts_df)} items are below threshold of {INVENTORY_THRESHOLD}.")
        else:
            print("No inventory data fetched. Check Shopify connection.")
    except requests.exceptions.RequestException as e:
        print(f"Network error during Shopify API call: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")