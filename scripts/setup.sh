#!/bin/bash

# ==============================================================================
# Script de Configuración Inicial - Chatbot Educativo
# ==============================================================================
#
# Este script automatiza la configuración inicial del chatbot.
#
# Uso:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh

set -e  # Salir si hay algún error

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Funciones de utilidad
print_header() {
    echo -e "\n${BOLD}${BLUE}========================================${NC}"
    echo -e "${BOLD}${BLUE}$1${NC}"
    echo -e "${BOLD}${BLUE}========================================${NC}\n"
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

ask_yes_no() {
    while true; do
        read -p "$1 (s/n): " yn
        case $yn in
            [Ss]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Por favor responde s (sí) o n (no).";;
        esac
    done
}

# ==============================================================================
# CONFIGURACIÓN INICIAL
# ==============================================================================

print_header "CONFIGURACIÓN INICIAL DEL CHATBOT EDUCATIVO"

echo "Este script te guiará en la configuración inicial del sistema."
echo ""

# Paso 1: Verificar Docker
print_info "Paso 1/6: Verificando Docker..."
if ! command -v docker &> /dev/null; then
    print_error "Docker no está instalado"
    echo "Por favor instala Docker desde: https://www.docker.com/get-started"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose no está instalado"
    echo "Por favor instala Docker Compose"
    exit 1
fi

if ! docker ps > /dev/null 2>&1; then
    print_error "Docker no está ejecutándose"
    echo "Por favor inicia Docker"
    exit 1
fi

print_success "Docker está instalado y ejecutándose"

# Paso 2: Configurar archivo .env
print_info "Paso 2/6: Configurando variables de entorno..."

if [ -f ".env" ]; then
    print_warning "El archivo .env ya existe"

    if ask_yes_no "¿Deseas sobrescribirlo?"; then
        cp .env.example .env
        print_success "Archivo .env creado desde .env.example"
    else
        print_info "Manteniendo archivo .env existente"
    fi
else
    cp .env.example .env
    print_success "Archivo .env creado desde .env.example"
fi

# Solicitar API Key
echo ""
print_info "Necesitas una API Key de Google AI Studio"
print_info "Visita: https://aistudio.google.com/"
print_info "O lee: SETUP_API_KEY.md para instrucciones detalladas"
echo ""

if ask_yes_no "¿Ya tienes tu API Key de Google?"; then
    read -p "Ingresa tu API Key: " api_key

    if [ -n "$api_key" ]; then
        # Reemplazar la API key en .env
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/GOOGLE_API_KEY=\"tu-api-key-aqui\"/GOOGLE_API_KEY=\"$api_key\"/" .env
        else
            # Linux
            sed -i "s/GOOGLE_API_KEY=\"tu-api-key-aqui\"/GOOGLE_API_KEY=\"$api_key\"/" .env
        fi
        print_success "API Key configurada"
    else
        print_warning "API Key no ingresada - deberás configurarla manualmente"
    fi
else
    print_warning "Necesitarás configurar la API Key en .env antes de continuar"
    print_info "Edita el archivo .env y reemplaza 'tu-api-key-aqui' con tu clave"
fi

# Paso 3: Seleccionar modelo
print_info "Paso 3/6: Seleccionando modelo de Gemini..."
echo ""
echo "Opciones de modelo:"
echo "  1) gemini-1.5-pro-latest (Máxima calidad, más lento)"
echo "  2) gemini-2.5-flash (Rápido y económico, recomendado)"
echo ""
read -p "Selecciona una opción (1 o 2) [2]: " model_choice

case $model_choice in
    1)
        model="models/gemini-1.5-pro-latest"
        print_success "Modelo seleccionado: Gemini 1.5 Pro"
        ;;
    *)
        model="models/gemini-2.5-flash"
        print_success "Modelo seleccionado: Gemini 2.5 Flash"
        ;;
esac

# Actualizar el modelo en .env
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|GEMINI_MODEL=\".*\"|GEMINI_MODEL=\"$model\"|" .env
else
    sed -i "s|GEMINI_MODEL=\".*\"|GEMINI_MODEL=\"$model\"|" .env
fi

# Paso 4: Verificar documentos
print_info "Paso 4/6: Verificando documentos del curso..."

if [ ! -d "data" ]; then
    mkdir -p data
    print_success "Directorio data/ creado"
fi

file_count=$(find data -type f 2>/dev/null | wc -l)

if [ "$file_count" -eq 0 ]; then
    print_warning "El directorio data/ está vacío"
    echo ""
    echo "Por favor agrega tus documentos del curso (PDF, TXT, MD, DOCX) en:"
    echo "  $(pwd)/data/"
    echo ""

    if ask_yes_no "¿Deseas continuar sin documentos? (solo para testing)"; then
        print_info "Continuando sin documentos..."
    else
        print_info "Agrega tus documentos y ejecuta este script nuevamente"
        exit 0
    fi
else
    print_success "Se encontraron $file_count archivos en data/"
fi

# Paso 5: Iniciar servicios
print_info "Paso 5/6: Iniciando servicios Docker..."

print_info "Iniciando ChromaDB..."
docker-compose up -d chromadb

print_info "Esperando a que ChromaDB esté listo..."
sleep 10

if docker-compose ps | grep -q "chromadb_service.*Up"; then
    print_success "ChromaDB está ejecutándose"
else
    print_error "Error al iniciar ChromaDB"
    exit 1
fi

# Paso 6: Ejecutar ingesta (si hay documentos)
if [ "$file_count" -gt 0 ]; then
    print_info "Paso 6/6: Procesando documentos..."
    echo ""
    print_warning "Este proceso puede tardar varios minutos..."
    echo ""

    if docker-compose run --rm fastapi_app python ingest.py; then
        print_success "Documentos procesados exitosamente"
    else
        print_error "Error al procesar documentos"
        print_info "Verifica que tu API Key sea correcta y tengas cuota disponible"
        exit 1
    fi
else
    print_warning "Paso 6/6: Omitiendo ingesta (no hay documentos)"
fi

# Iniciar la API
print_info "Iniciando API..."
docker-compose up -d fastapi_app

print_info "Esperando a que la API esté lista..."
sleep 5

# Verificar que la API esté funcionando
if curl -s -f http://localhost:8080/health > /dev/null 2>&1; then
    print_success "API está funcionando"
else
    print_warning "La API puede tardar un poco en estar lista"
fi

# Resumen final
print_header "✅ CONFIGURACIÓN COMPLETADA"

echo "Tu chatbot educativo está listo para usar!"
echo ""
echo "${BOLD}Próximos pasos:${NC}"
echo ""
echo "  1. Abre el archivo: ${BLUE}frontend/index.html${NC}"
echo "  2. Haz clic en el ícono de chat en la esquina inferior derecha"
echo "  3. Prueba haciendo preguntas sobre tu curso"
echo ""
echo "${BOLD}URLs útiles:${NC}"
echo "  - API: ${BLUE}http://localhost:8080${NC}"
echo "  - Documentación: ${BLUE}http://localhost:8080/docs${NC}"
echo "  - Health Check: ${BLUE}http://localhost:8080/health${NC}"
echo ""
echo "${BOLD}Comandos útiles:${NC}"
echo "  - Ver logs: ${YELLOW}docker-compose logs -f fastapi_app${NC}"
echo "  - Reiniciar: ${YELLOW}docker-compose restart${NC}"
echo "  - Detener: ${YELLOW}docker-compose down${NC}"
echo "  - Pruebas: ${YELLOW}./scripts/quick-test.sh${NC}"
echo ""

if ask_yes_no "¿Deseas ejecutar las pruebas del sistema ahora?"; then
    if [ -f "scripts/quick-test.sh" ]; then
        chmod +x scripts/quick-test.sh
        ./scripts/quick-test.sh
    else
        print_warning "Script de pruebas no encontrado"
    fi
fi

print_success "¡Disfruta tu chatbot educativo! 🎓🤖"
