import os
import subprocess
import time
import sys


def run_script(script_name):
    """Helper function to run other python scripts using the current interpreter."""
    print(f"\n--- Running {script_name} ---")
    interpreter = sys.executable
    try:
        # Use subprocess to run the other scripts
        subprocess.run([interpreter, script_name], check=True, cwd=os.getcwd())
        print(f"--- Finished {script_name} Successfully ---")
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Could not find {script_name}. Ensure the file exists.")
        sys.exit(1)


if __name__ == "__main__":
    print("--- Starting Full Stock Analysis Workflow ---")

    # Step 1: Fetch the data
    run_script("fetch_data.py")

    # Step 2: Generate the report (uses the new data from Step 1)
    run_script("generate_report.py")

    # Step 3: Start the dashboard (will use the new data from Step 1)
    print("\n--- Starting Dashboard Server (Press Ctrl+C to stop) ---")
    print("Dashboard available at: 127.0.0.1")

    # We run the dashboard in a loop or in the foreground as a final step
    # Subprocess run without 'check=True' so it stays running
    try:
        subprocess.run([sys.executable, "dashboard_app.py"], cwd=os.getcwd())
    except KeyboardInterrupt:
        print("\nDashboard stopped by user.")
    except Exception as e:
        print(f"An error occurred with the dashboard: {e}")

    print("--- Workflow Finished ---")