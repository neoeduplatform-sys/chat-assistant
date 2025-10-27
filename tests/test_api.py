"""
Script de Prueba para la API del Chatbot
=========================================

Este script prueba todos los endpoints de la API para verificar
que el sistema está funcionando correctamente.

Uso:
    python tests/test_api.py
"""

import requests
import json
import sys
from typing import Dict, Any

# Configuración
API_BASE_URL = "http://localhost:8080"
TIMEOUT = 30  # segundos

# Colores para output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Imprime un encabezado."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_success(text: str):
    """Imprime un mensaje de éxito."""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_error(text: str):
    """Imprime un mensaje de error."""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_warning(text: str):
    """Imprime un mensaje de advertencia."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


def print_info(text: str):
    """Imprime un mensaje informativo."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")


def test_root_endpoint() -> bool:
    """Prueba el endpoint raíz (/)."""
    print_info("Probando endpoint raíz (/)...")

    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            print_success(f"Endpoint raíz funciona correctamente")
            print(f"   Mensaje: {data.get('message')}")
            print(f"   Versión: {data.get('version')}")
            return True
        else:
            print_error(f"Endpoint raíz retornó código {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print_error("No se pudo conectar a la API. ¿Está ejecutándose?")
        print_info("Ejecuta: docker-compose up -d")
        return False
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        return False


def test_health_endpoint() -> bool:
    """Prueba el endpoint de health check (/health)."""
    print_info("Probando endpoint de health check (/health)...")

    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            status = data.get('status')

            if status == 'healthy':
                print_success("Sistema completamente saludable")
                print(f"   Modelo: {data.get('model')}")
                print(f"   Fragmentos en DB: {data.get('collection_count')}")
                return True
            elif status == 'degraded':
                print_warning("Sistema degradado")
                print(f"   Mensaje: {data.get('message')}")
                return False
            else:
                print_error("Sistema no saludable")
                print(f"   Mensaje: {data.get('message')}")
                return False
        else:
            print_error(f"Health check retornó código {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Error al verificar health: {e}")
        return False


def test_chat_endpoint() -> bool:
    """Prueba el endpoint de chat (/api/chat)."""
    print_info("Probando endpoint de chat (/api/chat)...")

    # Preguntas de prueba
    test_questions = [
        "¿Qué es RAG?",
        "Explícame la arquitectura del sistema",
        "¿Cuáles son los componentes principales?"
    ]

    all_passed = True

    for i, question in enumerate(test_questions, 1):
        print(f"\n  Pregunta {i}: {question}")

        try:
            response = requests.post(
                f"{API_BASE_URL}/api/chat",
                json={"question": question},
                timeout=TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                sources = data.get('sources', [])

                if answer:
                    print_success(f"Respuesta recibida ({len(answer)} caracteres)")

                    # Mostrar primeras líneas de la respuesta
                    preview = answer[:150] + "..." if len(answer) > 150 else answer
                    print(f"     {preview}")

                    if sources:
                        print(f"     Fuentes: {', '.join(sources)}")
                else:
                    print_error("Respuesta vacía")
                    all_passed = False
            elif response.status_code == 503:
                print_error("Motor de consulta no disponible")
                print_warning("Ejecuta: docker-compose run --rm fastapi_app python ingest.py")
                all_passed = False
                break
            else:
                print_error(f"Error: código {response.status_code}")
                all_passed = False

        except requests.exceptions.Timeout:
            print_error("Timeout - La consulta tardó demasiado")
            all_passed = False
        except Exception as e:
            print_error(f"Error: {e}")
            all_passed = False

    return all_passed


def test_chat_endpoint_errors() -> bool:
    """Prueba el manejo de errores del endpoint de chat."""
    print_info("Probando manejo de errores...")

    tests = [
        {
            "name": "Pregunta vacía",
            "payload": {"question": ""},
            "expected_status": 422
        },
        {
            "name": "Pregunta muy larga",
            "payload": {"question": "x" * 1001},
            "expected_status": 422
        },
        {
            "name": "Payload inválido",
            "payload": {"wrong_field": "test"},
            "expected_status": 422
        }
    ]

    all_passed = True

    for test in tests:
        print(f"\n  Test: {test['name']}")

        try:
            response = requests.post(
                f"{API_BASE_URL}/api/chat",
                json=test['payload'],
                timeout=TIMEOUT
            )

            if response.status_code == test['expected_status']:
                print_success(f"Error manejado correctamente (código {response.status_code})")
            else:
                print_error(f"Código esperado: {test['expected_status']}, recibido: {response.status_code}")
                all_passed = False

        except Exception as e:
            print_error(f"Error: {e}")
            all_passed = False

    return all_passed


def main():
    """Función principal."""
    print_header("SUITE DE PRUEBAS - API DEL CHATBOT EDUCATIVO")

    results = {}

    # Test 1: Endpoint raíz
    print_header("TEST 1: Endpoint Raíz")
    results['root'] = test_root_endpoint()

    # Test 2: Health check
    print_header("TEST 2: Health Check")
    results['health'] = test_health_endpoint()

    # Test 3: Chat endpoint
    print_header("TEST 3: Endpoint de Chat")
    results['chat'] = test_chat_endpoint()

    # Test 4: Manejo de errores
    print_header("TEST 4: Manejo de Errores")
    results['errors'] = test_chat_endpoint_errors()

    # Resumen
    print_header("RESUMEN DE RESULTADOS")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    print(f"Total de tests: {total}")
    print_success(f"Pasados: {passed}")

    if failed > 0:
        print_error(f"Fallidos: {failed}")

    print("\nResultados detallados:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name.capitalize()}: {status}")

    print_header("FIN DE LAS PRUEBAS")

    # Exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nPruebas interrumpidas por el usuario")
        sys.exit(1)
