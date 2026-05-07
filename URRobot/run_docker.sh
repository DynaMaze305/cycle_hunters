#!/bin/bash
echo "Cleaning agents container…"
sudo docker rm ur-agent
sudo docker rmi ur-agent

echo "Launching UR agent"
sudo docker compose build
sudo docker compose --profile ur up