# Tabroom Tools

A tool for scraping and analyzing debate tournament data from tabroom.com.

## Features

- Scrape judge information from tabroom.com
- Calculate and visualize judge metrics
- Store data locally for offline access
- Run in a Docker container for easy deployment

## Requirements

- Docker and Docker Compose
- Python 3.9+

## Setup

1. Clone this repository
2. Build the Docker container: `docker-compose -f docker/docker-compose.yml build`
3. Run the container: `docker-compose -f docker/docker-compose.yml up`
4. Access the web interface at http://localhost:8000

## Development

To set up a development environment:

1. Create a virtual environment: `python -m venv venv`
2. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`