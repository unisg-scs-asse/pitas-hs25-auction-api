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
AUCTION_HOUSE_BASE_URL = os.getenv(
    "AUCTION_HOUSE_BASE_URL", "http://localhost:8090")
TEST_CLIENT_BASE_URL = os.getenv(
    "TEST_CLIENT_BASE_URL", "http://localhost:8091")
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
        auction_house_uri = AUCTION_HOUSE_BASE_URL
        job_type = data.get("jobType")

        logger.info(
            f"Received auction started notification: auctionId={auction_id}, jobType={job_type}"
        )

        # Only bid on testJob auctions
        if job_type == "testJob":
            # Place bid on the auction
            auction = {
                "auctionId": auction_id,
                "auctionHouseUri": auction_house_uri,
                "status": "OPEN",
                "jobType": job_type,
            }
            place_bid_on_auction(auction)
            auctions_bid_on.add(auction_id)
        else:
            logger.info(
                f"Skipping auction {auction_id} - jobType '{job_type}' is not 'testJob'")

        # Return the auction representation
        return jsonify(data), 201

    except Exception as e:
        logger.error(
            f"Error handling auction started notification: {e}", exc_info=True)
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
        auction_house_uri = AUCTION_HOUSE_BASE_URL

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
            "version": 1,
            "data": {
                "auctionId": auction_id,
                "auctionHouseUri": auction_house_uri,
                "jobType": job_type,
                "status": "EXECUTED",
                "inputData": input_data,
                "outputData": output_data,
            }}

        result_url = f"{AUCTION_HOUSE_BASE_URL}/auctions/{auction_id}/job"
        logger.info(
            f"Sending job result to {result_url} with payload: {result_payload}"
        )

        try:
            response = requests.post(
                result_url,
                json=result_payload,
                headers={"Content-Type": "application/json",
                         "X-API-Version": "1"},
                timeout=10,
            )

            logger.info(
                f"Response from auction house: status={response.status_code}, body={response.text[:200]}"
            )

            if response.status_code == 201:
                # Validate JobPayload response format
                job_response = response.json()
                assert "version" in job_response, "Job response missing 'version' field"
                assert job_response[
                    "version"] == 1, f"Expected version 1, got {job_response['version']}"
                assert "data" in job_response, "Job response missing 'data' field"
                assert isinstance(
                    job_response["data"], dict), "'data' must be an object"
                assert "auctionId" in job_response["data"], "Job data missing 'auctionId' field"
                assert "jobType" in job_response["data"], "Job data missing 'jobType' field"
                assert "status" in job_response["data"], "Job data missing 'status' field"
                assert job_response["data"]["status"] in [
                    "OPEN", "EXECUTED", "FAILED"], f"Invalid job status: {job_response['data']['status']}"

                logger.info(
                    f"Successfully sent job result for auction {auction_id}")
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

    return ("Testing: " + input_data) if input_data else "Testing: no input"


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


def fetch_and_validate_auction(auction_id: str):
    """
    Fetch a specific auction by ID and validate its response format.
    Tests the GET /auctions/{auctionId} endpoint.
    """
    try:
        auction_url = f"{AUCTION_HOUSE_BASE_URL}/auctions/{auction_id}"
        logger.debug(f"Fetching auction details for {auction_id}")

        response = requests.get(
            auction_url,
            headers={"X-API-Version": "1"},
            timeout=5,
        )

        if response.status_code == 200:
            payload = response.json()

            # Validate AuctionPayload format
            assert "version" in payload, f"Auction response missing 'version' field for {auction_id}"
            assert payload["version"] == 1, f"Expected version 1, got {payload['version']} for {auction_id}"
            assert "data" in payload, f"Auction response missing 'data' field for {auction_id}"
            assert isinstance(
                payload["data"], dict), f"'data' must be an object for {auction_id}"

            # Validate Auction object fields
            auction = payload["data"]
            assert "status" in auction, f"Auction data missing 'status' field for {auction_id}"
            assert auction["status"] in [
                "OPEN", "CLOSED"], f"Invalid auction status: {auction['status']} for {auction_id}"
            assert "auctionHouseUri" in auction, f"Auction data missing 'auctionHouseUri' field for {auction_id}"
            assert "jobType" in auction, f"Auction data missing 'jobType' field for {auction_id}"
            assert "deadline" in auction, f"Auction data missing 'deadline' field for {auction_id}"

            logger.debug(f"Successfully validated auction {auction_id}")
        elif response.status_code == 404:
            logger.warning(f"Auction {auction_id} not found (404)")
        else:
            logger.warning(
                f"Failed to fetch auction {auction_id}: status={response.status_code}, body={response.text[:200]}"
            )

    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error fetching auction {auction_id}: {e}")
    except AssertionError as e:
        logger.error(f"Validation error for auction {auction_id}: {e}")
    except Exception as e:
        logger.error(
            f"Error fetching auction {auction_id}: {e}", exc_info=True)


def poll_for_auctions():
    """
    Poll the auction house for open auctions and automatically bid on them.
    This runs in a background thread.

    Polls GET {AUCTION_HOUSE_BASE_URL}/auctions/ every POLL_INTERVAL_SECONDS seconds
    to discover new open auctions and automatically bid on them.
    """
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
    logger.info(
        f"Starting auction polling thread (interval: {poll_interval}s)")

    while True:
        try:
            # Get list of open auctions from the auction house
            auctions_url = f"{AUCTION_HOUSE_BASE_URL}/auctions"
            logger.debug(f"Polling for auctions at {auctions_url}")

            response = requests.get(
                auctions_url,
                headers={"X-API-Version": "1"},
                timeout=5,
            )

            if response.status_code == 200:
                payload = response.json()

                # Validate AuctionListPayload format
                assert "version" in payload, "Response missing 'version' field"
                assert payload["version"] == 1, f"Expected version 1, got {payload['version']}"
                assert "data" in payload, "Response missing 'data' field"
                assert isinstance(
                    payload["data"], dict), "'data' must be an object"
                assert "auctions" in payload["data"], "Response data missing 'auctions' field"
                assert isinstance(
                    payload["data"]["auctions"], list), "'auctions' must be an array"

                auctions = payload["data"]["auctions"]
                logger.info(
                    f"Received {len(auctions)} auctions from auction house")

                # Validate each Auction object
                for auction in auctions:
                    assert "status" in auction, f"Auction missing 'status' field: {auction}"
                    assert auction["status"] in [
                        "OPEN", "CLOSED"], f"Invalid auction status: {auction['status']}"
                    assert "auctionHouseUri" in auction, f"Auction missing 'auctionHouseUri' field: {auction}"
                    assert "jobType" in auction, f"Auction missing 'jobType' field: {auction}"
                    assert "deadline" in auction, f"Auction missing 'deadline' field: {auction}"

                # Fetch and validate individual auction details
                for auction in auctions:
                    auction_id = auction.get("auctionId")
                    if auction_id:
                        fetch_and_validate_auction(auction_id)

                # Process each auction
                for auction in auctions:
                    auction_id = auction.get("auctionId")
                    status = auction.get("status")
                    job_type = auction.get("jobType")

                    # Only bid on open testJob auctions we haven't bid on yet
                    if (
                        status == "OPEN"
                        and auction_id
                        and auction_id not in auctions_bid_on
                        and job_type == "testJob"
                    ):
                        logger.info(
                            f"Found new open auction: {auction_id} (jobType: {job_type})"
                        )
                        place_bid_on_auction(auction)
                        auctions_bid_on.add(auction_id)
                    elif auction_id and status == "OPEN" and job_type != "testJob":
                        logger.debug(
                            f"Skipping auction {auction_id} - jobType '{job_type}' is not 'testJob'")
                    elif auction_id and auction_id in auctions_bid_on:
                        logger.debug(
                            f"Skipping auction {auction_id} - already bid on")
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

        if not auction_id:
            logger.warning(f"Invalid auction data: {auction}")
            return

        bid_payload = {
            "version": 1,
            "data": {
                "auctionId": auction_id,
                "bidderName": TEST_CLIENT_NAME,
                "bidderAuctionHouseUri": TEST_CLIENT_BASE_URL + "/",
            }
        }

        # Use the configured AUCTION_HOUSE_BASE_URL instead of auctionHouseUri from the auction
        # to ensure we use a resolvable hostname
        bid_url = f"{AUCTION_HOUSE_BASE_URL}/auctions/{auction_id}/bid"
        logger.info(f"Placing bid on auction {auction_id} at {bid_url}")

        response = requests.post(
            bid_url,
            json=bid_payload,
            headers={"Content-Type": "application/json", "X-API-Version": "1"},
            timeout=5,
        )

        if response.status_code == 201:
            # Validate BidPayload response format
            bid_response = response.json()
            assert "version" in bid_response, "Bid response missing 'version' field"
            assert bid_response["version"] == 1, f"Expected version 1, got {bid_response['version']}"
            assert "data" in bid_response, "Bid response missing 'data' field"
            assert isinstance(
                bid_response["data"], dict), "'data' must be an object"
            assert "bidderName" in bid_response["data"], "Bid data missing 'bidderName' field"
            assert "bidderAuctionHouseUri" in bid_response[
                "data"], "Bid data missing 'bidderAuctionHouseUri' field"

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
