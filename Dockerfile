# Use an official Python runtime as the base image
FROM python:slim

# Set the working directory in the container
WORKDIR /app

# Install build dependencies
RUN apt update -y && apt upgrade -y && apt install -y build-essential

# Copy the requirements.txt file to the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its dependencies
RUN python -m playwright install-deps
RUN python -m playwright install

# Copy the entire project directory to the container
COPY . .

# Expose the port your Flask application is running on
EXPOSE 5001

# Define the command to run your Flask application
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5001"]
