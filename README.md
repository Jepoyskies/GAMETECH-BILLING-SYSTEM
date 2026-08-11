# GAMETECH BILLING SYSTEM

This is a Django-based billing and network management system that integrates with MikroTik devices via the RouterOS API.

## Prerequisites

Before running this project on a new PC, make sure you have the following installed:
- **Python 3.8 or higher** (Ensure that you check the box to "Add Python to PATH" during installation if you are on Windows)
- **Git** (optional, if you are pulling the repository from GitHub)

---

## Step-by-Step Installation and Setup Guide

Follow these instructions to set up and run the system on any PC.

### 1. Open your Terminal or Command Prompt
Navigate to the directory where you have extracted or cloned this project.

```bash
cd path/to/GAMETECH-BILLING-SYSTEM
```

### 2. Allow Script Execution (Windows PowerShell Only)
If you are using PowerShell on Windows, you might encounter an error when trying to activate the virtual environment later. To prevent this, run:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```
*(If prompted, type `Y` and press Enter to confirm.)*

### 3. Create a Virtual Environment
It's highly recommended to use a virtual environment so the project's dependencies don't interfere with your system-wide Python packages.

**On Windows:**
```powershell
python -m venv venv
```
*(Note: If `python` opens the Windows Store, use `py -m venv venv` instead.)*

**On macOS/Linux:**
```bash
python3 -m venv venv
```

### 4. Activate the Virtual Environment

**On Windows (PowerShell):**
```powershell
.\venv\Scripts\activate
```

**On Windows (Command Prompt):**
```cmd
venv\Scripts\activate.bat
```

**On macOS/Linux:**
```bash
source venv/bin/activate
```
*(You should see `(venv)` appear at the start of your command line prompt, indicating it is active.)*

### 5. Install Dependencies
Now, install the required packages (`django` and `RouterOS-api`) from the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 6. Apply Database Migrations
This project uses SQLite as its database (`db.sqlite3`). To make sure all the database tables are set up correctly on a fresh install, run:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create a Superuser (Optional but Recommended)
If you need to access the Django admin panel, you will need an admin account. Create one by running:

```bash
python manage.py createsuperuser
```
*(Follow the prompts to enter a username, email, and password. The password won't show on the screen as you type it.)*

### 8. Run the Server
Finally, start the local development server:

```bash
python manage.py runserver
```

### 9. Access the System
Open your web browser and navigate to:
[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

To access the admin panel, go to:
[http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Important Notes
- **Always activate the virtual environment** (`.\venv\Scripts\activate`) before installing new packages or running `python manage.py` commands.
- **To stop the server**, click on the terminal where the server is running and press `Ctrl + C`.
