FROM python:3.9-slim

# Working directory
WORKDIR /app

# Copy files
ADD smartlist /app/smartlist
ADD static /app/static
ADD templates /app/templates
ADD requirements.txt /app/requirements.txt
ADD run.py /app/run.py

# Install dependencies
RUN apt-get update
RUN apt-get install -y gcc libffi-dev libssl-dev python-dev
RUN pip install --upgrade pip
RUN pip install --extra-index-url https://www.piwheels.org/simple -r requirements.txt

# Run application when container launches
CMD ["python", "run.py"]
