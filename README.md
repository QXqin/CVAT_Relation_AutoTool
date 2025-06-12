CVAT Relationship Annotation Tool
https://via.placeholder.com/150 (Placeholder for your project logo)

A powerful desktop application that automates relationship annotation for CVAT (Computer Vision Annotation Tool) XML files. This tool helps accelerate annotation workflows by automatically generating relationship points based on predefined rules and enables custom relationship creation.

Features ✨
​​Automated Relationship Generation​​: Auto-generate relationships based on object categories and predefined rules
​​Custom Relationship Creation​​: Define custom relationships between objects with an intuitive UI
​​Rule Management​​: Create and manage rules for automatic relationship generation
​​Label Configuration​​: Import label sets from Excel/CSV files
​​Auto-Backup​​: Automatic backup of original XML files before processing
​​Batch Processing​​: Process multiple XML files efficiently
AI-Assisted Development 🤖
This project was developed with assistance from AI technologies, including:

GPT-4 language model for code generation and optimization
AI-powered code completion and suggestion tools
Automated testing algorithms
All AI-generated code has been reviewed, tested, and refined by human developers to ensure:

Functional correctness
Optimal performance
Security best practices
User experience refinement
Installation 💻
Requirements
Python 3.7+
Pip package manager
Dependencies
Install required dependencies:

pip install pandas openpyxl
Running the Application
Clone the repository:
git clone https://github.com/your-username/your-repo-name.git
Run the main application:
cd your-repo-name
python main.py
Getting Started 🚀
Basic Workflow
Open the application
Select an input CVAT XML file
Optionally create custom relationships using the Custom Relationship mode
Click "Execute Auto Annotation" to process the file
Review the output XML file with generated relationships
Using Custom Relationship Mode
Select "Custom Relationship" from the menu
Enter the subject category or ID
Select the object category or ID
Choose a predicate
Click "Add to List"
Repeat as needed, then click "Confirm"
Managing Rules
Click "Manage Rules"
Add/edit/delete rules:
Object Type: The category to match
Predicate: The relationship to create
Save changes
Project Structure 📂
project-root/
│
├── main.py                 # Application entry point
├── config.py               # Configuration handling
├── rules.py                # Rule management
├── xml_processor.py        # Core XML processing logic
├── labels_manager.py       # Label configuration management
├── utils.py                # Utility functions
│
├── gui/                    # GUI components
│   ├── main_window.py      # Main application window
│   ├── dialogs.py          # Custom dialogs
│   └── widgets.py          # Reusable UI components
│
├── config.json             # Application configuration
├── rules.json             # Rule definitions
├── labels_config.json      # Entity-predicate configuration
│
└── backups/               # Auto-created backup directory
