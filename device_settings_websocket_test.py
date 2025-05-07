import asyncio
import json
import sys
import uuid
import websockets
import time

async def test_device_settings_websocket():
    """
    Test the device settings WebSocket connection.
    Usage: python device_settings_websocket_test.py <device_id> <api_key>
    """

    # Use device ID with hyphens to match server format
    device_id = "bb7eae68-2135-4f8a-b929-bb4f2e0f217c"  # With hyphens
    api_key = "VzXkNlgfEcPhUl9-qLoyNW2ANYzTLu2iadVF_PfycOx1s7KL_eA-9Q89SaVF0jVY"

    # Construct the WebSocket URL with the device ID and API key
    uri = f"ws://127.0.0.1:8000/ws/device-settings/{device_id}/?api_key={api_key}"

    print(f"Connecting to: {uri}")
    print(f"Current time: {time.strftime('%H:%M:%S')}")
    
    # Store previous settings to detect changes
    previous_settings = {}

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server!")

            # First, receive the initial settings
            initial_settings = await websocket.recv()
            initial_data = json.loads(initial_settings)
            print(f"Initial settings: {initial_data}")
            previous_settings = initial_data.copy()

            # Request the settings again explicitly
            await websocket.send(json.dumps({"action": "get_settings"}))
            settings = await websocket.recv()
            print(f"Requested settings: {json.loads(settings)}")

            # Keep the connection open and listen for updates
            print("Listening for real-time updates (press Ctrl+C to stop)...")
            print("=" * 50)
            print(f"DEBUG: Waiting for messages at {time.strftime('%H:%M:%S')}")
            
            msg_counter = 0
            while True:
                update = await websocket.recv()
                msg_counter += 1
                current_time = time.strftime('%H:%M:%S')
                print(f"\n[{current_time}] Message #{msg_counter} received: {update}")
                
                try:
                    data = json.loads(update)
                    
                    # Handle different message types
                    if data.get('type') == 'heartbeat':
                        print("❤️ Heartbeat received - sending response")
                        await websocket.send(json.dumps({"type": "heartbeat_response"}))
                    
                    elif data.get('type') == 'session_status':
                        # Handle session status events
                        action = data.get('action')
                        has_active = data.get('has_active_session')
                        
                        if action == 'start_session':
                            print(f"🟢 SESSION STARTED - Active: {has_active}")
                            # Your device could start monitoring posture here
                        
                        elif action == 'stop_session':
                            print(f"🔴 SESSION ENDED - Active: {has_active}")
                            # Your device could stop monitoring posture here
                    
                    else:
                        # Highlight changes in settings
                        changes = []
                        for key, value in data.items():
                            if key not in previous_settings or previous_settings[key] != value:
                                changes.append(f"{key}: {previous_settings.get(key, 'N/A')} → {value}")
                        
                        if changes:
                            print("\n" + "!" * 50)
                            print("🔄 DEVICE SETTINGS UPDATED:")
                            for change in changes:
                                print(f"  ✓ {change}")
                            print("!" * 50)
                        else:
                            print(f"Settings received (no changes): {data}")
                        
                        # Update previous settings
                        previous_settings = data.copy()
                except Exception as e:
                    print(f"Error processing message: {str(e)}")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed with code {e.code}: {e.reason}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    # START THE SERVER WITH: daphne -p 8000 server.asgi:application
    asyncio.run(test_device_settings_websocket())