#!/usr/bin/env bash
echo
echo " Stopping KBZHUY..."
docker compose -f infra/docker-compose.dev.yml stop
echo " Done. DB volumes preserved."
echo " Full reset:  docker compose -f infra/docker-compose.dev.yml down -v"
echo
