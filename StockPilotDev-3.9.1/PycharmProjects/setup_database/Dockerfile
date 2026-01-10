# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any specified packages (none listed for now, but good practice)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Command to run the application when the container starts
# This will execute your script to generate the report
CMD ["python", "dashboard_app.py"]
docker build -t stockpilot-app .

docker run stockpilot-app