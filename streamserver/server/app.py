from fastapi import FastAPI, HTTPException, Request, status, Form
from pydantic import BaseModel
from subprocess import Popen, PIPE
import os
from dotenv import load_dotenv
import asyncio
import signal
import httpx  # to send async HTTP requests
import os.path
import psutil
from datetime import datetime
import subprocess
import json
import yt_dlp  # This is the module for downloading videos
import aiohttp
from datetime import datetime, timedelta
import logging
from typing import List, Dict

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables

app = FastAPI()

class YouTubeDownloadRequest(BaseModel):
    youtube_url: str

class StreamData(BaseModel):
    identifier: str  # stream1, stream2, or mp4
    url: str

class ConfigPair(BaseModel):
    configKey: str
    configValue: str

class ConfigRequest(BaseModel):
    config: List[ConfigPair]

# Application version
__version__ = "1.0.0"

# Configuration management
config_file = "stream_config.json"

def get_size(nbytes, suffix="bps"):
    """
    Scale bytes to its proper format
    e.g:
        1253656 => '1.20MB'
        1253656678 => '1.17GB'
    """
    factor = 1024
    for unit in ["", "k", "m", "g", "t", "p"]:
        if nbytes < factor:
            return f"{int(nbytes):.2f} {unit}{suffix}"
        nbytes /= factor

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

    if os.path.isfile("/flowrecaster_stream_key.txt"):
        with open("/flowrecaster_stream_key.txt", 'r') as file:
            stream_key = file.read().strip()
    else:
        stream_key = server_uuid

    if os.path.isfile("/flowrecaster_youtube_key.txt"):
        with open("/flowrecaster_youtube_key.txt", 'r') as file:
            youtube_key = file.read().strip()

            if youtube_key == "None":
                youtube_key = ""
    else:
        youtube_key = ""

    try:
        with open(config_file, 'r') as file:
            j = json.load(file)

            if not "server_uuid" in j:
                j["server_uuid"] = server_uuid
            
            if not "server_host" in j:
                j["server_host"] = server_host

            if not "youtube_key" in j:
                j["youtube_key"] = youtube_key

            if not "stream_key" in j:
                j["stream_key"] = stream_key

            return j
    except:
        return {
            "stream1_url": f"rtmp://localhost:8453/live/{stream_key}",
            "stream2_url": os.getenv("STREAM2_URL"),
            "mp4_url": os.getenv("MP4_URL", "/backup.mp4"),
            "active_source": "stream1",
            "server_uuid": server_uuid,
            "server_host": server_host,
            "stream_key": stream_key,
            "youtube_key": youtube_key
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

@app.on_event("startup")
async def startup_event():
    global config
    if "should_be_streaming" in config and config["should_be_streaming"]:
        source_url = config[config["active_source"] + "_url"]
        await start_youtube_stream_directly(source_url)

    asyncio.create_task(check_stream())
    asyncio.create_task(report_system_status())
    asyncio.create_task(restart_stream_every_30_minutes())
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

async def restart_stream_every_30_minutes():
    global ffmpeg_process, config
    last_known_source = config['active_source']  # Track the last known active source

    while True:
        await asyncio.sleep(60*30)  # Non-blocking wait

        if ffmpeg_process:
            current_source = config['active_source']
            current_url = config[f'{current_source}_url']
            await start_youtube_stream_directly(current_url)

async def check_stream():
    global ffmpeg_process, config, failure_count
    last_known_source = config['active_source']  # Track the last known active source

    while True:
        await asyncio.sleep(3)  # Non-blocking wait

        current_source = config['active_source']
        current_url = config[f'{current_source}_url']
        
        if ffmpeg_process:
            if not await find_ffmpeg_processes():
                failure_count += 1

                if failure_count >= FAILURE_THRESHOLD:
                    await start_youtube_stream_directly(current_url)
                    failure_count = 0

                continue

            if current_source != 'mp4':
                try:
                    stream_live = await is_hls_stream_live(convert_url_rtmp_to_hls(current_url))
                except Exception as e:
                    print("failed to see if URL was live")
                    stream_live = False

                if not stream_live:
                    print(f"{current_source} failure detected.")
                    failure_count += 1
                    if failure_count >= FAILURE_THRESHOLD:
                        print(f"{current_source} failure detected for too long. Switching to MP4.")
                        await switch_to_backup_stream()
                        await report_failure()
                        
                        # Check if the stream comes back online
                        while not await is_hls_stream_live(convert_url_rtmp_to_hls(current_url)):
                            print ("Stream is still not live yet")
                            await asyncio.sleep(5)
                            # Check if the active source has been changed externally
                            if config['active_source'] != last_known_source:
                                print(f"Active source changed externally from {last_known_source} to {config['active_source']}")
                                break  # Break the inner loop to continue with the main loop
                                
                        if config['active_source'] == last_known_source:
                            # If the loop exits naturally, the original stream is back
                            print(f"{current_source} is back online, switching back from backup mp4")
                            await switch_to_original_stream(current_source)
                            failure_count = 0  # Reset failure count after recovery

                else:
                    failure_count = 0  # Reset failure count if stream is active

            # Update last known source for the next iteration
            last_known_source = config['active_source']
        elif "should_be_streaming" in config and config["should_be_streaming"]:
            failure_count += 1
            if failure_count >= FAILURE_THRESHOLD:
                await start_youtube_stream_directly(current_url)
                failure_count = 0

async def switch_to_backup_stream():
    await start_youtube_stream_directly(config['mp4_url'])

async def switch_to_original_stream(original_stream):
    global config
    config['active_source'] = original_stream
    save_config(config)
    await start_youtube_stream_directly(config[f'{original_stream}_url'])

async def report_failure():
    print("Report Failure")
    async with httpx.AsyncClient() as client:
        await client.post(f'{config["server_host"]}/api/v1/report_failure', json={"stream_url": os.getenv("STREAM1_URL"), "failure_count": failure_count})

def is_file_recent(filepath, max_age_seconds):
    """Check if the file was modified within the last `max_age_seconds` seconds."""
    if not os.path.exists(filepath):
        return False
    file_mod_time = os.path.getmtime(filepath)
    current_time = time.time()
    return (current_time - file_mod_time) < max_age_seconds

async def is_hls_stream_live(url, max_age_seconds=10):
    print("Checking URL:", url)
    if not url:
        return False
    
    """Check if the HLS stream is live by making a HEAD request to the playlist URL."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.head(url) as response:
                if response.status == 200:
                    last_modified = response.headers.get('Last-Modified')
                    print("200", last_modified)
                    if last_modified:
                        last_modified_time = datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
                        current_time = datetime.utcnow()
                        print("last Mod", last_modified_time, "cur", current_time)
                        return (current_time - last_modified_time) < timedelta(seconds=max_age_seconds)
        except Exception as e:
            print("Failed with", e)
            return False
    return False

def convert_url_rtmp_to_hls(rtmp_url):
    """
    Convert an RTMP URL to an HLS URL.
    
    Parameters:
        rtmp_url (str): The RTMP URL to convert.
    
    Returns:
        str: The corresponding HLS URL.
    """
    if not rtmp_url or not rtmp_url.startswith('rtmp://'):
        return ""

    # Extract parts of the RTMP URL
    parts = rtmp_url.split('/')
    if len(parts) < 5:
        return ""

    host = parts[2]  # Extract the host
    stream_id = parts[-1]  # Extract the stream ID

    host = host.split(":")[0]

    if host == "localhost":
        protocol = 'http://'
        host = "127.0.0.1"
    else:
        protocol = 'https://'

    # Construct the HLS URL
    hls_url = f"{protocol}{host}/streams/hls/{stream_id}.m3u8"
    return hls_url

async def report_system_status():
    global config
    global ffmpeg_process

    net_start = datetime.now()
    net_io = psutil.net_io_counters()
    init_bytes_sent = net_io.bytes_sent
    init_bytes_recv = net_io.bytes_recv

    while True:
        await asyncio.sleep(30)  # Report every minute
        print("Reporting System Status")
        
        try:
            # Collect system metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            ram_usage = psutil.virtual_memory().percent
            net_io = psutil.net_io_counters()

            net_now = datetime.now()
            duration_seconds = (net_now - net_start).total_seconds()

            bytes_sent = (net_io.bytes_sent - init_bytes_sent) / duration_seconds
            bytes_recv = (net_io.bytes_recv - init_bytes_recv) / duration_seconds

            init_bytes_sent = bytes_sent
            init_bytes_recv = bytes_recv
            net_start = net_now
            
            # Check FFmpeg stream status
            ffmpeg_alive = ffmpeg_process and ffmpeg_process.returncode is None

            print("ffmpeg?", ffmpeg_process)
            
            if ffmpeg_process:
                print("Poll?", ffmpeg_process.returncode)

            print("Checking URLs")
            stream1_live = await is_hls_stream_live(convert_url_rtmp_to_hls(config['stream1_url']))
            stream2_live = await is_hls_stream_live(convert_url_rtmp_to_hls(config['stream2_url']))
            
            # Prepare the payload
            payload = {
                "server_uuid": config["server_uuid"],
                "cpu_usage": cpu_usage,
                "ram_usage": ram_usage,
                "bytes_sent": get_size(bytes_sent),
                "bytes_recv": get_size(bytes_recv),
                "bytes_sent_raw": bytes_sent,
                "bytes_recv_raw": bytes_recv,
                "selected_source": config["active_source"],
                "youtube_key": config["youtube_key"],
                "ffmpeg_alive": ffmpeg_alive or False,
                "stream1_live": stream1_live,
                "stream2_live": stream2_live,
                "stream1_url": config['stream1_url'] or "",
                "stream2_url": config['stream2_url'] or "",
                "noise_reduction": config.get("noise_reduction", "0")
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
        except Exception as e:
            print("Main status look had failure", e)

async def is_stream_live(stream_url):
    if not stream_url:
        return False

    """ Check if the given stream URL is live using ffprobe. """
    try:
        # Run ffprobe to check the stream status
        # ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1
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

async def start_youtube_stream_directly(stream_url):
    global ffmpeg_process, config

    print("Starting stream direct", stream_url)

    config["should_be_streaming"] = True
    save_config(config)

    if ffmpeg_process:
        try:
            ffmpeg_process.kill()
            await asyncio.sleep(1)
            ffmpeg_process = None
            await kill_ffmpeg_processes()

            await asyncio.sleep(2)
        except Exception as e:
            print("Failed to kill ffmpeg", e)
        print("Should be dead")

    youtube_key = config["youtube_key"]

    if not youtube_key:
        return False

    cv = "copy"
    ca = "aac"

    additional_commands = []
    more_additional_commands = []

    additional_commands.append('-af "loudnorm=I=-16:TP=-1.5:LRA=11" -ac 1')

    if not stream_url.endswith(".mp4"):
        if "noise_reduction" in config and config["noise_reduction"]:
            nr_amount = 12

            try:
                nr_amount = int(config["noise_reduction"])
                if nr_amount > 97:
                    nr_amount = 97
                elif nr_amount < 0:
                    nr_amount = 0
            except:
                pass

            if nr_amount > 0:
                additional_commands.append(f'-af "afftdn=nr={nr_amount}"')
                ca = "aac"
    else:
        more_additional_commands.append("-stream_loop -1")

    command = f'/usr/bin/ffmpeg -re {" ".join(more_additional_commands)} -i {stream_url} {" ".join(additional_commands)} -c:v {cv} -c:a {ca} -g 60 -f flv -x264-params keyint=60:min-keyint=60:no-scenecut=1 -drop_pkts_on_overflow 1 -attempt_recovery 1 -recovery_wait_time 1 rtmp://a.rtmp.youtube.com/live2/{youtube_key}'
    print("Final Command", command)

    # ffmpeg_process = Popen(command, stdout=PIPE, stderr=PIPE, bufsize=1,
    #     universal_newlines=True, shell=True)

    try:
        ffmpeg_process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Log the output from FFmpeg process
        asyncio.create_task(log_ffmpeg_output(ffmpeg_process))

    except Exception as e:
        logger.exception("Failed to start FFmpeg process.")
        raise HTTPException(status_code=500, detail=str(e))

    # Kick off the log monitoring as a background task
    # asyncio.create_task(log_ffmpeg_output(ffmpeg_process))

async def log_ffmpeg_output(process):
    """ Log output from FFmpeg to check for any errors or important information. """
    async for line in process.stderr:
        if line:
            logger.error(f"FFMPEG: {line.decode().strip()}")
    await process.wait()

@app.get("/start-youtube-stream/")
async def start_youtube_stream():
    global config

    source_url = config[config["active_source"] + "_url"]
    await start_youtube_stream_directly(source_url)

    config["should_be_streaming"] = True
    save_config(config)

    return {"message": "YouTube stream started"}

@app.get("/stop-youtube-stream/")
async def stop_youtube_stream():
    global ffmpeg_process
    if ffmpeg_process:
        print("Killing")
        ffmpeg_process.kill()
        ffmpeg_process = None
        await kill_ffmpeg_processes()

        config["should_be_streaming"] = False
        save_config(config)

        await asyncio.sleep(2)
        print("Should be dead")

    return {"message": "YouTube stream stopped"}

@app.post("/switch-stream/")
async def switch_stream(stream_data: StreamData):
    if stream_data.identifier in ["stream1", "stream2", "mp4"]:
        config["active_source"] = stream_data.identifier
        save_config(config)
        await start_youtube_stream_directly(config[stream_data.identifier + "_url"])
        return {"message": f"Switched to {stream_data.identifier}"}
    raise HTTPException(status_code=404, detail="Invalid stream identifier")

@app.post("/set-stream-url/")
async def set_stream_url(stream_data: StreamData):
    global config

    if stream_data.identifier in ["stream1", "stream2"]:
        config[stream_data.identifier + "_url"] = stream_data.url
        save_config(config)
        print("Config updated", config)
        return {"message": f"{stream_data.identifier} URL updated"}
    raise HTTPException(status_code=404, detail="Invalid stream identifier")

@app.post("/set-config/")
async def set_stream_url(config_data: ConfigRequest):
    global config, ffmpeg_process

    for pair in config_data.config:
        config[pair.configKey] = pair.configValue

    save_config(config)

    if ffmpeg_process:
        await start_youtube_stream_directly(config[config["active_source"] + "_url"])

    return {"message": "Configuration updated"}

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

        if ffmpeg_process:
            # Start streaming the newly downloaded video
            await start_youtube_stream_directly(config['mp4_url'])

        return {"message": "YouTube video downloaded and streaming started", "mp4_url": config['mp4_url']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/version/")
async def get_version():
    return {"version": __version__}

@app.post("/validate_publish/")
async def validate_stream(name: str = Form(...)):
    # Implement your authentication logic here
    if name == config["stream_key"]:
        return {"success": True}
    else:
        return {"success": True}
        # raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

async def kill_ffmpeg_processes():
    """Kill all running ffmpeg processes."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'ffmpeg' or (proc.info['cmdline'] and '/usr/bin/ffmpeg' in proc.info['cmdline']):
                logger.info(f"Killing ffmpeg process: {proc.info}")
                proc.kill()
                proc.wait()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

async def find_ffmpeg_processes():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'ffmpeg' or (proc.info['cmdline'] and '/usr/bin/ffmpeg' in proc.info['cmdline']):
                logger.info(f"Checking ffmpeg process: {proc.info}")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    return False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level='debug')
