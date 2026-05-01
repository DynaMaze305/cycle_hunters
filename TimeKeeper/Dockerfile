FROM python:3.12-slim

WORKDIR /app

# BlueZ + D-Bus runtime required by bleak on Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
        bluez \
        libglib2.0-0 \
        dbus \
        libxml2-dev \
        libxslt-dev \
        gcc \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . ./TimeKeeper/

ENTRYPOINT ["python", "-m", "TimeKeeper.main"]
