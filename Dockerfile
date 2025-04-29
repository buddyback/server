FROM python:3.12

# Set the working directory in the container to /app
WORKDIR /app

# Copy requirements file first to leverage Docker cache
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Add the rest of the current directory contents into the container at /app
COPY . /app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the command to start uWSGI
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]