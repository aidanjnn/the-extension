import asyncio
from dotenv import load_dotenv
from agentverse_app.codegen import run_codegen
from agentverse_app.messages import CodegenRequest, ExtensionSpec, BuildInfo

load_dotenv("/Users/ultimateslayer/Documents/the-extension-new/.env")

async def main():
    spec = ExtensionSpec(
        job_id="test",
        project_id="test-proj",
        name="test-ext",
        description="test description",
        target_urls=["https://www.youtube.com/*"],
        files_needed=["manifest.json", "content.js", "content.css"],
        behavior="make background yellow",
        verification_notes=[]
    )
    req = CodegenRequest(job_id="test", spec=spec, build=BuildInfo(job_id="test", project_id="test", query="make background yellow", provider="gemini"))
    res = await run_codegen(req)
    print("Files written:", res.written_files)

if __name__ == "__main__":
    asyncio.run(main())
