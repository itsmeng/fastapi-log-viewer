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
import os

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

FAVORITES_FILE = "favorites.json"

def read_favorites():
    if not os.path.exists(FAVORITES_FILE):
        return {"log_groups": [], "log_streams": {}}
    with open(FAVORITES_FILE, "r") as f:
        favorites = json.load(f)
    # Ensure log_streams is a dictionary
    if "log_streams" not in favorites or not isinstance(favorites["log_streams"], dict):
        favorites["log_streams"] = {}
    return favorites

def write_favorites(favorites):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favorites, f, indent=4)

templates = Jinja2Templates(directory="templates")

def get_log_groups(limit: int = 50):
    client = boto3.client("logs")
    response = client.describe_log_groups(limit=limit)
    return response["logGroups"]

def get_log_streams(log_group_name: str, limit: int = 50):
    client = boto3.client("logs")
    response = client.describe_log_streams(logGroupName=log_group_name, limit=limit, orderBy='LastEventTime', descending=True)
    return response["logStreams"]

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        log_groups = get_log_groups()
    except Exception as e:
        error_message = f"Error fetching log groups: {e}"
        return templates.TemplateResponse("error.html", {"request": request, "error_message": error_message, "back_url": "/"})

    favorites = read_favorites()
    favorite_log_groups = favorites.get("log_groups", [])

    for group in log_groups:
        if 'creationTime' in group:
            timestamp_ms = group['creationTime']
            group['creationTime'] = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
        group['is_favorite'] = group['logGroupName'] in favorite_log_groups

    return templates.TemplateResponse("log_groups.html", {"request": request, "log_groups": log_groups, "favorites": favorites})

@app.post("/favorite/log-group/{log_group_name:path}")
async def toggle_favorite_log_group(log_group_name: str):
    decoded_log_group_name = unquote_plus(log_group_name)
    favorites = read_favorites()
    if decoded_log_group_name in favorites["log_groups"]:
        favorites["log_groups"].remove(decoded_log_group_name)
    else:
        favorites["log_groups"].append(decoded_log_group_name)
    write_favorites(favorites)
    return {"status": "success", "favorites": favorites}

@app.post("/favorite/log-group/{log_group_name:path}/stream/{log_stream_name:path}")
async def toggle_favorite_log_stream(log_group_name: str, log_stream_name: str):
    decoded_log_group_name = unquote_plus(log_group_name)
    decoded_log_stream_name = unquote_plus(log_stream_name)
    favorites = read_favorites()
    
    group_streams = favorites.get("log_streams", {})
    if decoded_log_group_name not in group_streams:
        group_streams[decoded_log_group_name] = []

    if decoded_log_stream_name in group_streams[decoded_log_group_name]:
        group_streams[decoded_log_group_name].remove(decoded_log_stream_name)
    else:
        group_streams[decoded_log_group_name].append(decoded_log_stream_name)
    
    favorites["log_streams"] = group_streams
    write_favorites(favorites)
    return {"status": "success", "favorites": favorites}


    
    favorites = read_favorites()
    is_favorite_stream = decoded_log_stream_name in favorites.get("log_streams", {}).get(decoded_log_group_name, [])

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

    return templates.TemplateResponse("log_events.html", {"request": request, "log_group_name": log_group_name, "log_stream_name": log_stream_name, "log_events": log_events, "is_favorite_stream": is_favorite_stream, "next_forward_token": next_forward_token})

def calculate_time_range(time_span: str = None, start_time_abs: str = None, end_time_abs: str = None, latest_event_timestamp_ms: int = None):
    if latest_event_timestamp_ms:
        end_time = datetime.fromtimestamp(latest_event_timestamp_ms / 1000)
    elif end_time_abs:
        end_time = datetime.fromisoformat(end_time_abs)
    else:
        end_time = datetime.now()

    if start_time_abs:
        start_time = datetime.fromisoformat(start_time_abs)
    elif time_span == "1hr":
        start_time = end_time - timedelta(hours=1)
    elif time_span == "3hr":
        start_time = end_time - timedelta(hours=3)
    elif time_span == "12hr":
        start_time = end_time - timedelta(hours=12)
    elif time_span == "1day":
        start_time = end_time - timedelta(days=1)
    else: # Default to last 7 days if no specific time span or absolute times are provided
        start_time = end_time - timedelta(days=7)

    return int(start_time.timestamp() * 1000), int(end_time.timestamp() * 1000)

@app.get("/log-group/{log_group_name:path}/stream/{log_stream_name:path}", response_class=HTMLResponse)
@app.get("/log-group/{log_group_name:path}/stream/{log_stream_name:path}", response_class=HTMLResponse)
async def read_log_stream(request: Request, log_group_name: str, log_stream_name: str, time_span: str = None, start_time_abs: str = None, end_time_abs: str = None, nextToken: str = None):
    decoded_log_group_name = unquote_plus(log_group_name)
    decoded_log_stream_name = unquote_plus(log_stream_name)
    
    log_events = []
    next_forward_token = None
    
    try:
        # Get the last event timestamp from describe_log_streams
        log_streams_info = get_log_streams(decoded_log_group_name, limit=1)
        latest_event_timestamp_from_metadata = None
        if log_streams_info and log_streams_info[0].get('lastEventTimestamp'):
            latest_event_timestamp_from_metadata = log_streams_info[0]['lastEventTimestamp']

        if time_span is None and start_time_abs is None and end_time_abs is None:
            # Default behavior: get the latest event and load 7 days from it
            if latest_event_timestamp_from_metadata:
                end_time_ms = latest_event_timestamp_from_metadata
                start_time_ms = int((datetime.fromtimestamp(latest_event_timestamp_from_metadata / 1000) - timedelta(days=7)).timestamp() * 1000)
            else:
                # Fallback if no events are found, use current time - 7 days
                start_time_ms, end_time_ms = calculate_time_range(time_span, start_time_abs, end_time_abs)
        elif time_span is not None and start_time_abs is None and end_time_abs is None:
            # If a time_span is provided, use the latest event from metadata to set the end_time
            if latest_event_timestamp_from_metadata:
                start_time_ms, end_time_ms = calculate_time_range(time_span, latest_event_timestamp_ms=latest_event_timestamp_from_metadata)
            else:
                # Fallback if no events are found, use current time as end_time
                start_time_ms, end_time_ms = calculate_time_range(time_span, start_time_abs, end_time_abs)
        else:
            start_time_ms, end_time_ms = calculate_time_range(time_span, start_time_abs, end_time_abs)

        log_events, next_forward_token = get_log_events(decoded_log_group_name, decoded_log_stream_name, start_time_ms, end_time_ms, nextToken)

        # Peek ahead to see if the next token will return any events.
        if next_forward_token:
            peek_events, _ = get_log_events(decoded_log_group_name, decoded_log_stream_name, start_time_ms, end_time_ms, next_forward_token)
            if not peek_events:
                next_forward_token = None
    except Exception as e:
        error_message = f"Error fetching log events for {decoded_log_group_name}/{decoded_log_stream_name}: {e}"
        # Determine the back URL based on the current context
        back_url = f"/log-group/{quote_plus(log_group_name)}"
        return templates.TemplateResponse("error.html", {"request": request, "error_message": error_message, "back_url": back_url})

    favorites = read_favorites()
    is_favorite_stream = decoded_log_stream_name in favorites.get("log_streams", {}).get(decoded_log_group_name, [])

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

    return templates.TemplateResponse("log_events.html", {
        "request": request, 
        "log_group_name": log_group_name, 
        "log_stream_name": log_stream_name, 
        "log_events": log_events, 
        "is_favorite_stream": is_favorite_stream, 
        "next_forward_token": next_forward_token, 
        "start_time_display": datetime.fromtimestamp(start_time_ms / 1000).strftime('%Y-%m-%d %H:%M:%S'), 
        "end_time_display": datetime.fromtimestamp(end_time_ms / 1000).strftime('%Y-%m-%d %H:%M:%S'),
        "start_time_ms": start_time_ms,
        "end_time_ms": end_time_ms
    })



@app.get("/api/log-events")
async def get_more_log_events(log_group_name: str, log_stream_name: str, start_time_ms: int, end_time_ms: int, nextToken: str = None):
    decoded_log_group_name = unquote_plus(log_group_name)
    decoded_log_stream_name = unquote_plus(log_stream_name)

    log_events, next_forward_token = get_log_events(decoded_log_group_name, decoded_log_stream_name, start_time_ms, end_time_ms, nextToken)

    formatted_events = []
    for event in log_events:
        timestamp = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        event['timestamp'] = timestamp

        message = event['message']
        LINE_THRESHOLD = 10
        PREVIEW_CHAR_LIMIT = 80

        def format_message(parsed_data, original_message):
            pretty_json = json.dumps(parsed_data, indent=2)
            num_lines = pretty_json.count('\n') + 1

            if num_lines > LINE_THRESHOLD:
                preview = original_message.split('\n')[0]
                if len(preview) > PREVIEW_CHAR_LIMIT:
                    preview = preview[:PREVIEW_CHAR_LIMIT] + "..."
                return f"<details><summary><span style=\"color: gray;\">Details:</span> {preview}</summary><pre><code>{pretty_json}</code></pre></details>"
            else:
                return f"<pre><code>{pretty_json}</code></pre>"

        try:
            parsed_message = json.loads(message)
            event['message'] = format_message(parsed_message, message)
        except json.JSONDecodeError:
            try:
                parsed_message = ast.literal_eval(message)
                event['message'] = format_message(parsed_message, message)
            except (ValueError, SyntaxError):
                event['message'] = message
        formatted_events.append(event)

    return {"log_events": formatted_events, "next_forward_token": next_forward_token}

@app.get("/log-group/{log_group_name:path}", response_class=HTMLResponse)
async def read_log_group(request: Request, log_group_name: str):
    log_group_name = unquote_plus(log_group_name)
    # Ensure log_group_name starts with a slash for AWS API
    if not log_group_name.startswith('/'):
        log_group_name = '/' + log_group_name
    try:
        log_streams = get_log_streams(log_group_name, limit=50)
    except Exception as e:
        error_message = f"Error fetching log streams for {log_group_name}: {e}"
        return templates.TemplateResponse("error.html", {"request": request, "error_message": error_message, "back_url": "/"})

    favorites = read_favorites()
    favorite_streams_for_group = favorites.get("log_streams", {}).get(log_group_name, [])

    for stream in log_streams:
        log_stream_name = stream.get("logStreamName", "N/A")
        last_event_timestamp = stream.get("lastEventTimestamp")
        if last_event_timestamp:
            last_event_time = datetime.fromtimestamp(last_event_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            last_event_time = "N/A"
        stream['lastEventTime'] = last_event_time
        stream['is_favorite'] = log_stream_name in favorite_streams_for_group

    return templates.TemplateResponse("log_streams.html", {"request": request, "log_group_name": log_group_name, "log_streams": log_streams})

def get_log_events(log_group_name: str, log_stream_name: str, start_time_ms: int, end_time_ms: int, nextToken: str = None, limit: int = 300, startFromHead: bool = False):
    client = boto3.client("logs")
    logging.info(f"Fetching log events for Log Group: {log_group_name}, Log Stream: {log_stream_name}")

    while True:
        params = {
            "logGroupName": '/' + log_group_name.lstrip('/'),
            "logStreamName": log_stream_name.lstrip('/'),
            "startTime": start_time_ms,
            "endTime": end_time_ms,
            "limit": limit,
            "startFromHead": startFromHead
        }
        if nextToken:
            params["nextToken"] = nextToken

        logging.info(f"Calling get_log_events with: {params}")
        response = client.get_log_events(**params)
        logging.info(f"Log events response: {response}")

        events = response["events"]
        next_token = response.get("nextForwardToken")

        if events:
            return events, next_token

        if not next_token or next_token == nextToken:
            return [], None

        nextToken = next_token




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
