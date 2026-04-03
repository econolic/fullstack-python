#!/bin/bash

# FastAPI Docker Management Script
# Usage: ./docker_manager.sh [start|stop|restart|logs|status]

COMPOSE_FILE="docker-compose.yaml"

case "$1" in
    start)
        echo "Starting FastAPI application with PostgreSQL..."
        docker-compose up --build -d
        echo "Application started!"
        echo "Access the app at: http://localhost:8000"
        ;;
    stop)
        echo "Stopping FastAPI application..."
        docker-compose down
        echo "Application stopped!"
        ;;
    restart)
        echo "Restarting FastAPI application..."
        docker-compose down
        docker-compose up --build -d
        echo "Application restarted!"
        ;;
    logs)
        echo "Showing application logs..."
        docker-compose logs -f
        ;;
    status)
        echo "Checking container status..."
        docker-compose ps
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Build and start the application"
        echo "  stop    - Stop the application"
        echo "  restart - Restart the application"
        echo "  logs    - Show application logs"
        echo "  status  - Show container status"
        echo ""
        echo "Before starting, make sure Docker Desktop is running!"
        exit 1
        ;;
esac
