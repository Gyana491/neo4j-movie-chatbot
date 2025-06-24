from flask import Flask, render_template, request, jsonify
import sys, os, logging

# Set up logging so we can see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add our scripts folder to Python path
sys.path.append('scripts')
from chatbot import MovieChatbot
from gemini_chatbot import GeminiMovieChatbot

app = Flask(__name__)
chatbot = MovieChatbot()
gemini_bot = GeminiMovieChatbot()

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Movie Chatbot</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; }
            .chat-scroll::-webkit-scrollbar {
                width: 6px;
            }
            .chat-scroll::-webkit-scrollbar-track {
                background: #f1f1f1;
            }
            .chat-scroll::-webkit-scrollbar-thumb {
                background: #888;
                border-radius: 3px;
            }
            .chat-scroll::-webkit-scrollbar-thumb:hover {
                background: #555;
            }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen">
        <div class="max-w-4xl mx-auto p-6">
            <div class="bg-white rounded-2xl shadow-lg p-6 mb-8">
                <div class="flex items-center mb-6">
                    <h1 class="text-3xl font-bold text-gray-800 flex items-center">
                        🎬 Movie Database Chatbot
                        <span class="ml-3 text-sm px-3 py-1 bg-blue-100 text-blue-700 rounded-full">AI Powered</span>
                    </h1>
                </div>


                <div id="chat-container" class="chat-scroll bg-gray-50 rounded-xl border border-gray-200 h-[500px] overflow-y-auto p-4 mb-6">
                    <div class="bot-message bg-blue-50 text-gray-800 p-4 rounded-xl max-w-[80%] mb-4">
                        Hi! I'm your movie chatbot. What would you like to know about movies? 🎥
                    </div>
                </div>

                <div class="flex flex-col sm:flex-row gap-4 items-end">
                    <div class="flex-1">
                        <label for="model-select" class="block text-sm font-medium text-gray-700 mb-2">Choose Language Model</label>
                        <select id="model-select" class="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                            <option value="deepseek">Deepseek</option>
                            <option value="gemini" selected>Gemini</option>
                        </select>
                    </div>
                    <div class="flex-[3] relative">
                        <input type="text" 
                            id="user-input" 
                            placeholder="Ask about movies..." 
                            class="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-[100px]"
                            onkeypress="if(event.key==='Enter') sendMessage()">
                        <button onclick="sendMessage()" 
                            class="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                            Send
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function sendMessage() {
                const input = document.getElementById('user-input');
                const question = input.value.trim();
                if (!question) return;
                
                // Show user message
                addMessage(question, 'user-message');
                input.value = '';
                
                // Show thinking message
                addMessage('🤔 Thinking...', 'bot-message thinking');
                
                // Send to chatbot
                fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        question: question,
                        model: document.getElementById('model-select').value
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // Remove thinking message
                    const thinkingMsg = document.querySelector('.thinking');
                    if (thinkingMsg) thinkingMsg.remove();
                    
                    // Show bot response
                    addMessage(data.answer, 'bot-message');
                });
            }
            
            function addMessage(text, className) {
                const container = document.getElementById('chat-container');
                const div = document.createElement('div');
                div.className = className + ' p-4 rounded-xl max-w-[80%] mb-4 ' + 
                    (className.includes('user-message') ? 
                        'bg-blue-600 text-white ml-auto' : 
                        'bg-blue-50 text-gray-800');
                
                if (typeof marked !== 'undefined') {
                    div.innerHTML = marked.parse(text);
                } else {
                    div.innerHTML = text.replace(/\\n/g, '<br>');
                }
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;

                // Add animation
                div.style.opacity = '0';
                div.style.transform = 'translateY(10px)';
                div.style.transition = 'all 0.3s ease';
                setTimeout(() => {
                    div.style.opacity = '1';
                    div.style.transform = 'translateY(0)';
                }, 50);
            }

            // Make example questions clickable
            document.querySelectorAll('.grid > div').forEach(div => {
                div.onclick = () => {
                    document.getElementById('user-input').value = div.textContent.trim();
                    sendMessage();
                };
            });
        </script>
    </body>
    </html>
    '''

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question = data.get('question', '')
    use_gemini = data.get('model') == 'gemini'
    bot = gemini_bot if use_gemini else chatbot
    try:
        answer = bot.chat(question)
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'answer': f'Sorry, I had a problem: {str(e)}'})
    
# Add endpoint to switch models
@app.route('/set_model', methods=['POST'])
def set_model():
    data = request.get_json()
    model = data.get('model')
    return jsonify({'status': f'Model set to {model}'})

if __name__ == '__main__':
    print("🚀 Starting Movie Chatbot...")
    app.run(debug=True, port=8080)