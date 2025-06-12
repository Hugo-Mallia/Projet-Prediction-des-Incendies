# Project Title: Flaméo - Expert IA en Sécurité Incendie

## Description
Flaméo is an intelligent fire safety audit application powered by AI. It assists users in conducting comprehensive fire safety audits of buildings by asking relevant questions, analyzing responses, and providing actionable insights and recommendations based on established fire safety norms.

## Features
- **Intelligent Questioning**: The chatbot adapts its questions based on user responses, ensuring a thorough audit process.
- **Risk Assessment**: Evaluates fire, structural, and evacuation risks based on user-provided data.
- **Contextual Insights**: Generates insights related to fire safety norms and potential risks.
- **Audit Reporting**: Exports audit data and generates detailed reports in various formats.
- **User-Friendly Interface**: Provides an interactive interface for users to engage with the chatbot.

## Project Structure
```
app/
├── main.py                # Entry point of the application
├── api/                   # API endpoints and middleware
│   ├── __init__.py
│   ├── endpoints.py
│   └── middleware.py
├── core/                  # Core application logic and configuration
│   ├── __init__.py
│   ├── config.py
│   ├── logging.py
│   └── utils.py
├── chatbot/               # Chatbot logic and state management
│   ├── __init__.py
│   ├── flameo.py
│   ├── audit_state.py
│   ├── questions.py
│   └── report.py
├── interface/             # User interface components
│   ├── __init__.py
│   └── gradio_app.py
├── models/                # Data models and schemas
│   ├── __init__.py
│   ├── risk_item.py
│   └── schemas.py
├── routers/               # Route definitions for the application
│   ├── __init__.py
│   └── items.py
├── routes/                # Specific routes for scanning environments
│   ├── __init__.py
│   └── scan_environment.py
├── services/              # Business logic and services
│   ├── __init__.py
│   ├── audit_service.py
│   └── detection_service.py
├── requirements.txt       # Project dependencies
└── README.md              # Project documentation
```

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   cd flaméo
   ```
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage
To start the application, run:
```
python main.py
```
Access the application via the provided interface at `http://localhost:8000/audit`.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.