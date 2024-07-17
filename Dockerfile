# Use an official Python runtime as the base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install build dependencies
RUN apt update && apt install -y build-essential

# Copy the requirements.txt file to the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt


# Copy the entire project directory to the container
COPY . .

# Expose the port your Flask application is running on
EXPOSE 5001

# Define the command to run your Flask application
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5001"]
