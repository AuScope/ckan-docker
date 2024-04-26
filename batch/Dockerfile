# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container to /fastapi
WORKDIR /app

# Install dependencies:
# This will copy your requirements and install them to avoid cache invalidation
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the local code to the container
COPY . /app

# Make port 80 available to the world outside this container
EXPOSE 80

# Define the command to run your application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]
