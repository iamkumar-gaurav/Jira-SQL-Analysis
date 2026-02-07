import os
import requests
import pyodbc
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# -------- Jira config (from .env) --------
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
BOARD_ID = int(os.getenv("BOARD_ID", "2"))

# -------- SQL Server config (Windows Auth) --------
SQL_SERVER = os.getenv("SQL_SERVER")                 # e.g. localhost OR .\SQLEXPRESS OR SERVER\INSTANCE
SQL_DATABASE = os.getenv("SQL_DATABASE", "JiraReporting")

# If you ever want SQL Auth later, set SQL_AUTH=sql and provide SQL_USERNAME/PASSWORD.
SQL_AUTH = os.getenv("SQL_AUTH", "windows").lower()
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)


def require_env(name: str, value: str | None):
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")


def to_dt(s: str | None):
    if not s:
        return None
    try:
        # Jira examples: 2026-02-07T10:22:33.123+0530 or ...Z
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def sql_conn():
    """
    Uses Windows Authentication by default (matches your SSMS screenshot).
    Keeps Encrypt=yes and TrustServerCertificate=yes to avoid the TLS trust error you saw in SSMS.
    """
    require_env("SQL_SERVER", SQL_SERVER)
    require_env("SQL_DATABASE", SQL_DATABASE)

    base = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )

    if SQL_AUTH == "sql":
        require_env("SQL_USERNAME", SQL_USERNAME)
        require_env("SQL_PASSWORD", SQL_PASSWORD)
        return pyodbc.connect(base + f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};")
    else:
        # Windows Authentication
        return pyodbc.connect(base + "Trusted_Connection=yes;")


def jira_get(path: str, params: dict | None = None):
    require_env("JIRA_BASE_URL", JIRA_BASE_URL)
    require_env("JIRA_EMAIL", JIRA_EMAIL)
    require_env("JIRA_API_TOKEN", JIRA_API_TOKEN)

    url = f"{JIRA_BASE_URL}{path}"
    r = requests.get(url, params=params, auth=AUTH, timeout=60)
    r.raise_for_status()
    return r.json()


def get_board_columns():
    # Board configuration gives column -> statuses mapping
    cfg = jira_get(f"/rest/agile/1.0/board/{BOARD_ID}/configuration")

    cols = []
    for col in cfg.get("columnConfig", {}).get("columns", []):
        col_name = col.get("name")
        for st in col.get("statuses", []):
            cols.append({
                "BoardId": BOARD_ID,
                "ColumnName": col_name,
                "StatusId": str(st.get("id")),
                "StatusName": st.get("name")
            })
    return cols


def upsert_columns(cur, cols):
    sql = """
        MERGE dbo.JiraBoardColumns AS t
        USING (SELECT ? AS BoardId, ? AS StatusId) AS s
        ON t.BoardId = s.BoardId AND t.StatusId = s.StatusId
        WHEN MATCHED THEN
            UPDATE SET ColumnName=?, StatusName=?
        WHEN NOT MATCHED THEN
            INSERT (BoardId, ColumnName, StatusId, StatusName)
            VALUES (?, ?, ?, ?);
    """
    for c in cols:
        cur.execute(
            sql,
            c["BoardId"], c["StatusId"],
            c["ColumnName"], c["StatusName"],
            c["BoardId"], c["ColumnName"], c["StatusId"], c["StatusName"]
        )


def get_board_issues():
    issues = []
    start_at = 0
    max_results = 50

    while True:
        data = jira_get(
            f"/rest/agile/1.0/board/{BOARD_ID}/issue",
            params={"startAt": start_at, "maxResults": max_results}
        )

        chunk = data.get("issues", [])
        if not chunk:
            break

        issues.extend(chunk)
        start_at += len(chunk)

        if start_at >= data.get("total", 0):
            break

    return issues


def upsert_issues(cur, issues, status_to_column):
    sql = """
        MERGE dbo.JiraIssuesBoard AS t
        USING (SELECT ? AS BoardId, ? AS IssueKey) AS s
        ON t.BoardId=s.BoardId AND t.IssueKey=s.IssueKey
        WHEN MATCHED THEN
            UPDATE SET Summary=?, StatusId=?, StatusName=?, ColumnName=?,
                       Assignee=?, DueDate=?, Created=?, Updated=?
        WHEN NOT MATCHED THEN
            INSERT (BoardId, IssueKey, Summary, StatusId, StatusName, ColumnName,
                    Assignee, DueDate, Created, Updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    for it in issues:
        key = it.get("key")
        f = it.get("fields", {})

        summary = f.get("summary")
        status = (f.get("status") or {})
        status_id = str(status.get("id")) if status.get("id") is not None else None
        status_name = status.get("name")

        assignee = ((f.get("assignee") or {}).get("displayName"))
        duedate = f.get("duedate")  # YYYY-MM-DD or None
        created = to_dt(f.get("created"))
        updated = to_dt(f.get("updated"))

        column_name = status_to_column.get(status_id)

        cur.execute(
            sql,
            BOARD_ID, key,
            summary, status_id, status_name, column_name,
            assignee, duedate, created, updated,
            BOARD_ID, key,
            summary, status_id, status_name, column_name,
            assignee, duedate, created, updated
        )


def main():
    print("Checking configuration...")
    require_env("JIRA_BASE_URL", JIRA_BASE_URL)
    require_env("JIRA_EMAIL", JIRA_EMAIL)
    require_env("JIRA_API_TOKEN", JIRA_API_TOKEN)
    require_env("SQL_SERVER", SQL_SERVER)

    print("Fetching board column mapping...")
    cols = get_board_columns()
    status_to_column = {c["StatusId"]: c["ColumnName"] for c in cols}

    print("Fetching board issues...")
    issues = get_board_issues()

    print("Writing to SQL Server...")
    with sql_conn() as conn:
        cur = conn.cursor()
        upsert_columns(cur, cols)
        upsert_issues(cur, issues, status_to_column)
        conn.commit()

    print(f"Done. Loaded {len(issues)} issues for board {BOARD_ID} into SQL Server ({SQL_DATABASE}).")


if __name__ == "__main__":
    main()
