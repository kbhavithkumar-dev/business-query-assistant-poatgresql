# Business Data Query Assistant

Ask sales questions in plain English and see the answer, result table, and PostgreSQL query. The app uses Python, FastAPI, PostgreSQL, and Gemini through LangChain. The example shop uses fictional orders.

## Start in VS Code

1. Install Docker with Docker Compose. Clone this repository and open the folder in VS Code.
2. Copy `.env.example` to `.env`. In PowerShell use `Copy-Item .env.example .env`. On macOS or Linux use `cp .env.example .env`.
3. Run `docker compose up --build -d --wait` from the repository root.
4. Open [Business Query on port 8001](http://localhost:8001). PostgreSQL listens locally on port 5433. DocDesk can run alongside it on port 8000.
5. Select **What is the total revenue?** and click **Run query**. The sample orders total **₹102,700**. Expand **View SQL** to read the statement.

Demo mode uses four built-in queries against real PostgreSQL, so it works without a Gemini API key. For AI mode, create a [Gemini API key](https://aistudio.google.com/apikey), set `GEMINI_API_KEY` and `DEMO_MODE=false` in `.env`, then run `docker compose up -d --wait` to apply the settings. Ask **Show total revenue for monitors in the West region.** The sample result is **₹25,000**.

Use `docker compose logs app` for logs and `docker compose down` to stop the app and preserve the sample data.

## Run Python directly

Run `docker compose up -d --wait db` to start only the database. Install Python 3.12 and run the commands for your OS.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001 --limit-concurrency 16
```

**macOS or Linux**

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001 --limit-concurrency 16
```

## Connect your own PostgreSQL instance

Set `BUSINESS_DATABASE_URL` to a DSN for a dedicated, non-admin login. Use TLS for hosted databases. An administrator should create a `reporting.sales` view that exposes only the fields listed below, with one row per order. Grant the login `CONNECT` on the database, `USAGE` on the `reporting` schema, and `SELECT` on that view. Keep privileges on the underlying tables with the database owner. The included [database setup script](database/init.sql) shows the pattern using sample data.

| Column | Expected value |
| --- | --- |
| `order_id` | Integer order ID |
| `order_date` | Order date |
| `region` | Region name |
| `product` | Product name |
| `quantity` | Units in the order |
| `revenue` | Numeric order total in INR |

Review `SCHEMA` in `assistant.py` when your data uses different categories or currency. The app checks the database view at `/readyz`. `/healthz` checks the process.

## Read the code

| File | What to look for |
| --- | --- |
| `main.py` | FastAPI endpoints and readable error responses. |
| `assistant.py` | Schema prompt, Gemini call, PostgreSQL execution, and result summary. |
| `sql_guard.py` | PostgreSQL parser, allowlisted SQL, and row limits. |
| `index.html`, `static/` | Browser form, example questions, result table, and SQL preview. |
| `web_security.py` | Host configuration, request bounds, and authentication for shared hosting. |

Read [Concepts and workflow](docs/WORKFLOW.md) for the data flow and a worked example.

## Tests, hosting, and limitations

Run `python -m unittest discover -s tests -v` in the virtual environment. Set `RUN_DB_TESTS=1` with the sample PostgreSQL database running to include database integration tests. In PowerShell set it with `$env:RUN_DB_TESTS = "1"`. The live Gemini walkthrough above verifies model access using your own key.

Both services bind to loopback in the example. For shared hosting, keep the app and database private, add an HTTPS reverse proxy with rate limits, and configure a strong `APP_PASSWORD`, `APP_USERNAME`, and explicit `ALLOWED_HOSTS`. Keep loopback addresses in the host list for local probes. Use a reporting view containing only data all authorized users may see.

- Questions must fit the sales view and supported SQL. Joins, CTEs, write operations, and nested queries are outside the allowed subset.
- A query can show up to 100 rows and has a three-second database statement timeout. Narrow large questions with a date, product, or region filter.
- Gemini may choose the wrong filter or aggregation. Review **View SQL** and compare important results against a known query.
- The provider receives questions and a schema description. Database result rows stay inside the app.
- This design uses one reporting view and one credential pair. It does not implement per-user permissions, external identity, or a full BI platform.
