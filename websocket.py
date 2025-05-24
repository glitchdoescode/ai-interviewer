import asyncio
from google import genai
from google.genai.types import LiveConnectConfig
# Import Content and Part directly from google.generativeai
from google.genai.types import Content, Part

async def main():
    # Replace "AIzaSyC8UT1YObB7fbn1cfe3KVm7nBeid08wBKE" with your actual API key or use a more secure method to load it
    client = genai.Client(api_key="AIzaSyC8UT1YObB7fbn1cfe3KVm7nBeid08wBKE") # Please replace this with your actual API key
    config = LiveConnectConfig(response_modalities=["TEXT"])
    model_id = "gemini-2.0-flash-exp"
    async with client.aio.live.connect(model=model_id, config=config) as session:
        # Remove the redundant import inside the async with block
        # from google.generativeai.types import Content, Part
        await session.send_client_content(turns=Content(role="user", parts=[Part(text="Say hello!")]))
        async for message in session.receive():
            print("RESPONSE:", message.text)
            if message.server_content and message.server_content.turn_complete:
                break

# asyncio.run(main()) # Remove this line
asyncio.run(main())  # Use await instead of asyncio.run() in Jupyter notebooks