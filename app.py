from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector.errors import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
import nltk 
from nltk.chat.util import Chat, reflections
from textblob import TextBlob
from db import insert_user_activity  # assuming you have this
import os
from utils import extract_text, allowed_file
import PyPDF2
from flask import Flask, request, jsonify
from docx import Document
from werkzeug.utils import secure_filename
from datetime import datetime
import pytesseract
from PIL import Image

app = Flask(__name__)
app.secret_key = '27f0cd7c8e6ca12b0d083593e2cf883c'

# 👇 This is where you point to your installed tesseract.exe
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Upload Configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx", "png", "jpg", "jpeg"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ''
    return text
    
def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return '\n'.join([para.text for para in doc.paragraphs])

def extract_text_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()
    
def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    elif ext == '.txt':
        return extract_text_from_txt(file_path)
    else:
        return "Unsupported file type"
    
def get_chatbot_response(user_input):
    # Use the chatbot to get a response
    bot_response = chatbot.respond(user_input)  # Corrected line
    
    # If no response found, use a default response
    if not bot_response:
        bot_response = "Sorry, I didn't quite understand that. Can you please clarify?"
    
    return bot_response
    
def download_nltk_data():
    """
    Function to download NLTK data (punkt tokenizer).
    This will download the data the first time it's run.
    """
    try:
        # Download the 'punkt' tokenizer
        nltk.download('punkt')
        print("NLTK 'punkt' tokenizer downloaded successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")

# Call the function
download_nltk_data()

chat_pairs = [
# Greetings
    (r'hi|hello|hey', ['Hello! How can I assist you today?']),
    (r'how are you?', ['I am doing great, thank you! How about you?']),
    (r'bye', ['Goodbye! Take care.']),
    (r'hey', ['Hey there! How can I help?']),
    (r'what\'s up?', ['Not much, just here to help! How can I assist you?']),
    (r'what is your name?', ['I am your assistant, SwiftBot.']),
    (r'who are you?', ['I am your personal assistant, here to help you with anything!']),
    
    # Time & Date
    (r'what time is it?', ['The current time is: ' + datetime.now().strftime('%H:%M:%S')]),
    (r'what day is it today?', ['Today is: ' + datetime.now().strftime('%A')]),
    (r'what is today\'s date?', ['Today is: ' + datetime.now().strftime('%Y-%m-%d')]),
    (r'what\'s the date today?', ['The date today is: ' + datetime.now().strftime('%Y-%m-%d')]),
    (r'what\'s the time now?', ['The current time is: ' + datetime.now().strftime('%H:%M:%S')]),
    
    # Work-related
    (r'can you solve my problem?', ['I will try my best to help! What\'s the problem?']),
    (r'how can you assist me?', ['I can answer questions, solve problems, and offer recommendations!']),

    # Advice & Recommendations
    (r'can you recommend me a book?', ['I recommend "To Kill a Mockingbird" by Harper Lee, or How about "1984" by George Orwell? It\'s a classic!']),
    (r'can you recommend a movie?', ['I recommend "Inception" for a mind-bending experience!']),
    (r'what book should I read?', ['How about "1984" by George Orwell? It\'s a classic!']),
    (r'what movie should I watch?', ['If you like action, "The Dark Knight" is a great choice.']),
    
    # User-specific Responses
    (r'how are you feeling?', ['I am doing well! How about you?']),
    (r'what\'s your favorite song?', ['I don\'t listen to music, but "Bohemian Rhapsody" is iconic!']),
    (r'where are you located?', ['I exist in the cloud, so I am wherever you are!']),
    (r'what can you do for me?', ['I can help you with questions, tasks, and much more!']),
    (r'can you tell me a joke?', ['Why don\'t skeletons fight each other? They don\'t have the guts!']),
    
    # Random Catch-all
    (r'(.*)', ['Sorry, I didn\'t quite understand that. Can you please clarify?']),
]

chatbot = Chat(chat_pairs, reflections)

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='Shravani123',
        database='chatbot_db'
    )
    
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('login'))

    return render_template('login.html')

def save_user_activity(action, time):
    conn = mysql.connector.connect(
        host="localhost", user="root", password="", database="chatbot_db"
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_activity (email, action, action_time) VALUES (%s, %s)", (action, time)
    )
    conn.commit()
    conn.close()
    
@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        extracted_text = extract_text(filepath)

        # Save user activity if session info available
        if 'email' in session:
            email = session['email']
            insert_user_activity(email, f'Uploaded and analyzed file: {filename}')

            # Save file info into the uploaded_files table
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = """
                INSERT INTO uploaded_files (filename, extracted_text, file_path, uploaded_at)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (filename, extracted_text, filepath, datetime.now()))
            conn.commit()
            cursor.close()
            conn.close()

        return jsonify({'file_name': filename, 'extracted_text': extracted_text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/send_message', methods=['POST'])
def send_message():
    if 'username' not in session:
        return jsonify({'response': 'User not logged in'}), 401

    user_input = request.form.get('message', '').strip()
    
    if not user_input:
        return jsonify({'response': 'No message received'}), 400

    # Generate bot response (for now, a simple placeholder response)
    bot_response = chatbot.respond(user_input)

    # Analyze sentiment
    sentiment_analysis = TextBlob(user_input).sentiment
    sentiment = 'Positive' if sentiment_analysis.polarity > 0 else 'Negative' if sentiment_analysis.polarity < 0 else 'Neutral'

    # Save chat data to database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO chat_logs (user_id, user_input, bot_response, sentiment) VALUES (%s, %s, %s, %s)', 
                    (session['user_id'], user_input, bot_response, sentiment))
        conn.commit()
    except Exception as e:
        print(f"Error saving to database: {e}")
        return jsonify({'response': 'Error saving message'}), 500
    finally:
        conn.close()

    return jsonify({'response': bot_response, 'sentiment': sentiment})

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        full_name = request.form['full_name']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            flash('Username already exists')
            return render_template('signup.html')

        try:
            cursor.execute('INSERT INTO users (username, password, email, full_name) VALUES (%s, %s, %s, %s)', 
                    (username, hashed_password, email, full_name))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except IntegrityError:
            conn.close()
            flash('Error occurred. Please try again.')
            return render_template('signup.html')

    return render_template('signup.html')

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        return redirect(url_for('login'))

    feedback = request.form['feedback']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO feedback (user_id, feedback) VALUES (%s, %s)', (session['user_id'], feedback))
    conn.commit()
    conn.close()

    flash('Feedback submitted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user data
    cursor.execute('SELECT username, email, full_name, profile_pic FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()

    extracted_text = None
    image_path = None

    if request.method == 'POST':
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                # Create upload folder if not exists
                upload_folder = os.path.join('static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)

                # Save image
                image_path = os.path.join(upload_folder, file.filename)
                file.save(image_path)

                # Perform OCR
                image = Image.open(image_path)
                extracted_text = pytesseract.image_to_string(image)

                # Save result to DB
                cursor.execute(
                    'INSERT INTO ocr_results (user_id, image_path, extracted_text, timestamp) VALUES (%s, %s, %s, %s)',
                    (session['user_id'], image_path, extracted_text, datetime.now())
                )
                conn.commit()

    cursor.close()
    conn.close()
    return render_template('dashboard.html', user=user, extracted_text=extracted_text, image_path=image_path)

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))

    user_input = ''
    bot_response = ''
    sentiment = ''
    
    if request.method == 'POST':
        user_input = request.form.get('user_input', '')
        print(f"User input: {user_input}")  # Debugging line
        bot_response = get_chatbot_response(user_input)
        print(f"Bot response: {bot_response}")  # Debugging line

        sentiment_analysis = TextBlob(user_input).sentiment
        if sentiment_analysis.polarity > 0:
            sentiment = 'Positive'
        elif sentiment_analysis.polarity < 0:
            sentiment = 'Negative'
        else:
            sentiment = 'Neutral'
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO chat_logs (user_id, user_input, bot_response, sentiment) VALUES (%s, %s, %s, %s)', 
                        (session['user_id'], user_input, bot_response, sentiment))
            conn.commit()
        except Exception as e:
            print(f"Error saving to database: {e}")
        finally:
            conn.close()

    return render_template('chat.html', user_input=user_input, bot_response=bot_response, sentiment=sentiment)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT username, email, full_name, profile_pic FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    if request.method == 'POST':
        email = request.form['email']
        full_name = request.form['full_name']
        profile_pic = user['profile_pic']

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile_pic = filename

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET email = %s, full_name = %s, profile_pic = %s WHERE id = %s', 
                    (email, full_name, profile_pic, session['user_id']))
        conn.commit()
        conn.close()

        flash('Profile updated successfully.')
        return redirect(url_for('dashboard'))

    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
