FROM python:3.14-slim AS base

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV AUTO_CLEANUP_TMP=1


RUN apt-get update && \
    apt-get install -y ffmpeg gosu && \
    apt-get clean

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install --requirement /app/requirements.txt --root-user-action=ignore
COPY ./showsaver /app

RUN mkdir -p /config /tvshows /temp_dir && \
    chown -R appuser:appuser /app /config /tvshows /temp_dir

VOLUME /config /tvshows /temp_dir

EXPOSE 5000

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]

# ===== Development stage =====
FROM base AS dev

COPY ./requirements-dev.txt /app/requirements-dev.txt
RUN pip install --requirement /app/requirements-dev.txt --root-user-action=ignore

EXPOSE 5678

CMD ["python", "main.py"]
