# EduNavigator
A Python-based chatbot that provides university program details, merit requirements, and admission timelines for students.

# 🎓 University Merit Chatbot

**University Merit Chatbot** is a Python-based chatbot that helps students explore universities, programs (BS, MS, PhD), merit requirements, and admission timelines. It uses a SQLite database to store university program data and can easily be updated using a CSV file.

## Features

- 🎓 Browse all universities and campuses.  
- 📚 Get program-specific information (Department, Program, Year, Minimum & Maximum Merit).  
- 🗓️ Supports admission dates (start and close) — can be added to CSV and DB.  
- 🗄️ Built with Python and SQLite for fast, reliable querying.  
- 📝 Easy to update database by modifying CSV.  

## How to Use

1. Make sure you have Python 3 installed.
2. Install dependencies (if any) and activate your virtual environment:
   ```bash
   python -m venv ChatBotEnv
   source ChatBotEnv/bin/activate   # Linux/Mac
   ChatBotEnv\Scripts\activate      # Windows
Run the chatbot:

python app.py
Update merit_list.csv to add new universities or programs. The database will automatically populate on first run.
