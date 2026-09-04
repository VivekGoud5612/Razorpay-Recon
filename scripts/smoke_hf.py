from openai import AsyncOpenAI
import os
import asyncio
from dotenv import load_dotenv


async def main():
    load_dotenv()

    client = AsyncOpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=os.environ["HF_TOKEN"],
        timeout=60.0,
    )

    response = await client.responses.create(
        model=os.environ["HF_MODEL"],
        input="Reply with exactly: hello",
    )

    print(response.output_text)


asyncio.run(main())