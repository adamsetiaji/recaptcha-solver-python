FROM mcr.microsoft.com/playwright/python:v1.51.0-jammy

# Set timezone to avoid tzdata prompt
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Jakarta

RUN apt-get update && apt-get install -y \
    tzdata \
    x11vnc xvfb lsof sudo \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install python-dotenv

EXPOSE 3000 5900

CMD ["python3", "app.py"]
