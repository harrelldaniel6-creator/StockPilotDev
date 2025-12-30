@echo off
echo Running Inventory Checker...
"C:\StockPilotSafe\.venv\Scripts\python.exe" "C:\StockPilotSafe\inventory_checker.py"

echo Running Dashboard Generator...
"C:\StockPilotSafe\.venv\Scripts\python.exe" "C:\StockPilotSafe\StockPilotDev_Dashboard.py"

echo Automation complete.
pause