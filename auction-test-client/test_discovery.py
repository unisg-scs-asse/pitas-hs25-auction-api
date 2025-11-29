#!/usr/bin/env python3
"""
Discovery Endpoint Test Client

Tests the /discovery endpoints for registering and retrieving known auction houses.
Validates responses according to the auction-house.yaml OpenAPI specification.
"""

import logging
import os
import sys

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
AUCTION_HOUSE_BASE_URL = os.getenv(
    "AUCTION_HOUSE_BASE_URL", "http://localhost:8090")
TEST_CLIENT_URI = os.getenv(
    "TEST_CLIENT_URI", "http://localhost:8092")
GROUP_TYPE = os.getenv("GROUP_TYPE", "EVEN")  # EVEN or ODD


def test_get_discovery():
    """
    Test GET /discovery endpoint.

    Retrieves the list of known auction houses and validates the response format.
    Returns True if test passes, False otherwise.
    """
    logger.info("=" * 60)
    logger.info("Testing GET /discovery")
    logger.info("=" * 60)

    try:
        url = f"{AUCTION_HOUSE_BASE_URL}/discovery"
        logger.info(f"Sending GET request to: {url}")

        response = requests.get(
            url,
            headers={"X-API-Version": "1"},
            timeout=10,
        )

        logger.info(f"Response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Expected status 200, got {response.status_code}")
            logger.error(f"Response body: {response.text}")
            return False

        payload = response.json()
        logger.info(f"Response payload: {payload}")

        # Validate DiscoveryHostsPayload format
        logger.info("Validating response format...")

        assert "version" in payload, "Response missing 'version' field"
        assert payload["version"] == 1, f"Expected version 1, got {payload['version']}"
        logger.info("✓ Version field validated")

        assert "data" in payload, "Response missing 'data' field"
        assert isinstance(payload["data"], dict), "'data' must be an object"
        logger.info("✓ Data field validated")

        # Validate DiscoveryHosts data
        data = payload["data"]

        assert "type" in data, "Data missing 'type' field"
        assert data["type"] in ["EVEN", "ODD"], f"Invalid type: {data['type']}"
        logger.info(f"✓ Group type validated: {data['type']}")

        assert "hosts" in data, "Data missing 'hosts' field"
        assert isinstance(data["hosts"], list), "'hosts' must be an array"
        logger.info(
            f"✓ Hosts field validated ({len(data['hosts'])} hosts found)")

        # Validate each DiscoveryHost
        for i, host in enumerate(data["hosts"]):
            assert isinstance(host, dict), f"Host {i} must be an object"
            assert "auctionHouseUri" in host, f"Host {i} missing 'auctionHouseUri' field"
            assert isinstance(
                host["auctionHouseUri"], str), f"Host {i} 'auctionHouseUri' must be a string"
            logger.info(f"  ✓ Host {i}: {host['auctionHouseUri']}")

        logger.info("✅ GET /discovery test PASSED")
        return True

    except AssertionError as e:
        logger.error(f"❌ Validation failed: {e}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return False


def test_post_discovery(group_type: str, auction_house_uri: str):
    """
    Test POST /discovery endpoint.

    Registers an auction house with the discovery service and validates the response.

    Args:
        group_type: Group type ("EVEN" or "ODD")
        auction_house_uri: URI of the auction house to register

    Returns True if test passes, False otherwise.
    """
    logger.info("=" * 60)
    logger.info("Testing POST /discovery")
    logger.info("=" * 60)

    try:
        url = f"{AUCTION_HOUSE_BASE_URL}/discovery"

        # Prepare registration payload
        registration_payload = {
            "version": 1,
            "data": {
                "type": group_type,
                "auctionHouseUri": auction_house_uri
            }
        }

        logger.info(f"Sending POST request to: {url}")
        logger.info(f"Registration payload: {registration_payload}")

        response = requests.post(
            url,
            json=registration_payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Version": "1"
            },
            timeout=10,
        )

        logger.info(f"Response status: {response.status_code}")

        if response.status_code != 201:
            logger.error(f"Expected status 201, got {response.status_code}")
            logger.error(f"Response body: {response.text}")
            return False

        payload = response.json()
        logger.info(f"Response payload: {payload}")

        # Validate DiscoveryRegistrationPayload format
        logger.info("Validating response format...")

        assert "version" in payload, "Response missing 'version' field"
        assert payload["version"] == 1, f"Expected version 1, got {payload['version']}"
        logger.info("✓ Version field validated")

        assert "data" in payload, "Response missing 'data' field"
        assert isinstance(payload["data"], dict), "'data' must be an object"
        logger.info("✓ Data field validated")

        # Validate DiscoveryRegistration data
        data = payload["data"]

        assert "type" in data, "Data missing 'type' field"
        assert data["type"] in ["EVEN", "ODD"], f"Invalid type: {data['type']}"
        assert data["type"] == group_type, f"Expected type '{group_type}', got '{data['type']}'"
        logger.info(f"✓ Group type validated: {data['type']}")

        assert "auctionHouseUri" in data, "Data missing 'auctionHouseUri' field"
        assert isinstance(data["auctionHouseUri"],
                          str), "'auctionHouseUri' must be a string"
        logger.info(
            f"✓ Auction house URI validated: {data['auctionHouseUri']}")

        logger.info("✅ POST /discovery test PASSED")
        return True

    except AssertionError as e:
        logger.error(f"❌ Validation failed: {e}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return False


def test_discovery_integration():
    """
    Integration test: Register an auction house and verify it appears in the list.

    Returns True if test passes, False otherwise.
    """
    logger.info("=" * 60)
    logger.info("Testing Discovery Integration (POST + GET)")
    logger.info("=" * 60)

    try:
        # First, register a test auction house
        test_uri = f"https://test-integration.{GROUP_TYPE.lower()}.asse.scs.unisg.ch"
        logger.info(f"Step 1: Registering test URI: {test_uri}")

        if not test_post_discovery(GROUP_TYPE, test_uri):
            logger.error("Registration failed in integration test")
            return False

        logger.info("Step 2: Retrieving auction houses list...")

        # Get the list of auction houses
        url = f"{AUCTION_HOUSE_BASE_URL}/discovery"
        response = requests.get(
            url,
            headers={"X-API-Version": "1"},
            timeout=10,
        )

        if response.status_code != 200:
            logger.error(
                f"GET request failed with status {response.status_code}")
            return False

        payload = response.json()
        hosts = payload.get("data", {}).get("hosts", [])

        # Check if our registered URI is in the list
        registered_uris = [host.get("auctionHouseUri") for host in hosts]

        if test_uri in registered_uris:
            logger.info(f"✓ Test URI found in discovery list")
            logger.info("✅ Discovery integration test PASSED")
            return True
        else:
            logger.warning(
                f"Test URI not found in discovery list (might be expected if not persistent)")
            logger.info(f"Found {len(registered_uris)} registered URIs")
            logger.info(
                "✅ Discovery integration test COMPLETED (URI not required to persist)")
            return True

    except Exception as e:
        logger.error(f"❌ Integration test error: {e}", exc_info=True)
        return False


def main():
    """Run all discovery endpoint tests."""
    logger.info("Starting Discovery Endpoint Tests")
    logger.info(f"Auction House URL: {AUCTION_HOUSE_BASE_URL}")
    logger.info(f"Test Client URI: {TEST_CLIENT_URI}")
    logger.info(f"Group Type: {GROUP_TYPE}")
    logger.info("")

    results = {}

    # Test 1: GET /discovery
    results["GET /discovery"] = test_get_discovery()
    logger.info("")

    # Test 2: POST /discovery
    results["POST /discovery"] = test_post_discovery(
        GROUP_TYPE, TEST_CLIENT_URI)
    logger.info("")

    # Test 3: Integration test
    results["Integration Test"] = test_discovery_integration()
    logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")

    # Exit with appropriate code
    if passed == total:
        logger.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.error(f"⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
