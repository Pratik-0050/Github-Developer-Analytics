# GitHub Developer Analytics 

A web application that analyzes GitHub profiles, repositories, commits, pull requests, and issues through an interactive dashboard. It uses GitHub's API to present developer activity and repository statistics in an organized, visual format.

## ✨ Features

* GitHub OAuth authentication
* GitHub profile and repository analytics
* Commit history and activity tracking
* Pull request and issue analytics
* Programming language distribution
* Interactive charts and statistics
* Responsive dark-themed dashboard

## 🛠️ Tech Stack

* **Frontend:** Next.js, TypeScript, Tailwind CSS
* **Backend:** Python, FastAPI
* **API:** GitHub REST API
* **Authentication:** GitHub OAuth
* **Charts:** Recharts, if installed

## 🚀 Run Locally

**1. Clone the repository**

```bash
git clone https://github.com/Pratik-0050/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

**2. Start the backend**

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Configure the required environment variables in `backend/.env` before starting the backend.

**3. Start the frontend**

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Configure `frontend/.env.local` with:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Open **http://localhost:3000** in your browser.


* **4.One-Click Startup:**
* Launch the frontend and backend automatically by double-clicking `run.bat` inside your Windows Folder.


## 👨‍💻 Author

**Pratik Wankar**
GitHub: [Pratik-0050](https://github.com/Pratik-0050)
