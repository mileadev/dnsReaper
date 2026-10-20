FROM python:3.11-alpine AS builder
RUN apk add --no-cache gcc libffi musl-dev libffi-dev

# Create app directory
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# Prepares a zipped version of the application suitable for running on lambda
FROM amazon/aws-lambda-python:3.11 AS lambda

COPY requirements.txt /app/
COPY lambda-requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt -r lambda-requirements.txt --target .
COPY . /app

RUN yum install -y zip && yum clean all && zip -r9 /packaged_app.zip .

# Main application target
FROM python:3.11-alpine
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN addgroup -S app \
    && adduser -S -G app -h /home/app app \
    && mkdir -p /app/results \
    && chown -R app:app /app
WORKDIR /app

COPY --chown=app:app . .

# Exports
ENV SM_COMMAND="docker run punksecurity/dnsreaper --"
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app
USER app
ENTRYPOINT [ "python3", "/app/main.py" ]

