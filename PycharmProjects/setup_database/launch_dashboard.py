import os
import subprocess
import sys

# Get the absolute path to the directory this script is running from
script_dir = os.path.dirname(os.path.abspath(__file__))
# !!! Corrected this line to use 'dashboard_app.py' (with an underscore) !!!
dashboard_script = os.path.join(script_dir, 'dashboard_app.py')

# Ensure we use the same Python interpreter currently running this script
interpreter = sys.executable

print(f"Attempting to run: {dashboard_script} using {interpreter}")

# Use subprocess to run the dashboard script correctly
try:
    # We use sys.executable to ensure the correct python env is used
    subprocess.run([interpreter, dashboard_script], check=True)
except subprocess.CalledProcessError as e:
    print(f"Dashboard script failed with return code {e.returncode}")
except FileNotFoundError:
    print(f"Error: Could not find the dashboard script at {dashboard_script}")