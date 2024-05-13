from fastapi import FastAPI, HTTPException, Request, status, Form
from pydantic import BaseModel
from subprocess import Popen, PIPE
import os
from dotenv import load_dotenv
import asyncio
import httpx  # to send async HTTP requests
import os.path
import psutil
from datetime import datetime
import subprocess
import json
import yt_dlp  # This is the module for downloading videos

load_dotenv()  # Load environment variables

app = FastAPI()

class YouTubeDownloadRequest(BaseModel):
    youtube_url: str

# Application version
__version__ = "1.0.0"

# Configuration management
config_file = "stream_config.json"

def load_config():
    if os.path.isfile("/flowrecaster_uuid.txt"):
        with open("/flowrecaster_uuid.txt", 'r') as file:
            server_uuid = file.read().strip()
    else:
        server_uuid = "None"

    if os.path.isfile("/flowrecaster_host.txt"):
        with open("/flowrecaster_host.txt", 'r') as file:
            server_host = file.read().strip()
    else:
        server_host = "http://localhost"

    try:
        with open(config_file, 'r') as file:
            j = json.load(file)
            j["server_uuid"] = server_uuid
            j["server_host"] = server_host
            j["stream1_url"] = f"rtmp://localhost:8453/live/{server_uuid}"
            j["stream1_url"] = f"video.mp4"
            return j
    except:
        return {
            "stream1_url": f"rtmp://localhost:8453/live/{server_uuid}",
            "stream2_url": os.getenv("STREAM2_URL"),
            "mp4_url": os.getenv("MP4_URL", "video.mp4"),
            "active_source": "stream1",
            "server_uuid": server_uuid,
            "server_host": server_host
        }

def save_config(config):
    with open(config_file, 'w') as file:
        json.dump(config, file)

config = load_config()

print("Config", config)

# Global variables to manage the stream
ffmpeg_process = None
failure_count = 0
FAILURE_THRESHOLD = 3  # Number of allowed consecutive failures

class StreamData(BaseModel):
    identifier: str  # stream1, stream2, or mp4

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(check_stream())
    asyncio.create_task(report_system_status())
    await notify_server_online()

@app.on_event("shutdown")
async def shutdown_event():
    if ffmpeg_process:
        ffmpeg_process.terminate()

async def notify_server_online():
    """ Notify the central server that this node is online. """
    payload = {
        "server_uuid": config["server_uuid"]
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f'{config["server_host"]}/api/v1/streamservers/server_online', json=payload)
            response.raise_for_status()  # Will raise an exception for 4XX/5XX responses
        except httpx.HTTPError as e:
            print(f"Failed to notify server: {e}")

async def check_stream():
    global ffmpeg_process, config, failure_count
    last_known_source = config['active_source']  # Track the last known active source

    while True:
        await asyncio.sleep(5)  # Non-blocking wait
        current_source = config['active_source']
        current_url = config[f'{current_source}_url']

        if current_source != 'mp4':
            stream_live = await is_stream_live(current_url)
            if not stream_live:
                print(f"{current_source} failure detected, switching to backup mp4")
                failure_count += 1
                if failure_count >= FAILURE_THRESHOLD:
                    switch_to_backup_stream()
                    await report_failure()
                    
                    # Check if the stream comes back online
                    while not await is_stream_live(current_url):
                        await asyncio.sleep(5)
                        # Check if the active source has been changed externally
                        if config['active_source'] != last_known_source:
                            print(f"Active source changed externally from {last_known_source} to {config['active_source']}")
                            break  # Break the inner loop to continue with the main loop
                            
                    if config['active_source'] == last_known_source:
                        # If the loop exits naturally, the original stream is back
                        print(f"{current_source} is back online, switching back from backup mp4")
                        switch_to_original_stream(current_source)
                        failure_count = 0  # Reset failure count after recovery

            else:
                failure_count = 0  # Reset failure count if stream is active

        # Update last known source for the next iteration
        last_known_source = config['active_source']

def switch_to_backup_stream():
    start_youtube_stream_directly(config['mp4_url'])

def switch_to_original_stream(original_stream):
    global config
    config['active_source'] = original_stream
    save_config(config)
    start_youtube_stream_directly(config[f'{original_stream}_url'])

async def report_failure():
    print("Report Failure")
    async with httpx.AsyncClient() as client:
        await client.post(f'{config["server_host"]}/api/v1/report_failure', json={"stream_url": os.getenv("STREAM1_URL"), "failure_count": failure_count})

async def report_system_status():
    while True:
        await asyncio.sleep(30)  # Report every minute
        print("Reporting System Status")
        
        # Collect system metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_usage = psutil.virtual_memory().percent
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent
        bytes_recv = net_io.bytes_recv
        
        # Check FFmpeg stream status
        ffmpeg_alive = not (ffmpeg_process and ffmpeg_process.poll() is not None)

        stream1_live = await is_stream_live(config['stream1_url'])
        stream2_live = await is_stream_live(config['stream2_url'])
        
        # Prepare the payload
        payload = {
            "server_uuid": config["server_uuid"],
            "cpu_usage": cpu_usage,
            "ram_usage": ram_usage,
            "bytes_sent": bytes_sent,
            "bytes_recv": bytes_recv,
            "selected_source": config["active_source"],
            "youtube_stream_key": os.getenv("YOUTUBE_STREAM_KEY", ""),
            "ffmpeg_alive": ffmpeg_alive,
            "stream1_live": stream1_live,
            "stream2_live": stream2_live,
        }

        print("Sending payload", payload)
        
        # Send the status to the central server
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f'{config["server_host"]}/api/v1/streamservers/report_status', json=payload)
                response.raise_for_status()  # Will raise an exception for 4XX/5XX responses
                print(f"Status reported successfully at {datetime.now()}")
            except httpx.HTTPError as e:
                print(f"Failed to report status: {e}")

async def is_stream_live(stream_url):
    """ Check if the given stream URL is live using ffprobe. """
    try:
        # Run ffprobe to check the stream status
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", 
             "default=noprint_wrappers=1:nokey=1", stream_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10  # Set a timeout to avoid hanging
        )
        # If ffprobe runs successfully, the stream is live
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        # If ffprobe times out, the stream is not live
        return False
    except:
        return False

def start_youtube_stream_directly(stream_url):
    global ffmpeg_process
    if ffmpeg_process:
        ffmpeg_process.terminate()
    youtube_key = os.getenv("YOUTUBE_STREAM_KEY")
    command = f'ffmpeg -re -i {stream_url} -c copy -f flv rtmp://a.rtmp.youtube.com/live2/{youtube_key}'
    ffmpeg_process = Popen(command.split(), stdout=PIPE, stderr=PIPE, bufsize=1, universal_newlines=True)

@app.get("/start-youtube-stream/")
async def start_youtube_stream():
    source_url = config[config["active_source"] + "_url"]
    start_youtube_stream_directly(source_url)
    return {"message": "YouTube stream started"}

@app.get("/stop-youtube-stream/")
async def stop_youtube_stream():
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

@app.post("/download-youtube-video/")
async def download_youtube_video(request: YouTubeDownloadRequest):
    # Specify the output template and options for yt-dlp
    ydl_opts = {
        'format': 'best',
        'outtmpl': '/yt_video.mp4',  # Set output file template
        'merge_output_format': 'mp4',  # Ensure the output is MP4 if video and audio are separate
    }

    try:
        # Use yt-dlp to download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.youtube_url])

        # Update the configuration to use the new MP4 file
        global config
        config['mp4_url'] = '/yt_video.mp4'
        save_config(config)

        # Start streaming the newly downloaded video
        start_youtube_stream_directly(config['mp4_url'])

        return {"message": "YouTube video downloaded and streaming started", "mp4_url": config['mp4_url']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/version/")
async def get_version():
    return {"version": __version__}

@app.post("/validate_publish/")
async def validate_stream(name: str = Form(...)):
    # Implement your authentication logic here
    if name == config["server_uuid"]:
        return {"success": True}
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level='debug')
