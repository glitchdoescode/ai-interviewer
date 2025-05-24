import asyncio
import websockets

async def connect_with_headers():
    uri = "wss://echo.websocket.org" # A public echo server
    try:
        async with websockets.connect(uri, extra_headers={"X-Custom-Header": "TestValue"}) as websocket:
            print(f"Connected to {uri} with custom header.")
            await websocket.send("Hello from websockets!")
            response = await websocket.recv()
            print(f"Received: {response}")
    except Exception as e:
            print(f"WebSocket connection failed: {e}")
if __name__ == "__main__":
    asyncio.run(connect_with_headers())