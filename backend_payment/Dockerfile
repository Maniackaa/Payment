FROM python:3.10
WORKDIR /app
RUN apt-get update && apt-get install libpq-dev libgl1
RUN pip install --upgrade pip
RUN pip install gunicorn==20.1.0
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN ["chmod", "u+x", "/app/entrypoint.sh"]
#ENTRYPOINT ["/app/entrypoint.sh"]
