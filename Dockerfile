FROM python:3.12

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 libx264-dev -y

# Upgrade pip
# RUN pip install --upgrade pip

# Install faiss-cpu
#RUN #pip install faiss-cpu

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the command to start uWSGI
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]