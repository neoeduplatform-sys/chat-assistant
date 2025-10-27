#!/bin/bash

# ==============================================================================
# Script de Prueba Rápida para el Chatbot Educativo
# ==============================================================================
#
# Este script realiza una prueba rápida del sistema completo.
#
# Uso:
#   chmod +x scripts/quick-test.sh
#   ./scripts/quick-test.sh

set -e  # Salir si hay algún error

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones de utilidad
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# ==============================================================================
# PRUEBAS
# ==============================================================================

print_header "PRUEBA RÁPIDA DEL CHATBOT EDUCATIVO"

# Test 1: Verificar que Docker está ejecutándose
print_info "Verificando Docker..."
if docker ps > /dev/null 2>&1; then
    print_success "Docker está ejecutándose"
else
    print_error "Docker no está ejecutándose o no tienes permisos"
    exit 1
fi

# Test 2: Verificar que los servicios están activos
print_info "Verificando servicios..."
if docker-compose ps | grep -q "chromadb_service"; then
    print_success "ChromaDB está activo"
else
    print_warning "ChromaDB no está activo"
    print_info "Ejecuta: docker-compose up -d chromadb"
fi

if docker-compose ps | grep -q "fastapi_service"; then
    print_success "FastAPI está activo"
else
    print_warning "FastAPI no está activo"
    print_info "Ejecuta: docker-compose up -d"
fi

# Test 3: Verificar archivo .env
print_info "Verificando configuración..."
if [ -f ".env" ]; then
    print_success "Archivo .env existe"

    if grep -q "GOOGLE_API_KEY=\"tu-api-key-aqui\"" .env; then
        print_error "API Key no configurada en .env"
        print_info "Edita el archivo .env y agrega tu API key de Google"
        exit 1
    elif grep -q "GOOGLE_API_KEY=\"\"" .env; then
        print_error "API Key vacía en .env"
        exit 1
    else
        print_success "API Key configurada"
    fi
else
    print_error "Archivo .env no existe"
    print_info "Copia .env.example a .env y configura tu API key"
    exit 1
fi

# Test 4: Verificar directorio de datos
print_info "Verificando documentos..."
if [ -d "data" ]; then
    file_count=$(find data -type f \( -name "*.pdf" -o -name "*.txt" -o -name "*.md" \) 2>/dev/null | wc -l)

    if [ "$file_count" -gt 0 ]; then
        print_success "Se encontraron $file_count documentos en /data"
    else
        print_warning "No se encontraron documentos en /data"
        print_info "Agrega tus documentos del curso en el directorio data/"
    fi
else
    print_error "Directorio data/ no existe"
    exit 1
fi

# Test 5: Probar endpoint de health
print_info "Probando API..."
sleep 2  # Esperar un poco

if curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
    print_success "API responde correctamente"

    # Obtener el estado detallado
    health_response=$(curl -s http://localhost:8080/health)
    status=$(echo "$health_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

    if [ "$status" = "healthy" ]; then
        print_success "Sistema completamente saludable"

        # Extraer número de documentos
        count=$(echo "$health_response" | grep -o '"collection_count":[0-9]*' | cut -d':' -f2)
        if [ -n "$count" ] && [ "$count" -gt 0 ]; then
            print_success "Base de datos contiene $count fragmentos"
        else
            print_warning "Base de datos vacía - ejecuta el script de ingesta"
            print_info "Comando: docker-compose run --rm fastapi_app python ingest.py"
        fi
    else
        print_warning "Sistema en estado: $status"
    fi
else
    print_error "No se puede conectar con la API en http://localhost:8080"
    print_info "Verifica que los servicios estén ejecutándose: docker-compose ps"
    exit 1
fi

# Test 6: Probar una consulta simple
print_info "Probando consulta al chatbot..."
response=$(curl -s -X POST http://localhost:8080/api/chat \
    -H "Content-Type: application/json" \
    -d '{"question": "Hola"}' \
    2>/dev/null)

if echo "$response" | grep -q '"answer"'; then
    print_success "Chatbot responde correctamente"
    answer=$(echo "$response" | grep -o '"answer":"[^"]*"' | cut -d'"' -f4 | head -c 100)
    echo "     Respuesta: $answer..."
else
    print_warning "El chatbot no pudo generar una respuesta"
    print_info "Verifica que hayas ejecutado el script de ingesta"
fi

# Resumen final
print_header "RESUMEN"

echo -e "Estado del sistema: ${GREEN}Operativo${NC}"
echo ""
echo "Próximos pasos:"
echo "  1. Abre frontend/index.html en tu navegador"
echo "  2. Haz clic en el ícono de chat"
echo "  3. Haz preguntas sobre tu curso"
echo ""
echo "URLs útiles:"
echo "  - API: http://localhost:8080"
echo "  - Docs: http://localhost:8080/docs"
echo "  - Health: http://localhost:8080/health"
echo ""

print_success "¡Todo listo! 🎉"
