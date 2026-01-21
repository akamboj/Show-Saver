FROM python:3.14-slim AS base

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV AUTO_CLEANUP_TMP=1


WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

COPY ./requirements.txt /app/
RUN pip install --requirement /app/requirements.txt --root-user-action=ignore
COPY ./showsaver /app

VOLUME /config /tvshows /tmp

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--worker-tmp-dir", "/dev/shm", "main:app"]

# ===== Development stage =====
FROM base AS dev

COPY ./requirements-dev.txt /app/
RUN pip install --requirement /app/requirements-dev.txt --root-user-action=ignore

EXPOSE 5678
