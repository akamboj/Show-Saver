FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
#ENV USERNAME=

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

COPY ./requirements.txt /app/
RUN pip install --requirement /app/requirements.txt
COPY ./showsaver /app

VOLUME /config /tvshows /tmp

CMD ["python", "main.py"]
