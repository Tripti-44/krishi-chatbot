# Free AI Chatbot Backend for Krishi Sahayak
# Uses Hugging Face (FREE) + ThingSpeak (FREE)
# No database needed!

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app)  # Allow your website to access this

# =============================================
#           CONFIGURATION
# =============================================

# ThingSpeak Settings (FREE)
CHANNEL_ID = "3186649"
READ_API_KEY = "1Q662QYR5B6OC2J7"
WRITE_API_KEY = "S11TBLKKK829U3NA"

# Hugging Face Settings (FREE)
# You can use these FREE APIs without any key!
HF_API_URL = "https://api-inference.huggingface.co/models/google/gemma-2b-it"

# System Instructions in Hindi
SYSTEM_PROMPT = """
तुम एक कृषि सहायक हो। किसानों को खेती में मदद करो।

तुम्हारे पास है:
- तापमान सेंसर (°C)
- नमी सेंसर (%)
- मिट्टी की नमी (0-1023, अच्छा: 300-400)
- गैस सेंसर
- बारिश सेंसर
- मोटर (ON/OFF)

हमेशा हिंदी में जवाब दो।
सरल भाषा इस्तेमाल करो।
"""

# =============================================
#        HELPER FUNCTIONS
# =============================================

def get_sensor_data():
    """Fetch latest sensor data from ThingSpeak"""
    try:
        url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json"
        params = {
            "api_key": READ_API_KEY,
            "results": 1
        }
        response = requests.get(url, params=params)
        data = response.json()
        
        if data and 'feeds' in data and len(data['feeds']) > 0:
            latest = data['feeds'][0]
            return {
                "temperature": float(latest.get('field1', 0)),
                "humidity": float(latest.get('field2', 0)),
                "soil": int(latest.get('field3', 0)),
                "gas": int(latest.get('field4', 0)),
                "rain": int(latest.get('field5', 0)),
                "motor": int(latest.get('field6', 0)),
                "timestamp": latest.get('created_at', '')
            }
    except Exception as e:
        print(f"Error fetching sensor data: {e}")
    
    return None

def control_motor(action):
    """Control motor via ThingSpeak
    action: 1 for ON, 0 for OFF
    """
    try:
        url = "https://api.thingspeak.com/update"
        params = {
            "api_key": WRITE_API_KEY,
            "field6": action
        }
        response = requests.get(url, params=params)
        return response.text != "0"  # Returns entry number if successful
    except Exception as e:
        print(f"Error controlling motor: {e}")
        return False

def call_hugging_face_ai(user_message, sensor_data=None):
    """Call FREE Hugging Face AI model"""
    
    # Build context with sensor data
    context = SYSTEM_PROMPT
    
    if sensor_data:
        context += f"\n\nवर्तमान सेंसर डेटा:\n"
        context += f"तापमान: {sensor_data['temperature']}°C\n"
        context += f"नमी: {sensor_data['humidity']}%\n"
        context += f"मिट्टी: {sensor_data['soil']}\n"
        context += f"गैस: {sensor_data['gas']}\n"
        context += f"बारिश: {sensor_data['rain']}\n"
        context += f"मोटर: {'चालू' if sensor_data['motor'] == 1 else 'बंद'}\n"
    
    # Prepare prompt
    full_prompt = f"{context}\n\nउपयोगकर्ता: {user_message}\nसहायक:"
    
    try:
        # Call Hugging Face API (FREE!)
        # Note: First call may be slow (model loading), then fast
        headers = {"Content-Type": "application/json"}
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": 200,
                "temperature": 0.7,
                "return_full_text": False
            }
        }
        
        response = requests.post(HF_API_URL, headers=headers, json=payload)
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            return result[0].get('generated_text', 'माफ़ करें, मुझे समझ नहीं आया।')
        else:
            return "माफ़ करें, कुछ गड़बड़ हो गई। फिर से कोशिश करें।"
            
    except Exception as e:
        print(f"Error calling AI: {e}")
        return "माफ़ करें, AI सेवा अभी उपलब्ध नहीं है।"

def detect_intent(message):
    """Detect what user wants to do"""
    message_lower = message.lower()
    
    # Motor control intents
    if any(word in message_lower for word in ['मोटर चालू', 'motor on', 'start motor', 'पानी दो']):
        return 'motor_on'
    if any(word in message_lower for word in ['मोटर बंद', 'motor off', 'stop motor', 'पानी बंद']):
        return 'motor_off'
    
    # Status check intents
    if any(word in message_lower for word in ['status', 'स्थिति', 'कैसा है', 'क्या हाल']):
        return 'status'
    
    # Specific sensor queries
    if any(word in message_lower for word in ['तापमान', 'temperature', 'गर्मी']):
        return 'temperature'
    if any(word in message_lower for word in ['नमी', 'humidity']):
        return 'humidity'
    if any(word in message_lower for word in ['मिट्टी', 'soil', 'जमीन']):
        return 'soil'
    
    # Visualization
    if any(word in message_lower for word in ['ग्राफ', 'chart', 'graph', 'visualization']):
        return 'chart'
    
    # General advice
    if any(word in message_lower for word in ['सलाह', 'advice', 'मदद', 'help']):
        return 'advice'
    
    return 'general'

# =============================================
#           API ENDPOINTS
# =============================================

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint"""
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Get current sensor data
        sensor_data = get_sensor_data()
        
        # Detect intent
        intent = detect_intent(user_message)
        
        # Handle specific intents
        if intent == 'motor_on':
            success = control_motor(1)
            response = "✅ मोटर चालू हो गई है!" if success else "❌ मोटर चालू करने में समस्या आई।"
            
        elif intent == 'motor_off':
            success = control_motor(0)
            response = "✅ मोटर बंद हो गई है!" if success else "❌ मोटर बंद करने में समस्या आई।"
            
        elif intent == 'status' and sensor_data:
            response = f"""📊 आपके खेत की स्थिति:

🌡️ तापमान: {sensor_data['temperature']}°C
💧 नमी: {sensor_data['humidity']}%
🌿 मिट्टी: {sensor_data['soil']} {'(सूखी)' if sensor_data['soil'] > 500 else '(अच्छी)'}
💨 गैस: {sensor_data['gas']}
🌧️ बारिश: {sensor_data['rain']}
⚙️ मोटर: {'चालू' if sensor_data['motor'] == 1 else 'बंद'}"""

        elif intent == 'temperature' and sensor_data:
            response = f"🌡️ अभी तापमान {sensor_data['temperature']}°C है।"
            
        elif intent == 'humidity' and sensor_data:
            response = f"💧 अभी नमी {sensor_data['humidity']}% है।"
            
        elif intent == 'soil' and sensor_data:
            status = "सूखी है" if sensor_data['soil'] > 500 else "अच्छी है"
            response = f"🌿 मिट्टी की नमी {sensor_data['soil']} है। मिट्टी {status}।"
            
        elif intent == 'chart':
            response = "📊 यहाँ आपका डेटा विज़ुअलाइज़ेशन देखें:\n👉 /chart.html\n\nआप देख सकते हैं:\n- तापमान ट्रेंड\n- नमी का ग्राफ\n- मिट्टी की नमी\n- सभी सेंसर की तुलना"
            
        else:
            # Use AI for general questions
            response = call_hugging_face_ai(user_message, sensor_data)
        
        return jsonify({
            "response": response,
            "sensor_data": sensor_data,
            "intent": intent
        })
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sensors', methods=['GET'])
def sensors():
    """Get current sensor data"""
    data = get_sensor_data()
    if data:
        return jsonify(data)
    return jsonify({"error": "Could not fetch sensor data"}), 500

@app.route('/motor', methods=['POST'])
def motor():
    """Control motor"""
    data = request.json
    action = data.get('action', 0)  # 0 or 1
    
    success = control_motor(action)
    
    return jsonify({
        "success": success,
        "message": "Motor turned " + ("ON" if action == 1 else "OFF")
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Krishi Sahayak Chatbot is running!"})

# =============================================
#           RUN THE SERVER
# =============================================

if __name__ == '__main__':
    print("🌱 Krishi Sahayak Chatbot Backend Starting...")
    print("📡 ThingSpeak Channel:", CHANNEL_ID)
    print("🤖 AI Model: Hugging Face (FREE)")
    print("💾 Database: Not needed (using ThingSpeak)")
    print("\n✅ Server ready!")
    
    app.run(host='0.0.0.0', port=5000, debug=True)