FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8091

ENV AUCTION_HOUSE_BASE_URL=http://localhost:8090
ENV TEST_CLIENT_BASE_URL=http://localhost:8091
ENV TEST_CLIENT_NAME=test-client
ENV TEST_CLIENT_PORT=8091
ENV POLL_INTERVAL_SECONDS=5

CMD ["python", "app.py"]


