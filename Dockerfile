FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
ENV USERNAME=

WORKDIR /app

COPY ./requirements.txt /app/
RUN pip install --requirement /app/requirements.txt
COPY . /app

CMD ["python", "main.py"]