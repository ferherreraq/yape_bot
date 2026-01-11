from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import re
import requests
from datetime import datetime

app = Flask(__name__)
# Habilitar CORS para permitir peticiones desde el navegador
CORS(app)

# ==================== CONFIGURACIÓN ====================
API_KEY = os.environ.get('WEBHOOK_API_KEY', 'tu_clave_secreta_aqui_cambiar')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'tu_token_de_telegram')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', 'tu_chat_id')

# ==================== FUNCIONES AUXILIARES ====================
def validar_api_key(headers):
    """Valida que el API Key en el header sea correcto"""
    api_key = headers.get('X-API-Key')
    return api_key == API_KEY

def extraer_datos_yape(texto):
    """
    Extrae nombre del emisor y monto del mensaje de Yape
    Formatos soportados:
    - ¡Yape! Has recibido un pago de Juan Perez por S/ 20.00
    - Juan Perez te envió S/ 20.00
    - Recibiste S/ 20.00 de Juan Perez
    """
    # Limpiar el texto
    texto = texto.strip()
    
    # Patrón 1: "Has recibido un pago de NOMBRE por S/ MONTO"
    patron1 = r'(?:has recibido un pago de|recibiste de)\s+([\w\s]+?)\s+por\s+S/\s*([\d,]+\.\d{2})'
    
    # Patrón 2: "NOMBRE te envió S/ MONTO"
    patron2 = r'([\w\s]+?)\s+te envió\s+S/\s*([\d,]+\.\d{2})'
    
    # Patrón 3: "Recibiste S/ MONTO de NOMBRE"
    patron3 = r'recibiste\s+S/\s*([\d,]+\.\d{2})\s+de\s+([\w\s]+)'
    
    # Intentar con patrón 1 y 2 (nombre primero, luego monto)
    for patron in [patron1, patron2]:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            nombre = match.group(1).strip()
            monto = match.group(2).strip()
            return nombre, monto
    
    # Intentar con patrón 3 (monto primero, luego nombre)
    match = re.search(patron3, texto, re.IGNORECASE)
    if match:
        monto = match.group(1).strip()
        nombre = match.group(2).strip()
        return nombre, monto
    
    return None, None

def enviar_telegram(mensaje):
    """Envía mensaje al chat de Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': mensaje,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")
        return False

# ==================== RUTAS ====================
@app.route('/')
def home():
    """Ruta de prueba para verificar que el servidor está activo"""
    return jsonify({
        'status': 'online',
        'service': 'Yape Webhook',
        'timestamp': datetime.now().isoformat(),
        'endpoints': {
            'test': '/test',
            'webhook': '/webhook/yape'
        }
    })

@app.route('/webhook/yape', methods=['POST'])
def webhook_yape():
    """
    Endpoint principal que recibe las notificaciones de Yape
    """
    # 1. Validar API Key
    if not validar_api_key(request.headers):
        return jsonify({'error': 'API Key inválido'}), 401
    
    # 2. Obtener datos del JSON
    try:
        data = request.get_json()
        if not data or 'texto' not in data:
            return jsonify({'error': 'Formato JSON inválido. Se requiere campo "texto"'}), 400
        
        texto_notificacion = data['texto']
    except Exception as e:
        return jsonify({'error': f'Error procesando JSON: {str(e)}'}), 400
    
    # 3. Extraer información de Yape
    nombre, monto = extraer_datos_yape(texto_notificacion)
    
    # 4. Si no se detectó un pago válido, ignorar
    if not nombre or not monto:
        return jsonify({
            'status': 'ignored',
            'reason': 'No se detectó un formato de pago de Yape'
        }), 200
    
    # 5. Formatear mensaje para Telegram
    mensaje = f"""
💰 <b>NUEVO PAGO RECIBIDO</b>

👤 <b>De:</b> {nombre}
💵 <b>Monto:</b> S/ {monto}
🕐 <b>Hora:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

📱 <i>Notificación automática de Yape</i>
"""
    
    # 6. Enviar a Telegram
    if enviar_telegram(mensaje):
        return jsonify({
            'status': 'success',
            'nombre': nombre,
            'monto': monto,
            'enviado_telegram': True
        }), 200
    else:
        return jsonify({
            'status': 'partial_success',
            'nombre': nombre,
            'monto': monto,
            'enviado_telegram': False,
            'error': 'No se pudo enviar a Telegram'
        }), 500

@app.route('/test', methods=['POST'])
def test_endpoint():
    """Endpoint de prueba para verificar configuración"""
    if not validar_api_key(request.headers):
        return jsonify({'error': 'API Key inválido'}), 401
    
    mensaje_prueba = """
🧪 <b>MENSAJE DE PRUEBA</b>

✅ El webhook está funcionando correctamente
🔐 API Key validado
📡 Conexión con Telegram exitosa

<i>Sistema listo para recibir notificaciones de Yape</i>
"""
    
    if enviar_telegram(mensaje_prueba):
        return jsonify({'status': 'success', 'message': 'Prueba exitosa'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Error al enviar a Telegram'}), 500

# ==================== EJECUTAR SERVIDOR ====================
if __name__ == '__main__':
    # Para desarrollo local
    app.run(host='0.0.0.0', port=5000, debug=True)