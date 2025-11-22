#!/usr/bin/env python3
"""
Lightweight Auction Test Client
A simple service that automatically bids on auctions and executes jobs when it wins.
"""

import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional, Set

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

# Store active jobs we're executing
active_jobs = {}

# Track auctions we've already bid on (to avoid duplicate bids)
auctions_bid_on: Set[str] = set()


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
                # Clean up
                if auction_id in active_jobs:
                    del active_jobs[auction_id]
            else:
                logger.error(
                    f"Failed to send job result: status={response.status_code}, body={response.text}"
                )
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Exception while sending job result to {result_url}: {e}",
                exc_info=True,
            )
            raise

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
                    if (
                        status == "OPEN"
                        and auction_id
                        and auction_id not in auctions_bid_on
                    ):
                        logger.info(
                            f"Found new open auction: {auction_id} (jobType: {auction.get('jobType', 'unknown')})"
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

        if not auction_id or not auction_house_uri:
            logger.warning(f"Invalid auction data: {auction}")
            return

        bid_payload = {
            "auctionId": auction_id,
            "bidderName": TEST_CLIENT_NAME,
            "bidderAuctionHouseUri": TEST_CLIENT_BASE_URL + "/",
        }

        bid_url = f"{auction_house_uri}auctions/{auction_id}/bid"
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

    # Start polling thread for discovering auctions
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
    logger.info(f"  Polling for auctions every {poll_interval} seconds")

    polling_thread = threading.Thread(target=poll_for_auctions, daemon=True)
    polling_thread.start()

    app.run(host="0.0.0.0", port=TEST_CLIENT_PORT, debug=False)
