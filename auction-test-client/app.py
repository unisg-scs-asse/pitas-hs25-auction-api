#!/usr/bin/env python3
"""
Lightweight Auction Test Client
A simple service that automatically bids on auctions and executes jobs when it wins.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional, Set

import paho.mqtt.client as mqtt
import requests
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration from environment variables
AUCTION_HOUSE_BASE_URL = os.getenv("AUCTION_HOUSE_BASE_URL", "http://localhost:8090")
TEST_CLIENT_BASE_URL = os.getenv("TEST_CLIENT_BASE_URL", "http://localhost:8091")
TEST_CLIENT_NAME = os.getenv("TEST_CLIENT_NAME", "test-client")
TEST_CLIENT_PORT = int(os.getenv("TEST_CLIENT_PORT", "8091"))
SUPPORTED_JOB_TYPES = {
    jt.strip() for jt in os.getenv("SUPPORTED_JOB_TYPES", "testJob").split(",") if jt.strip()
}

MQTT_ENABLED = os.getenv("MQTT_ENABLED", "true").lower() == "true"
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "ch/unisg/pitas/auctions/#")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Store active jobs we're executing
active_jobs = {}

# Track auctions we've already bid on (to avoid duplicate bids)
auctions_bid_on: Set[str] = set()

mqtt_client: Optional[mqtt.Client] = None


def ensure_trailing_slash(value: str) -> str:
    if not value.endswith("/"):
        return value + "/"
    return value


def is_supported_job(job_type: Optional[str]) -> bool:
    if not job_type:
        return False
    return not SUPPORTED_JOB_TYPES or job_type in SUPPORTED_JOB_TYPES


def start_mqtt_listener():
    if not MQTT_ENABLED:
        logger.info("MQTT listener disabled via environment variable")
        return

    client = mqtt.Client(client_id=f"{TEST_CLIENT_NAME}-mqtt")
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    def on_connect(_client, _userdata, _flags, rc, _properties=None):
        if rc == 0:
            logger.info(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}, subscribing to {MQTT_TOPIC}")
            _client.subscribe(MQTT_TOPIC)
        else:
            logger.error(f"MQTT connection failed with rc={rc}")

    def on_message(_client, _userdata, message):
        handle_mqtt_message(message.topic, message.payload)

    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as exc:
            logger.error(f"MQTT loop terminated: {exc}. Reconnecting in 5s")
            time.sleep(5)


def handle_mqtt_message(topic: str, payload: bytes):
    try:
        data = json.loads(payload.decode("utf-8"))
        auction = data.get("data", {}).get("auction")
        if not auction:
            return

        auction_id = auction.get("auctionId")
        job_type = auction.get("jobType")
        if not auction_id or auction_id in auctions_bid_on or not is_supported_job(job_type):
            return

        auction_house_uri = ensure_trailing_slash(auction.get("auctionHouseUri", AUCTION_HOUSE_BASE_URL))
        logger.info(
            f"MQTT: discovered auction {auction_id} (jobType={job_type}) on topic {topic}. Placing bid."
        )
        place_bid_on_auction(
            {
                "auctionId": auction_id,
                "auctionHouseUri": auction_house_uri,
                "jobType": job_type,
                "status": auction.get("status", "OPEN"),
            }
        )
        auctions_bid_on.add(auction_id)
    except json.JSONDecodeError:
        logger.warning("Received invalid MQTT payload: %s", payload[:200])


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route("/bidders", methods=["POST"])
def handle_auction_started():
    """
    Called when an auction starts (via direct HTTP notification).
    Automatically places a bid on the auction.

    This endpoint can be called directly by the auction house if it knows about this client.
    Alternatively, the client will discover auctions via polling.
    """
    try:
        data = request.get_json()
        auction_id = data.get("auctionId")
        auction_house_uri = data.get("auctionHouseUri")
        job_type = data.get("jobType")

        logger.info(
            f"Received auction started notification: auctionId={auction_id}, jobType={job_type}"
        )

        # Place bid on the auction
        auction = {
            "auctionId": auction_id,
            "auctionHouseUri": auction_house_uri,
            "status": "OPEN",
        }
        place_bid_on_auction(auction)
        auctions_bid_on.add(auction_id)

        # Return the auction representation
        return jsonify(data), 201

    except Exception as e:
        logger.error(f"Error handling auction started notification: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/bidders/<auction_id>/job", methods=["POST"])
def handle_job_assignment(auction_id: str):
    """
    Called when we win an auction.
    Receives the job assignment and executes it.
    """
    try:
        data = request.get_json()
        job_type = data.get("jobType")
        input_data = data.get("inputData")
        auction_house_uri = data.get("auctionHouseUri")

        logger.info(
            f"Received job assignment for auction {auction_id}: jobType={job_type}, inputData={input_data}"
        )

        # Store job info
        active_jobs[auction_id] = {
            "jobType": job_type,
            "inputData": input_data,
            "auctionHouseUri": auction_house_uri,
            "receivedAt": datetime.now().isoformat(),
        }

        # Simulate job execution (in a real scenario, this would take time)
        # For testing, we'll execute it immediately
        logger.info(f"Executing job for auction {auction_id}...")
        time.sleep(0.5)  # Simulate some processing time

        # Generate output based on job type
        output_data = execute_job(job_type, input_data)

        # Send job result back to the auction house
        result_payload = {
            "auctionId": auction_id,
            "auctionHouseUri": auction_house_uri,
            "jobType": job_type,
            "status": "EXECUTED",
            "inputData": input_data,
            "outputData": output_data,
        }

        # Ensure auction_house_uri has a trailing slash, then construct URL properly
        if not auction_house_uri.endswith("/"):
            auction_house_uri = auction_house_uri + "/"
        result_url = f"{auction_house_uri}auctions/{auction_id}/job"
        logger.info(
            f"Sending job result to {result_url} with payload: {result_payload}"
        )

        try:
            response = requests.post(
                result_url,
                json=result_payload,
                headers={"Content-Type": "application/json", "X-API-Version": "1"},
                timeout=10,
            )

            logger.info(
                f"Response from auction house: status={response.status_code}, body={response.text[:200]}"
            )

            if response.status_code == 201:
                logger.info(f"Successfully sent job result for auction {auction_id}")
                if auction_id in active_jobs:
                    del active_jobs[auction_id]
            else:
                logger.error(
                    "Failed to send job result: status=%s body=%s payload=%s",
                    response.status_code,
                    response.text,
                    json.dumps(result_payload),
                )
                return jsonify({"error": "Failed to send job result"}), 500
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Exception while sending job result to {result_url}: {e}",
                exc_info=True,
            )
            return jsonify({"error": str(e)}), 500

        # Return the job representation
        return jsonify(result_payload), 201

    except Exception as e:
        logger.error(f"Error handling job assignment: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def execute_job(job_type: str, input_data: Optional[str]) -> str:
    """
    Execute a job and return the output.
    This is a dummy implementation that returns a fixed message for testing.
    """
    logger.info(f"Executing job type: {job_type}, input: {input_data}")

    # Return the same message for all job types (as requested)
    return "Cloudflare is having a little issue at the moment, grab a coffee and come back in 5 days"


@app.route("/status", methods=["GET"])
def status():
    """Get status of the test client"""
    return (
        jsonify(
            {
                "name": TEST_CLIENT_NAME,
                "baseUrl": TEST_CLIENT_BASE_URL,
                "auctionHouseUrl": AUCTION_HOUSE_BASE_URL,
                "activeJobs": len(active_jobs),
                "jobs": list(active_jobs.keys()),
                "auctionsBidOn": len(auctions_bid_on),
            }
        ),
        200,
    )


def poll_for_auctions():
    """
    Poll the auction house for open auctions and automatically bid on them.
    This runs in a background thread.

    Polls GET {AUCTION_HOUSE_BASE_URL}/auctions/ every POLL_INTERVAL_SECONDS seconds
    to discover new open auctions and automatically bid on them.
    """
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
    logger.info(f"Starting auction polling thread (interval: {poll_interval}s)")

    while True:
        try:
            # Get list of open auctions from the auction house
            auctions_url = f"{AUCTION_HOUSE_BASE_URL}/auctions/"
            logger.debug(f"Polling for auctions at {auctions_url}")

            response = requests.get(
                auctions_url,
                headers={"X-API-Version": "1"},
                timeout=5,
            )

            if response.status_code == 200:
                auctions = response.json()
                logger.debug(f"Received {len(auctions)} auctions from auction house")

                # Process each auction
                for auction in auctions:
                    auction_id = auction.get("auctionId")
                    status = auction.get("status")

                    # Only bid on open auctions we haven't bid on yet
                    job_type = auction.get("jobType")
                    if (
                        status == "OPEN"
                        and auction_id
                        and auction_id not in auctions_bid_on
                        and is_supported_job(job_type)
                    ):
                        logger.info(
                            f"Found new open auction: {auction_id} (jobType: {job_type})"
                        )
                        place_bid_on_auction(auction)
                        auctions_bid_on.add(auction_id)
                    elif auction_id and auction_id in auctions_bid_on:
                        logger.debug(f"Skipping auction {auction_id} - already bid on")
            else:
                logger.warning(
                    f"Failed to fetch auctions: status={response.status_code}, body={response.text[:200]}"
                )

        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error while polling for auctions: {e}")
        except Exception as e:
            logger.error(f"Error polling for auctions: {e}", exc_info=True)

        time.sleep(poll_interval)


def place_bid_on_auction(auction: dict):
    """
    Place a bid on an auction.
    """
    try:
        auction_id = auction.get("auctionId")
        auction_house_uri = auction.get("auctionHouseUri")
        job_type = auction.get("jobType")

        if not auction_id or not auction_house_uri:
            logger.warning(f"Invalid auction data: {auction}")
            return

        if not is_supported_job(job_type):
            logger.info(
                f"Skipping auction {auction_id} because jobType '{job_type}' is not supported"
            )
            return

        bid_payload = {
            "auctionId": auction_id,
            "bidderName": TEST_CLIENT_NAME,
            "bidderAuctionHouseUri": TEST_CLIENT_BASE_URL + "/",
        }

        bid_url = f"{ensure_trailing_slash(auction_house_uri)}auctions/{auction_id}/bid"
        logger.info(f"Placing bid on auction {auction_id} at {bid_url}")

        response = requests.post(
            bid_url,
            json=bid_payload,
            headers={"Content-Type": "application/json", "X-API-Version": "1"},
            timeout=5,
        )

        if response.status_code == 201:
            logger.info(f"Successfully placed bid on auction {auction_id}")
        else:
            logger.warning(
                f"Failed to place bid: status={response.status_code}, body={response.text}"
            )

    except Exception as e:
        logger.error(f"Error placing bid: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("Starting Auction Test Client")
    logger.info(f"  Name: {TEST_CLIENT_NAME}")
    logger.info(f"  Base URL: {TEST_CLIENT_BASE_URL}")
    logger.info(f"  Auction House URL: {AUCTION_HOUSE_BASE_URL}")
    logger.info(f"  Listening on port {TEST_CLIENT_PORT}")
    logger.info(
        f"  Supported job types: {', '.join(sorted(SUPPORTED_JOB_TYPES)) if SUPPORTED_JOB_TYPES else 'all'}"
    )
    logger.info(
        f"  MQTT: {'enabled' if MQTT_ENABLED else 'disabled'} (broker={MQTT_BROKER}:{MQTT_PORT}, topic={MQTT_TOPIC})"
    )

    # Start polling thread for discovering auctions
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
    logger.info(f"  Polling for auctions every {poll_interval} seconds")

    polling_thread = threading.Thread(target=poll_for_auctions, daemon=True)
    polling_thread.start()

    if MQTT_ENABLED:
        mqtt_thread = threading.Thread(target=start_mqtt_listener, daemon=True)
        mqtt_thread.start()

    app.run(host="0.0.0.0", port=TEST_CLIENT_PORT, debug=False)
