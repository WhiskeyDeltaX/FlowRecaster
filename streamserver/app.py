from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from subprocess import Popen, PIPE
import os
from dotenv import load_dotenv
import time

load_dotenv()  # Load environment variables

app = FastAPI()

# Application version
__version__ = "1.0.0"

# Global variables to manage the stream
ffmpeg_process = None
failure_count = 0
FAILURE_THRESHOLD = 6  # Number of allowed consecutive failures

class StreamData(BaseModel):
    url: str

@app.on_event("startup")
async def startup_event(background_tasks: BackgroundTasks):
    background_tasks.add_task(check_stream)

async def check_stream():
    global ffmpeg_process, failure_count
    while True:
        time.sleep(10)  # Check every 10 seconds
        if ffmpeg_process and ffmpeg_process.poll() is not None:
            # Process has exited, increment failure count
            failure_count += 1
            if failure_count >= FAILURE_THRESHOLD:
                print("Stream failure detected, switching to backup")
                switch_to_backup_stream()
        else:
            # Reset failure count if stream is active
            failure_count = 0

def switch_to_backup_stream():
    global ffmpeg_process
    backup_stream_url = os.getenv("STREAM2_URL")  # Default to backup stream
    if ffmpeg_process:
        ffmpeg_process.terminate()
    start_youtube_stream_directly(backup_stream_url)

def start_youtube_stream_directly(stream_url):
    global ffmpeg_process
    youtube_key = os.getenv("YOUTUBE_STREAM_KEY")
    command = f'ffmpeg -i {stream_url} -c copy -f flv rtmp://a.rtmp.youtube.com/live2/{youtube_key}'
    ffmpeg_process = Popen(command.split(), stdout=PIPE, stderr=PIPE)

@app.post("/start-youtube-stream/")
async def start_youtube_stream():
    start_youtube_stream_directly(os.getenv("STREAM1_URL"))  # Start with main stream
    return {"message": "YouTube stream started"}

@app.post("/end-youtube-stream/")
async def end_youtube_stream():
    global ffmpeg_process
    if ffmpeg_process:
        ffmpeg_process.terminate()
        ffmpeg_process = None
    return {"message": "YouTube stream stopped"}

@app.post("/switch-stream/")
async def switch_stream(stream_data: StreamData):
    start_youtube_stream_directly(stream_data.url)
    return {"message": "Stream switched successfully"}

@app.get("/version/")
async def get_version():
    return {"version": __version__}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)