#!/usr/bin/env python3
"""
Test script for WebSocket lifecycle logging
"""
import asyncio
import websockets
import json
import logging

# Set up logging to see the server logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_connection():
    """Test WebSocket connection to verify lifecycle logging"""
    try:
        # Test screener endpoint (requires JWT token)
        uri = "ws://localhost:8000/ws/screener?token=test_token"
        logger.info(f"Connecting to {uri}")

        async with websockets.connect(uri) as websocket:
            logger.info("Connected to screener WebSocket")

            # Wait a bit to see connection logs
            await asyncio.sleep(2)

            # Send a test message
            await websocket.send(json.dumps({"type": "ping"}))
            logger.info("Sent ping message")

            # Wait for response or timeout
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"Received: {response}")
            except asyncio.TimeoutError:
                logger.info("No response received (expected for invalid token)")

    except Exception as e:
        logger.error(f"Connection failed: {e}")

    # Test price endpoint
    try:
        uri = "ws://localhost:8000/ws/price?symbol=RELIANCE&token=test_token"
        logger.info(f"Connecting to {uri}")

        async with websockets.connect(uri) as websocket:
            logger.info("Connected to price WebSocket")

            # Wait a bit to see connection logs
            await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"Price WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())