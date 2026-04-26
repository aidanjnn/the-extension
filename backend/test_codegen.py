import asyncio
import os
from dotenv import load_dotenv
from agentverse_app.codegen import _generate_checked
import logging

logging.basicConfig(level=logging.WARNING)

load_dotenv("/Users/ultimateslayer/Documents/the-extension-new/.env")

async def main():
    print("Testing codegen...")
    res = await _generate_checked(
        query="make background yellow",
        target_urls=["https://www.youtube.com/*"],
        extension_name="Yellow",
        provider="gemini"
    )
    if res is None:
        print("FAILED: Returned None")
    else:
        print("SUCCESS")
        print("JS length:", len(res.get("content.js", "")))
        print("CSS length:", len(res.get("content.css", "")))

if __name__ == "__main__":
    asyncio.run(main())
