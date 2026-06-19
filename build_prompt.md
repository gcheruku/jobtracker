Act as an Elite Full-Stack Software Engineer and System Architect. I want to build a self-hosted Job Tracking Dashboard with a decoupled architecture (Python backend API + a frontend web client). 

Review the product design requirements below, present tech stack recommendations, and then generate the code systematically.

Use @figma_design.png as the base design for the user interface.

=========================================
PRODUCT DESIGN REQUIREMENTS
=========================================
1. Landing Page / Dashboard: Metric cards, Kanban pipeline (Saved, Applied, Interviewing, Offer, Rejected), Activity log, Calendar widget.
2. Filtering & Search: Global search, dropdown filters (Status, Date, Work Mode, Salary), and sort features.
3. Job Details Page/Drawer: Key metadata, job description text, persistent personal notes, action item checklists, and application timeline.
4. AI Resume-Job Fit Tool: A "Compare with Resume" button that displays an AI analysis overlay (Match Score %, matched vs. missing keyword chips, tailored interview prep questions, and resume optimization tips).

=========================================
STEP 1: FRONTEND TECH STACK EVALUATION
=========================================
Before writing the code, briefly list 2-3 modern, popular frontend options (e.g., Next.js with Tailwind CSS, Vite + React with shadcn/ui, Vue/Nuxt), Flutter. 
- Provide a clear "Recommended Approach" that prioritizes developer velocity, responsive design, and smooth component states (like Kanban drag-and-drop or modal animations).
- Explain *why* it fits a self-hosted setup. Stop and let me confirm, OR proceed directly with your recommendation if it is standard industry best practice.

=========================================
STEP 2: BACKEND ARCHITECTURE SPECIFICATIONS
=========================================
Build the backend using Python. It must run locally on a laptop or a remote server as a standalone service.
- Framework: FastPI (highly recommended for performance, automatic OpenAPI docs, and easy integration with modern frontends).
- API Exposure: Expose clean RESTful API endpoints for:
    - Jobs CRUD (Create, Read, Update, Delete)
    - Status management (moving a job across pipeline columns)
    - Resume management (uploading/storing the text or PDF of the user's resume)
    - AI Comparison endpoint (stubs out the LLM payload, parsing job text vs resume text)
- Persistent Database: Use SQLite (configured via SQLAlchemy or SQLModel) so the application runs entirely locally out of a single file without needing complex database clustering.

=========================================
STEP 3: IMPLEMENTATION & CODE GENERATION
=========================================
Create the repository file structure and generate production-ready code.

1. File Structure: Print the clean directory layout separating `/backend` and `/frontend`.
2. Backend Code:
   - Provide the Database Schema / Models (Job application table, Notes table, Resume table).
   - Provide `main.py` with FastAPI endpoints, CORS middleware enabled (allowing connection from any origin/device), and SQLite initialization.
3. Frontend Code:
   - Scaffold the main dashboard layout using the recommended framework.
   - Implement the Kanban pipeline, filter states, and the interactive "Compare with Resume" UI panel (including loading states and color-coded keyword chips).
