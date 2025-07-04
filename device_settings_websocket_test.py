import asyncio
import json
import random
import sys
import time

import websockets

# Client heartbeat interval (in seconds)
HEARTBEAT_INTERVAL = 30


async def test_device_settings_websocket():
    """
    Test the device settings WebSocket connection.
    Usage: python device_settings_websocket_test.py <device_id> <api_key>
    """

    # Use device ID with hyphens to match server format
    device_id = "0fd95512318f4ec88aa9f071d39ab18c"  # With hyphens
    api_key = "LqvhDU4sb51uVMw5oMGpHE0xPuYhG47eF1onAI8mGyofgESLcU3eMeLqmMmKbU5i"

    # Construct the WebSocket URL with the device ID and API key
    uri = f"ws://127.0.0.1:8000/ws/device-connection/{device_id}/?api_key={api_key}"

    print(f"Connecting to: {uri}")
    print(f"Current time: {time.strftime('%H:%M:%S')}")

    # Store previous settings to detect changes
    previous_settings = {}

    # Flag to track if we have an active session (necessary for sending posture data)
    has_active_session = False

    # Flag to control heartbeat task
    heartbeat_running = False

    try:
        async with websockets.connect(uri) as websocket:
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
            user_task = asyncio.create_task(process_user_commands(websocket))

            # Start heartbeat task
            heartbeat_running = True
            heartbeat_task = asyncio.create_task(send_heartbeats(websocket, heartbeat_running))

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
                    if data.get("type") == "heartbeat_ack":
                        print("❤️ Heartbeat acknowledged by server")

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
    finally:
        # Stop heartbeat task
        heartbeat_running = False
        if "heartbeat_task" in locals() and heartbeat_task:
            heartbeat_task.cancel()

        # Stop user command task
        if "user_task" in locals() and user_task:
            user_task.cancel()


async def send_heartbeats(websocket, running):
    """Periodically send heartbeats to the server"""
    while running:
        try:
            # Sleep for the interval
            await asyncio.sleep(HEARTBEAT_INTERVAL)

            # Send heartbeat
            print(f"❤️ SENDING HEARTBEAT at {time.strftime('%H:%M:%S')}")
            await websocket.send(json.dumps({"type": "heartbeat"}))

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error sending heartbeat: {str(e)}")
            break


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
    while True:
        # Read command from stdin
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        command = line.strip().lower()

        if command == "data":
            # Send a single posture data sample
            await send_single_posture_reading(websocket)
        elif command == "heartbeat":
            # Send a manual heartbeat
            print(f"❤️ Sending manual heartbeat")
            await websocket.send(json.dumps({"type": "heartbeat"}))


if __name__ == "__main__":
    try:
        asyncio.run(test_device_settings_websocket())
    except KeyboardInterrupt:
        print("\nTest script stopped by user")
