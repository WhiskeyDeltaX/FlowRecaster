from fastapi import FastAPI, HTTPException, Request, status, Form
from pydantic import BaseModel
from subprocess import Popen, PIPE
import os
from dotenv import load_dotenv
import asyncio
import httpx  # to send async HTTP requests

load_dotenv()  # Load environment variables

app = FastAPI()

# Application version
__version__ = "1.0.0"

# Configuration management
config_file = "stream_config.json"

def load_config():
    with open("/flowrecaster_uuid.txt", 'r') as file:
        server_uuid = file.read()

    try:
        with open(config_file, 'r') as file:
            j = json.load(file)
            j["server_uuid"] = server_uuid
    except FileNotFoundError:
        return {
            "stream1_url": os.getenv("STREAM1_URL"),
            "stream2_url": os.getenv("STREAM2_URL"),
            "mp4_url": os.getenv("MP4_URL"),
            "active_source": "stream1",
            "secret_uuid": os.getenv("SECRET_UUID", "none"),
            "server_uuid": server_uuid
        }

def save_config(config):
    with open(config_file, 'w') as file:
        json.dump(config, file)

config = load_config()

# Global variables to manage the stream
ffmpeg_process = None
failure_count = 0
FAILURE_THRESHOLD = 6  # Number of allowed consecutive failures

class StreamData(BaseModel):
    identifier: str  # stream1, stream2, or mp4

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(check_stream())
    asyncio.create_task(report_system_status())

@app.on_event("shutdown")
async def shutdown_event():
    if ffmpeg_process:
        ffmpeg_process.terminate()

async def check_stream():
    global ffmpeg_process, failure_count
    while True:
        await asyncio.sleep(10)  # Non-blocking wait
        if ffmpeg_process and ffmpeg_process.poll() is not None:
            print("_Failure")
            failure_count += 1
            if failure_count >= FAILURE_THRESHOLD:
                print("Stream failure detected, switching to backup")
                await report_failure()
                switch_to_backup_stream()
        else:
            failure_count = 0  # Reset failure count if stream is active

async def report_failure():
    print("Report Failure")
    async with httpx.AsyncClient() as client:
        await client.post(f'{os.getenv("CENTRAL_SERVER_ADDRESS")}/report_failure', json={"stream_url": os.getenv("STREAM1_URL"), "failure_count": failure_count})

def switch_to_backup_stream():
    backup_stream_url = os.getenv("STREAM2_URL")
    start_youtube_stream_directly(backup_stream_url)

async def report_system_status():
    while True:
        await asyncio.sleep(60)  # Every minute
        print("Report System Status")
        async with httpx.AsyncClient() as client:
            await client.post(f'{os.getenv("CENTRAL_SERVER_ADDRESS")}/report_status', json={"status": "streaming"})

def start_youtube_stream_directly(stream_url):
    global ffmpeg_process
    if ffmpeg_process:
        ffmpeg_process.terminate()
    youtube_key = os.getenv("YOUTUBE_STREAM_KEY")
    command = f'ffmpeg -i {stream_url} -c copy -f flv rtmp://a.rtmp.youtube.com/live2/{youtube_key}'
    ffmpeg_process = Popen(command.split(), stdout=PIPE, stderr=PIPE)

@app.get("/start-youtube-stream/")
async def start_youtube_stream():
    source_url = config[config["active_source"] + "_url"]
    start_youtube_stream_directly(source_url)
    return {"message": "YouTube stream started"}

@app.get("/end-youtube-stream/")
async def end_youtube_stream():
    global ffmpeg_process
    if ffmpeg_process:
        ffmpeg_process.terminate()
        ffmpeg_process = None
    return {"message": "YouTube stream stopped"}

@app.post("/switch-stream/")
async def switch_stream(stream_data: StreamData):
    if stream_data.identifier in ["stream1", "stream2", "mp4"]:
        config["active_source"] = stream_data.identifier
        save_config(config)
        start_youtube_stream_directly(config[stream_data.identifier + "_url"])
        return {"message": f"Switched to {stream_data.identifier}"}
    raise HTTPException(status_code=404, detail="Invalid stream identifier")

@app.post("/set-stream-url/")
async def set_stream_url(stream_data: BaseModel):
    if stream_data.identifier in ["stream1", "stream2"]:
        config[stream_data.identifier + "_url"] = stream_data.url
        save_config(config)
        return {"message": f"{stream_data.identifier} URL updated"}
    raise HTTPException(status_code=404, detail="Invalid stream identifier")

@app.get("/version/")
async def get_version():
    return {"version": __version__}

@app.post("/validate_publish/")
async def validate_stream(name: str = Form(...)):
    # Implement your authentication logic here
    if config["secret_uuid"] != "none" and name == config["secret_uuid"]:
        return {"success": True}
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level='debug')
