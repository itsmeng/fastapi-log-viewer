from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import boto3
from datetime import datetime, timedelta
from urllib.parse import quote_plus, unquote_plus
import json
import ast
import io

import logging

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_log_groups(limit: int = 50):
    client = boto3.client("logs")
    try:
        response = client.describe_log_groups(limit=limit)
        return response["logGroups"]
    except Exception as e:
        print(f"Error fetching log groups: {e}")
        return []

def get_log_streams(log_group_name: str, limit: int = 50):
    client = boto3.client("logs")
    try:
        response = client.describe_log_streams(logGroupName=log_group_name, limit=limit, orderBy='LastEventTime', descending=True)
        return response["logStreams"]
    except Exception as e:
        print(f"Error fetching log streams for {log_group_name}: {e}")
        return []

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    log_groups = get_log_groups()
    
    for group in log_groups:
        if 'creationTime' in group:
            timestamp_ms = group['creationTime']
            group['creationTime'] = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

    return templates.TemplateResponse("log_groups.html", {"request": request, "log_groups": log_groups})

@app.get("/log-group/{log_group_name:path}/stream/{log_stream_name:path}", response_class=HTMLResponse)
async def read_log_stream(request: Request, log_group_name: str, log_stream_name: str, lastEventTimestamp: int = None):
    decoded_log_group_name = unquote_plus(log_group_name)
    decoded_log_stream_name = unquote_plus(log_stream_name)
    log_events = get_log_events(decoded_log_group_name, decoded_log_stream_name, lastEventTimestamp)

    for event in log_events:
        timestamp = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        event['timestamp'] = timestamp

        message = event['message']
        LINE_THRESHOLD = 10  # Number of lines to consider a message "long"
        PREVIEW_CHAR_LIMIT = 80 # Character limit for the preview text

        def format_message(parsed_data, original_message):
            pretty_json = json.dumps(parsed_data, indent=2)
            num_lines = pretty_json.count('\n') + 1

            if num_lines > LINE_THRESHOLD:
                # Use the first line of the original raw message for the preview
                preview = original_message.split('\n')[0]
                if len(preview) > PREVIEW_CHAR_LIMIT:
                    preview = preview[:PREVIEW_CHAR_LIMIT] + "..."
                return f"<details><summary><span style=\"color: gray;\">Details:</span> {preview}</summary><pre><code>{pretty_json}</code></pre></details>"
            else:
                return f"<pre><code>{pretty_json}</code></pre>"

        try:
            # Try to parse as JSON first
            parsed_message = json.loads(message)
            event['message'] = format_message(parsed_message, message)
        except json.JSONDecodeError:
            try:
                # If not valid JSON, try to parse as a Python literal (e.g., dictionary with single quotes)
                parsed_message = ast.literal_eval(message)
                # If successful, convert it to JSON for consistent pretty-printing
                event['message'] = format_message(parsed_message, message)
            except (ValueError, SyntaxError):
                # If neither JSON nor Python literal, keep original message
                event['message'] = message

    return templates.TemplateResponse("log_events.html", {"request": request, "log_group_name": log_group_name, "log_stream_name": log_stream_name, "log_events": log_events})

@app.get("/log-group/{log_group_name:path}", response_class=HTMLResponse)
async def read_log_group(request: Request, log_group_name: str):
    log_group_name = unquote_plus(log_group_name)
    log_streams = get_log_streams(log_group_name, limit=50)

    for stream in log_streams:
        log_stream_name = stream.get("logStreamName", "N/A")
        last_event_timestamp = stream.get("lastEventTimestamp")
        if last_event_timestamp:
            last_event_time = datetime.fromtimestamp(last_event_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            last_event_time = "N/A"
        stream['lastEventTime'] = last_event_time

    return templates.TemplateResponse("log_streams.html", {"request": request, "log_group_name": log_group_name, "log_streams": log_streams})

def get_log_events(log_group_name: str, log_stream_name: str, lastEventTimestamp: int = None):
    client = boto3.client("logs")
    logging.info(f"Fetching log events for Log Group: {log_group_name}, Log Stream: {log_stream_name}")

    if lastEventTimestamp:
        end_time = lastEventTimestamp
        start_time = int((datetime.fromtimestamp(lastEventTimestamp / 1000) - timedelta(days=7)).timestamp() * 1000)
    else:
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)

    logging.info(f"Calling get_log_events with: logGroupName={log_group_name}, logStreamName={log_stream_name}, startTime={start_time}, endTime={end_time}, limit=300, startFromHead=False")
    response = client.get_log_events(
        logGroupName=log_group_name,
        logStreamName=log_stream_name,
        startTime=start_time,
        endTime=end_time,
        limit=300,  # Get the latest 300 events
        startFromHead=False  # Get latest events
    )
    logging.info(f"Log events response: {response}")
    return response["events"]




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
