# Project Overview

This is a Python FastAPI application designed to provide a local web interface for viewing AWS CloudWatch Logs. It allows users to browse log groups, log streams, and view individual log events.

## Key Features & Functionality

*   **Log Browsing:** Displays AWS CloudWatch Log Groups and their associated Log Streams.
*   **Log Event Viewing:** Fetches and displays log events for selected log streams.
*   **Intelligent Message Formatting:** Automatically detects and pretty-prints JSON and Python dictionary-like log messages, making them more readable.
*   **Collapsible Log Entries:** Long log messages are collapsed by default, showing a single-line preview. Users can expand/collapse individual messages.
*   **"Expand All" / "Collapse All" Functionality:** A button is provided on the log events page to toggle the expanded state of all log messages.
*   **Favorites System:** Users can mark log groups and log streams as favorites for quick access from the main page. Favorites are stored locally in `favorites.json`.
*   **Flexible Time Range Selection:**
    *   **Relative Time:** Users can select predefined relative time spans (e.g., "Last 1 Hour", "Last 1 Day"). These time spans are calculated relative to the *latest log event* in the stream, not the current time.
    *   **Absolute Time:** Users can specify custom start and end datetimes.
    *   **Default Behavior:** If no time range is specified, the application defaults to showing logs for the 7-day period ending at the latest log event's timestamp. If no events are found, it defaults to the last 7 days from the current time.
*   **Pagination ("Load More"):** Log events are loaded in batches (300 events per request), with a "Load More" button to fetch older events.
*   **Centralized Error Handling:** All `boto3` API call failures are caught and redirected to a dedicated `error.html` page, providing a user-friendly error message and a "Go Back" button.

## Technology Stack

*   **Backend:** Python 3.x, FastAPI
*   **Frontend:** HTML, CSS (Pico.css), JavaScript (Vanilla JS)
*   **AWS Integration:** `boto3` library for interacting with CloudWatch Logs API.
*   **Templating:** Jinja2

## Project Structure & Important Files

*   `main.py`: Main FastAPI application logic, API endpoints, and core functions for interacting with AWS and managing favorites.
*   `templates/`: Directory containing Jinja2 HTML templates.
    *   `log_groups.html`: Displays log groups and favorite log groups.
    *   `log_streams.html`: Displays log streams for a selected log group.
    *   `log_events.html`: Displays log events for a selected log stream, including time range controls and pretty-printing.
    *   `error.html`: Dedicated template for displaying error messages.
*   `favorites.json`: A simple JSON file used to store user's favorited log groups and log streams. This file is automatically created and managed by the application.
*   `app.log`: Application log file for internal debugging. This file is included in `.gitignore` to prevent accidental commits.
*   `.gitignore`: Configured to ignore virtual environment files, `app.log`, and other common development artifacts.

## Conventions & Best Practices

*   **AWS Log Group Names:** CloudWatch Log Group names typically start with a leading slash (e.g., `/aws/lambda/my-function`). The application handles ensuring this format for API calls.
*   **AWS Log Stream Names:** CloudWatch Log Stream names typically do *not* start with a leading slash. The application handles ensuring this format for API calls.
*   **Error Handling:** `boto3` calls are wrapped in `try-except` blocks to catch exceptions and redirect to a centralized error page.
*   **Path Handling:** `urllib.parse.unquote_plus` is used to decode URL-encoded path parameters.
*   **Favorites Storage:** Favorites are stored in a simple `favorites.json` file, avoiding the need for a database.
*   **FastAPI Routing:** The order of route definitions in `main.py` is important. More specific routes (e.g., `/log-group/{log_group_name:path}/stream/{log_stream_name:path}`) must be defined before more general routes (e.g., `/log-group/{log_group_name:path}`) to ensure correct matching.

## Development Notes

*   The virtual environment (`venv/`) is excluded from version control.
*   Sensitive information (like AWS credentials) should be configured via environment variables or AWS CLI configuration, not hardcoded in the application.
*   The `app.log` file is for debugging and should not be committed to version control.
