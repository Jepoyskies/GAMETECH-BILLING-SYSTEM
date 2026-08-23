# GAMETECH BILLING SYSTEM

This is a comprehensive Django-based billing and network management system that integrates with MikroTik devices via the RouterOS API. 

The project operates on a containerized **Docker Architecture** utilizing:
- **Django** (Web Application & API)
- **PostgreSQL** (Primary Database)
- **Redis** (Message Broker)
- **Celery & Celery Beat** (Background Task Processing & Scheduling)

---

## Prerequisites

Before running this project, you must install:
- **[Docker Desktop](https://www.docker.com/products/docker-desktop)** (Includes Docker Engine and Docker Compose). Ensure Docker Desktop is running before proceeding.

---

## Setting up the System (Docker)

Spinning up the entire tech stack is incredibly simple thanks to Docker Compose.

### Step 1: Build and Run the Containers
Open your terminal at the root of the project (where `docker-compose.yml` is located) and run:
```bash
docker-compose up --build
```
*Note: This command will download the necessary base images, install all Python dependencies, set up the database, run Django migrations, and start the web server alongside the Celery workers. You can omit `--build` on subsequent runs.*

### Step 2: Create a Superuser (Admin)
Once the containers are successfully running, open a **new terminal tab** and execute the following command to create your admin account:
```bash
docker-compose exec web python manage.py createsuperuser
```
Follow the prompts to set your username, email, and password.

### Step 3: Load Initial Data (Optional)
The system automatically creates a fresh PostgreSQL database and runs all migrations on startup. Since the database is new, it will be empty. If you need test data (like seed plans), you can load the backup data fixture by running:
```bash
docker-compose exec web python manage.py loaddata data/fixtures/datadump.json
```

### Step 4: Access the System
With the services running, you can access the application in your web browser:
- **Main Portal**: [http://localhost:8000/](http://localhost:8000/)
- **Admin Panel**: [http://localhost:8000/admin/](http://localhost:8000/admin/)

### Step 5: Stopping and Restarting the System
**To Stop the System:**
When you are done working for the day, you can safely shut down the system without losing any data.
- If running in the foreground: Simply press `Ctrl + C` in the terminal where Docker is running.
- Alternatively, you can open a new terminal in the project root and run:
  ```bash
  docker-compose down
  ```

**To Restart the System Later:**
When you want to work on the project again, simply open your terminal at the project root and run:
```bash
docker-compose up
```
*(You don't need the `--build` flag again unless you've added new packages to requirements.txt).*

---

## Useful Docker Commands

- **Run in the background (detached mode)**: `docker-compose up -d`
- **View logs**: `docker-compose logs -f`
- **Access the Django shell**: `docker-compose exec web python manage.py shell`

---

## Legacy Local Setup
*Note: The standalone local setup is no longer the recommended way to run this project.*

If you need to run the project without Docker for legacy testing purposes, the old local Windows setup batch scripts (`setup.bat` and `run.bat`) and local Python utilities have been preserved and moved to the `scripts/` directory. 
