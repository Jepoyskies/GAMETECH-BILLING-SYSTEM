# GAMETECH BILLING SYSTEM

This is a Django-based billing and network management system that integrates with MikroTik devices via the RouterOS API.

## Prerequisites

Before running this project, make sure you have installed:
- **Python 3.8 or higher** (The `python-installer.exe` is provided in the directory if you need it. When installing, make sure to check "Add Python to PATH" if possible).

---

## Quick Setup and Run (Windows)

We have created two batch scripts to make it super easy for you to run the project.

### Step 1: Initial Setup
If this is your first time opening this project, just double-click the **`setup.bat`** file.
- It will automatically create a virtual environment.
- It will install all the necessary dependencies (`django` and `RouterOS-api`).
- It will set up your local SQLite database correctly.

### Step 2: Running the System
Whenever you want to start the project, just double-click the **`run.bat`** file.
- It will activate the virtual environment and start the development server.
- Leave the black terminal window open while you use the system.

### Step 3: Access the System
Once `run.bat` is running, open your web browser and go to:
- **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

To access the admin panel, go to:
- **[http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)**

---

## Manual Setup (If batch files don't work)

If you prefer to use the command line manually, follow these steps:

1. **Create the virtual environment**:
   ```cmd
   py -m venv venv
   ```
2. **Activate it**:
   ```cmd
   py -m venv venv
   .\venv\Scripts\Activate.ps1

   ```
3. **Install dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
4. **Apply database migrations**:
   ```cmd
   python manage.py makemigrations
   python manage.py migrate
   ```
5. **Run the server**:
   ```cmd
   python manage.py runserver
   ```
