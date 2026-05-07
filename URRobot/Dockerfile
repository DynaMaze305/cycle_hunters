FROM python:3.10

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir setuptools wheel

COPY urbasic /app/urbasic
RUN python3 -m pip install --no-cache-dir -e /app/urbasic

CMD ["python", "-m", "ur_robot"]


