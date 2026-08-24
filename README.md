<div align="center">
  
# 🎮 GAMETECH BILLING SYSTEM
**Comprehensive ISP Billing & Network Management**

[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=green)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)

</div>

---

Welcome to the **Gametech Billing System**! This is a robust web application built to seamlessly manage ISP billing, customer profiles, and network infrastructure, fully integrated with MikroTik routers via the RouterOS API.

## 🏗️ Architecture

This project is built using a modern, containerized **Docker Architecture** which handles everything for you out-of-the-box:
- 🌐 **Django** - Web Application & API Core
- 🐘 **PostgreSQL** - Primary Relational Database
- 🔴 **Redis** - High-speed Message Broker
- ⚙️ **Celery & Celery Beat** - Asynchronous Background Task Processing & Scheduling

---

## 🛠️ Prerequisites

Before you launch the system, ensure you have the following installed:
- 🐳 **[Docker Desktop](https://www.docker.com/products/docker-desktop)** (Includes Docker Engine and Docker Compose). 
> 💡 *Make sure Docker Desktop is open and running on your machine before proceeding!*

---

## 🚀 Setting up the System (Docker)

Spinning up the entire tech stack is incredibly simple. You don't need to manually configure databases or environments—Docker Compose handles it all!

### 1️⃣ Build and Run the Containers
Open your terminal at the root of the project and run:
```bash
docker-compose up --build
```
> 📌 *Note: This command will download base images, install Python dependencies, set up PostgreSQL, run Django migrations, and start the web server alongside the Celery workers. You can omit `--build` on subsequent runs.*

### 2️⃣ Create a Superuser (Admin Account)
Once the system is successfully running, open a **new terminal tab** and execute:
```bash
docker-compose exec web python manage.py createsuperuser
```
Follow the prompts to configure your admin username and password.

### 3️⃣ Load Initial Data (Optional)
The system automatically creates a fresh, empty PostgreSQL database on first launch. If you need test data for real-world testing (including mock customers, plans, agents, and routers), you can run the seed command:
```bash
docker-compose exec web python manage.py seed
```

### 4️⃣ Access the System
With everything running smoothly, access the application in your browser:
- 🌍 **Main Portal**: [http://localhost:8000/](http://localhost:8000/)
- 🔐 **Admin Panel**: [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## 🛑 Stopping & Restarting the System

### 💤 To Stop the System
When you are done working for the day, you can safely shut down the system without losing any data.
- **If running in the foreground:** Simply press `Ctrl + C` in the terminal where Docker is running.
- **If running in detached mode:** Open a terminal in the project root and run:
  ```bash
  docker-compose down
  ```

### 🔄 To Restart the System Later
When you want to resume work on the project, open your terminal at the root and run:
```bash
docker-compose up
```
> 💡 *You don't need the `--build` flag again unless you've modified `requirements.txt` or the `Dockerfile`.*

---

## 💻 Useful Docker Commands

Here is a quick cheat-sheet for common operations:

| Command | Action |
| :--- | :--- |
| `docker-compose up -d` | Run the system in the background (detached mode) |
| `docker-compose logs -f` | View live logs from all containers |
| `docker-compose exec web python manage.py shell` | Open the interactive Django Python shell |

---

## 🗄️ Legacy Local Setup
> ⚠️ **Notice**: The standalone local setup is no longer the recommended way to run this project.

If you must run the project without Docker for legacy testing purposes, the old local Windows batch scripts (`setup.bat` and `run.bat`) and testing utilities have been preserved in the `scripts/` directory.
