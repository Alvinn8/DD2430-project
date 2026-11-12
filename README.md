# DD2430: LLM Agent for DSC Analysis

A chat-based AI agent that helps scientists analyse raw **Differential Scanning Calorimetry (DSC)** data. The user uploads a DSC curve and asks questions in natural language. Instead of estimating values by looking at the graph, the language model calls Python tools that compute exact results from the raw data, such as the melting point.

This project is developed in the course **DD2430 Project Course in Data Science** at KTH Royal Institute of Technology, in collaboration with **AstraZeneca**.

## Features

Currently available in the agent:

- Upload DSC data files (CSV) through the chat
- Plot heat flow against temperature, so the model can "see" the curve
- Read the heat flow at a given temperature
- Find the maximum or minimum heat flow within a temperature range (to locate peaks)
- **Melting point analysis** (extrapolated onset: intersection of a baseline fit and a fit of the peak's leading edge)
- Shows which tools the agent called and their results, so every answer can be checked

In development:

- **Glass transition temperature (Tg)** using the midpoint method (prototype in branch `glass_transition_script`)
- **Data standardizer** that converts public DSC datasets to the common format below (branch `standardize`)

## Architecture

```
Frontend (Vue 3, port 5173)
        │  HTTP, streamed response
        ▼
Backend (FastAPI, port 8000)
        │
        ▼
Agent (LangChain) ──► LLM (Gemini 2.5 Flash on Google Cloud Vertex AI)
        │
        ▼
Python analysis tools (NumPy, SciPy, pandas, Matplotlib)
```

## Repository structure

| Path | Content |
|---|---|
| `backend/app/services/llm_service.py` | Connection to the LLM, chat sessions and response streaming |
| `backend/app/services/llm_tools.py` | Tools the agent can call |
| `backend/app/tools/` | DSC file reader and melting point algorithm |
| `backend/app/routes/` | API endpoints (`/api/chat`, `/api/health`) |
| `backend/prompts/main.md` | System prompt of the agent |
| `frontend/` | Chat interface (Vue 3 + TypeScript) |
| `apps/calculate_by_hand.py` | Desktop app to compute the melting point manually by selecting regions of the curve |
| `docker-compose.yml` | Starts backend and frontend together |

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Access to the team's Google Cloud project (service account key). Ask a team member for it.

The key and the data files are **not** stored in the repository.

## Setup and running

1. Rename the Google Cloud service account key to `service-account.json` and place it in the `backend/` folder.
2. Copy `backend/.env.example` to `backend/.env` and set `GCP_PROJECT_ID` to the team's project ID.
3. Start Docker Desktop (on Windows it must be running before the next step).
4. From the repository root, run:

   ```bash
   docker compose up --build
   ```

5. Open <http://localhost:5173/> in your browser.
6. To stop the application:

   ```bash
   docker compose down
   ```

API documentation is available at <http://localhost:8000/api/docs> while the backend is running.

### Manual analysis app (optional)

```bash
pip install -r backend/requirements.txt
python -m apps.calculate_by_hand
```

The app expects a CSV file with `Temperature` and `HeatFlow` columns.

## Data format

The agent reads DSC data in a standardized CSV format:

| Column | Description |
|---|---|
| `time_min` | Time since the start of the experiment (minutes). May be empty |
| `temperature_C` | Temperature (°C) |
| `heat_flow_mW` | Heat flow (mW) |

Experiment metadata (sample name, heating rate, mass) can be provided in a file with the same name ending in `_metadata.csv`.

## Team

- Polonia Ramírez
- Alvin Westling
- Kristijan Bilanović
- Kristijan Šagovac

## License

This project is licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
