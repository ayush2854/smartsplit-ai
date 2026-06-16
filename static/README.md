# 💸 SmartSplit AI — Smart Expense Manager

An AI-powered group expense splitting web application built with Python Flask and Google Gemini AI.

## 🔴 Live Demo
[Click here to view the live app](your-deployment-link-here)

## 📸 Screenshots
![SmartSplit AI Screenshot](screenshot.png)

## ✨ Features
- Create trip/group and add members
- Add expenses — AI automatically categorizes them (Food, Transport, Accommodation, etc.)
- Visual spending breakdown with category progress bars
- Smart settlement calculator — tells exactly who owes whom
- AI-generated spending insights and money-saving tips
- Graceful fallback if AI API is unavailable — app never crashes

## 🛠️ Tech Stack
- **Backend:** Python, Flask
- **AI:** Google Gemini 2.0 Flash API
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Deployment:** Render

## 🚀 Run Locally

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/smartsplit-ai.git
cd smartsplit-ai

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Add your API key
# Create a .env file and add:
# GEMINI_API_KEY=your_key_here

# Run the app
python app.py
```

## 🔑 Environment Variables
Create a `.env` file in the root directory:
GEMINI_API_KEY=your_gemini_api_key_here

Get your free API key at [aistudio.google.com](https://aistudio.google.com)

## 💡 How It Works
1. User creates a group and adds members
2. As expenses are added, Gemini AI categorizes each one automatically
3. The app calculates fair settlements using equal split logic
4. AI analyzes all expenses and generates personalized spending insights.