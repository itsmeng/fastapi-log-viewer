# Local Watch Logs

A self-hosted FastAPI application to view AWS CloudWatch logs locally, aimed at providing faster access than the AWS console, especially in environments with restrictive company policies.

## Features

*   Fast, local access to CloudWatch logs.
*   Simple and easy-to-use API.
*   Bypasses slow AWS console access.

## Prerequisites

*   Python 3.7+
*   AWS credentials configured on your local machine (e.g., via `~/.aws/credentials` or environment variables).

## Installation

1.  Clone this repository.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3.  Run the application:

    ```bash
    uvicorn main:app --reload
    ```

## Usage

Once the application is running, you can access the API at `http://127.0.0.1:8000`.
