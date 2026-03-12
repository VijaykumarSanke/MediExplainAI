# MediExplainAI

MediExplainAI is an AI-powered web application that helps users understand complex medical information in simple and easy-to-read language. The system processes medical queries and provides clear explanations using Natural Language Processing techniques.

## Overview

Medical reports and terminology can be difficult for patients to understand. MediExplainAI aims to bridge this gap by converting complex medical terms into simplified explanations that are easier for users to interpret.

The project integrates NLP models with a web interface so users can ask questions or input medical information and receive understandable explanations.

## Features

* AI-based medical explanation system
* Converts complex medical terms into simple language
* Interactive chatbot-style interface
* Fast query processing
* Easy-to-use web interface

## Tech Stack

**Backend**

* Python
* Flask
* NLP Models

**Frontend**

* HTML
* CSS
* JavaScript

**Database**

* SQLite (mediai.db)

## Project Structure

```
MediExplainAI/
│
├── test_chatbot.py        # Main chatbot logic
├── mediai.db              # Database for storing data
├── all_code.txt           # Combined project code
├── templates/             # HTML pages
├── static/                # CSS, JS, assets
└── README.md              # Project documentation
```

## Installation

1. Clone the repository

```
git clone https://github.com/VijaykumarSanke/MediExplainAI.git
```

2. Navigate to the project folder

```
cd MediExplainAI
```

3. Install dependencies

```
pip install -r requirements.txt
```

4. Run the application

```
python test_chatbot.py
```

5. Open your browser and go to

```
http://127.0.0.1:5000/
```

## Usage

1. Open the web application.
2. Enter a medical query or medical term.
3. The system processes the query using NLP techniques.
4. The AI returns a simplified explanation.

## Author
Vijaykumar Sanke GitHub: https://github.com/VijaykumarSanke Email: vijaykumar.sanke7@gmail.com

## Future Improvements

* Integration with advanced LLM models
* Voice-based medical queries
* Mobile-friendly UI
* Expanded medical knowledge base

## License

This project is developed for educational and research purposes.
