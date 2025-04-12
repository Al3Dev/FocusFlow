from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import google.generativeai as genai
from flask_dance.contrib.google import make_google_blueprint, google
import os


app = Flask(__name__)

# Configura tu API key (asegúrate de usar la clave correcta)
genai.configure(api_key="AIzaSyC9-25IMBVX-uva026nOOqc50ZQ48SFv80")  # Coloca tu API Key de Gemini

# Cambia al modelo correcto (gemini-2.0-flash)
model = genai.GenerativeModel("models/gemini-1.5-flash")  # Este es el modelo correcto para ti

app.secret_key = "my_secret_key"  # Para usar sesiones

# Configuración de Flask-Dance para Google OAuth
google_bp = make_google_blueprint(client_id='YOUR_GOOGLE_CLIENT_ID', client_secret='YOUR_GOOGLE_CLIENT_SECRET', redirect_to='google_login')
app.register_blueprint(google_bp, url_prefix='/google_login')

# Función para conectarse a MySQL
def conectar_mysql():
    return mysql.connector.connect(
        host="localhost",
        user="root",  # Tu contraseña si la tienes
        password="",  # Normalmente está vacío
        database="focusflow_db"
    )

# Historial simple en memoria (global, solo para pruebas locales)
conversation_history = []

# Simple in-memory history (for testing only)
conversation_history = []

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message")

    if not user_message:
        return jsonify({"error": "No message received"}), 400

    # English system prompt for Focus AI Assistant
    system_prompt = """
You are Focus, an AI-powered assistant specifically designed to support individuals with ADHD (Attention Deficit Hyperactivity Disorder). Your goal is to provide empathetic, clear, and structured guidance.

Important:
- Do NOT repeat greetings like "Hi" or "Hello" in every response.
- Always get straight to the point with helpful, actionable advice, even if it’s the first message.

Your purpose includes:
1. Breaking down complex tasks into small, achievable steps.
2. Recommending time management techniques (e.g., Pomodoro, Time Blocking).
3. Providing encouragement and motivation when users feel distracted or frustrated.
4. Suggesting ways to minimize distractions and build focus-friendly environments.
5. Offering emotional support in a kind, understanding, and non-judgmental tone.
6. Adapting your strategies to each user’s unique workflow and needs.

Use simple, friendly, and direct language. Always validate the user's efforts and celebrate small wins. You are a focus companion, not just a tool.
"""

    try:
        # Add user message to history
        conversation_history.append(f"User: {user_message}")

        # Use only the last 10 messages for context
        recent_history = "\n".join(conversation_history[-10:])
        full_prompt = f"{system_prompt}\n\n{recent_history}\nFocus:"

        # Generate AI response
        response = model.generate_content(full_prompt)
        ai_message = response.text.strip()

        # Add AI message to history
        conversation_history.append(f"Focus: {ai_message}")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"response": ai_message})




# Página principal con los botones
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.pop("user_email", None)
    session.pop("user_name", None)
    return redirect("/login")

# Página del chatbot, accesible solo después de iniciar sesión
@app.route("/chatbot")
def chatbot():
    if "user_email" not in session:
        return redirect("/login")  # Si no hay sesión, redirigir al login
    return render_template("chatbot.html", user_email=session["user_email"])  # Pasar el correo a la plantilla

# Login con Google (OAuth)
@app.route("/login/callback")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))
    
    user_info = google.get("/plus/v1/people/me")
    user_data = user_info.json()
    email = user_data["emails"][0]["value"]
    nombre = str(user_data.get("displayName", "Google User"))

    # Guardar usuario en la base de datos (si es necesario)
    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    user = cursor.fetchone()
    
    if user is None:  # Si el usuario no está en la base de datos, guardarlo
        cursor.execute("INSERT INTO usuarios (nombre, email, contraseña) VALUES (%s, %s, %s)", (nombre, email, ""))
        conn.commit()
    
    session["user_email"] = email
    session["user_name"] = nombre
    conn.close()

    return redirect("/chatbot")

# Registro de usuario
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form["nombre"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])  # Encriptar la contraseña

        # Guardar usuario en la base de datos
        conn = conectar_mysql()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (nombre, email, contraseña) VALUES (%s, %s, %s)",
                       (nombre, email, password))
        conn.commit()
        conn.close()

        return redirect("/login")  # Redirigir a la página de login

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Buscar usuario en la base de datos
        conn = conectar_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):  # Verificar la contraseña
            session["user_email"] = user[2]  # email
            session["user_name"] = user[1]   # nombre
            return redirect("/chatbot")

        # Si el usuario no existe o la contraseña es incorrecta
        return "Credenciales incorrectas"

    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True)

