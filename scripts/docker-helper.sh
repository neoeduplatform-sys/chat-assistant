#!/bin/bash

# ==============================================================================
# Docker Helper Script
# ==============================================================================
# Este script detecta automáticamente si usar "docker compose" o "docker-compose"

# Detectar qué comando de docker compose usar
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ Error: Ni 'docker compose' ni 'docker-compose' están disponibles"
    echo ""
    echo "Por favor instala Docker Desktop desde:"
    echo "  https://www.docker.com/products/docker-desktop"
    echo ""
    echo "O instala docker-compose standalone:"
    echo "  brew install docker-compose"
    exit 1
fi

export DOCKER_COMPOSE

echo "✅ Usando: $DOCKER_COMPOSE"

# Ejecutar el comando pasado como argumentos
$DOCKER_COMPOSE "$@"
