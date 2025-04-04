from flask import Flask, request, jsonify
import json
from flask_cors import CORS
import os
import google.generativeai as genai
from dotenv import load_dotenv

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)
load_dotenv()

# Configure the Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Create the model with configuration
generation_config = {
  "temperature": 0,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "text/plain",
}
safety_settings = [
  {
    "category": "HARM_CATEGORY_HARASSMENT",
    "threshold": "BLOCK_NONE",
  },
  {
    "category": "HARM_CATEGORY_HATE_SPEECH",
    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
  },
  {
    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
  },
  {
    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
  },
]

model = genai.GenerativeModel(
  model_name="gemini-1.5-pro",
  safety_settings=safety_settings,
  generation_config=generation_config,
  system_instruction='''
  IMPORTANT ... Do not use Markdown formatting (e.g., **bold**, *italics*, `code blocks`, bullet points, or numbered lists). Always return plain text.
Role & Purpose:

You are Cipher, an AI tutor for an interactive learning platform. Your goal is to help users understand topics, solve doubts, and improve their skills based on their learning level. Users may be Beginners, Intermediate, or Advanced learners.

Guidelines:
	1.	Adaptive Explanations:
	- If the user is a Beginner, explain concepts in simple terms with real-life analogies.
	- If the user is Intermediate, provide concise explanations with examples and encourage them to think critically.
	- If the user is Advanced, use technical explanations and discuss optimization strategies or deeper insights.
	2.	Code & Examples (For Coding Topics):
	- Provide well-commented code snippets where needed.
	- Break down complex concepts into step-by-step solutions.
	- When applicable, include multiple solutions (brute force & optimized).
	3.	Encouraging Problem-Solving:
	- Instead of directly giving answers, guide the user by asking leading questions.
	- Encourage them to try solving problems before revealing the solution.
	- Offer hints if the user is stuck.
	4.	Personalized Study Assistance:
	- Suggest relevant study materials (videos, articles, exercises) based on their skill level.
	- Recommend daily challenges based on their weak areas.
	- If the user has completed a quiz, refer to their results and roadmap for tailored responses.
	5.	Escape Room & Challenges:
	- If the user is in the Escape Room Challenge, give hints without revealing direct answers.
	- Ensure fairness by not providing solutions outright.
	- Track their progress and provide explanations for wrong answers.
	6.	Interactive & Engaging:
	- Keep responses engaging and motivating to encourage learning.
	- Recognize achievements (e.g., "Great job! You've mastered this concept!").
	- If a user asks an unrelated question, gently guide them back to learning.
dont go on giving para graphs unless neccesary keep the answers crisp no unnececsary info
also dont give the text in markdown format'''
)

# Store chat sessions for different users
chat_sessions = {}

# Load questions from JSON file
try:
    with open("pythonBig.json", "r") as f:
        questions = json.load(f)
except FileNotFoundError:
    questions = []
    print("Warning: pythonBig.json file not found. Quiz functionality will be limited.")

@app.route('/')
def index():
    return app.send_static_file('homepage.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    session_id = request.remote_addr  # Using IP as a simple session identifier
    
    # Create a new chat session if one doesn't exist for this user
    if session_id not in chat_sessions:
        chat_sessions[session_id] = model.start_chat(history=[])
    
    try:
        # Send the message to the model
        response = chat_sessions[session_id].send_message(user_message)
        model_response = response.text
        
        # Update chat history
        chat_sessions[session_id].history.append({"role": "user", "parts": [user_message]})
        chat_sessions[session_id].history.append({"role": "model", "parts": [model_response]})
        
        return jsonify({"response": model_response})
    except Exception as e:
        return jsonify({"response": f"Sorry, I encountered an error: {str(e)}"})

# Process user's answers
@app.route('/evaluate_quiz', methods=['POST'])
def evaluate_quiz():
    data = request.json
    level = data.get("level")  # Beginner, Intermediate, or Advanced
    answers = data.get("answers", [])

    correct_count = 0
    total_questions = len(questions)
    subtopic_analysis = {}

    for answer in answers:
        qid = answer["Qid"]
        selected_option = answer["Selected"]

        # Find the correct answer from the JSON data
        question_data = next((q for q in questions if q["Qid"] == qid), None)

        if question_data:
            subtopic = question_data["Subtopic"]
            correct_answer = question_data["Correct Answer"]

            if selected_option == correct_answer:
                correct_count += 1
                subtopic_analysis[subtopic] = subtopic_analysis.get(subtopic, 0) + 1
            else:
                subtopic_analysis[subtopic] = subtopic_analysis.get(subtopic, 0) - 1

    # Determine strengths and weaknesses
    strengths = [sub for sub, score in subtopic_analysis.items() if score > 0]
    weaknesses = [sub for sub, score in subtopic_analysis.items() if score <= 0]

    # Determine if the user passes to the next level
    percentage = (correct_count / total_questions) * 100
    if percentage >= 80:
        status = "Congratulations! You passed."
        next_level = "Intermediate" if level == "Beginner" else "Advanced" if level == "Intermediate" else "Expert"
    else:
        status = "You are currently at the same level."
        next_level = level

    return jsonify({
        "score": correct_count,
        "total_questions": total_questions,
        "status": status,
        "next_level": next_level,
        "strengths": strengths,
        "weaknesses": weaknesses
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)