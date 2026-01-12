FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
#ENV USERNAME=

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg

COPY ./requirements.txt /app/
RUN pip install --requirement /app/requirements.txt
COPY ./showsaver /app

CMD ["python", "main.py"]