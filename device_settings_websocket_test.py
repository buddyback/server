import asyncio
import json
import random
import sys
import time

import websockets


async def test_device_settings_websocket():
    """
    Test the device settings WebSocket connection.
    Usage: python device_settings_websocket_test.py <device_id> <api_key>
    """

    # Use device ID with hyphens to match server format
    device_id = "bb7eae68-2135-4f8a-b929-bb4f2e0f217c"  # With hyphens
    api_key = "VzXkNlgfEcPhUl9-qLoyNW2ANYzTLu2iadVF_PfycOx1s7KL_eA-9Q89SaVF0jVY"

    # Construct the WebSocket URL with the device ID and API key
    uri = f"ws://127.0.0.1:8000/ws/device-connection/{device_id}/?api_key={api_key}"

    print(f"Connecting to: {uri}")
    print(f"Current time: {time.strftime('%H:%M:%S')}")

    # Store previous settings to detect changes
    previous_settings = {}

    # Flag to track if we have an active session (necessary for sending posture data)
    has_active_session = False

    # Create a global variable to store the websocket connection
    websocket_connection = None

    try:
        async with websockets.connect(uri) as websocket:
            websocket_connection = websocket
            print("Connected to WebSocket server!")

            # First, receive the initial settings
            initial_settings = await websocket.recv()
            initial_data = json.loads(initial_settings)
            print(f"Initial settings: {initial_data}")
            previous_settings = initial_data.copy()

            # Check if we already have an active session
            if isinstance(initial_data, dict) and initial_data.get("data"):
                has_active_session = initial_data.get("data", {}).get("has_active_session", False)
            elif isinstance(initial_data, dict):
                has_active_session = initial_data.get("has_active_session", False)

            print(f"Active session status: {'🟢 ACTIVE' if has_active_session else '🔴 INACTIVE'}")

            # Request the settings again explicitly
            await websocket.send(json.dumps({"type": "settings_request"}))
            settings = await websocket.recv()
            print(f"Requested settings: {json.loads(settings)}")

            # Start a background task for user commands
            asyncio.create_task(process_user_commands(websocket))

            # Keep the connection open and listen for updates
            print("Listening for real-time updates (press Ctrl+C to stop)...")
            print("=" * 50)
            print("Commands:")
            print("  'data' - Send single posture data sample")
            print("=" * 50)
            print(f"DEBUG: Waiting for messages at {time.strftime('%H:%M:%S')}")

            msg_counter = 0
            while True:
                update = await websocket.recv()
                msg_counter += 1
                current_time = time.strftime("%H:%M:%S")
                print(f"\n[{current_time}] Message #{msg_counter} received: {update}")

                try:
                    data = json.loads(update)

                    # Handle different message types
                    if data.get("type") == "heartbeat":
                        print("❤️ Heartbeat received - sending response")
                        await websocket.send(json.dumps({"type": "heartbeat_response"}))

                    elif data.get("type") == "session_status":
                        # Handle session status events
                        action = data.get("action")
                        has_active_session = data.get("has_active_session", False)

                        if action == "start_session":
                            print(f"🟢 SESSION STARTED - Active: {has_active_session}")
                            # Your device could start monitoring posture here

                        elif action == "stop_session":
                            print(f"🔴 SESSION ENDED - Active: {has_active_session}")
                            # Your device could stop monitoring posture here

                    elif data.get("type") == "posture_data_response":
                        # Handle response to our posture data submission
                        status = data.get("status")
                        if status == "success":
                            print("✅ Posture data successfully saved")
                        else:
                            print(f"❌ Error saving posture data: {data.get('error')}")

                    elif data.get("type") == "settings":
                        # Extract the actual settings data
                        settings_data = data.get("data", {})

                        # Update session status from settings if available
                        if "has_active_session" in settings_data:
                            has_active_session = settings_data["has_active_session"]

                        # Highlight changes in settings
                        changes = []
                        for key, value in settings_data.items():
                            if key not in previous_settings or previous_settings[key] != value:
                                changes.append(f"{key}: {previous_settings.get(key, 'N/A')} → {value}")

                        if changes:
                            print("\n" + "!" * 50)
                            print("🔄 DEVICE SETTINGS UPDATED:")
                            for change in changes:
                                print(f"  ✓ {change}")
                            print("!" * 50)
                        else:
                            print(f"Settings received (no changes): {settings_data}")

                        # Update previous settings
                        previous_settings = settings_data.copy()

                    else:
                        print(f"Unknown message type: {data}")

                except Exception as e:
                    print(f"Error processing message: {str(e)}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed with code {e.code}: {e.reason}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")


async def send_single_posture_reading(websocket):
    """Send a single posture reading with randomized scores"""

    # Generate somewhat realistic scores (weighted towards medium-good posture)
    neck_score = random.randint(50, 95)
    torso_score = random.randint(60, 95)
    shoulders_score = random.randint(55, 90)

    # Create posture data payload
    posture_data = {
        "type": "posture_data",
        "data": {
            "components": [
                {"component_type": "neck", "score": neck_score},
                {"component_type": "torso", "score": torso_score},
                {"component_type": "shoulders", "score": shoulders_score},
            ]
        },
    }

    # Send data and print what we're sending
    print(f"\n📤 Sending posture data: neck={neck_score}, torso={torso_score}, shoulders={shoulders_score}")
    await websocket.send(json.dumps(posture_data))


async def process_user_commands(websocket):
    """Process user commands from stdin while WebSocket is running"""
    global auto_send_enabled, auto_send_interval

    while True:
        # Read command from stdin
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        command = line.strip().lower()

        if command == "data":
            # Send a single posture data sample
            await send_single_posture_reading(websocket)


if __name__ == "__main__":
    # START THE SERVER WITH: daphne -p 8000 server.asgi:application
    try:
        asyncio.run(test_device_settings_websocket())
    except KeyboardInterrupt:
        print("\nTest script stopped by user")
    finally:
        # Make sure we stop auto-sending on exit
        auto_send_enabled = False
