FROM python:3.10

RUN ["mkdir", "-p", "/app"]

# Copy all files so this can work as a standalone container.
COPY . /app

WORKDIR /app

RUN ["pip", "install", "-r", "requirements.txt"]

CMD [ "python", "main.py" ]
