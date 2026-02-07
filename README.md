[Project Banner](assets/JiraBoard.mp4)


# Jira Board → SQL Server (SSMS Reporting)

This project syncs **Jira Cloud Kanban board data** into **Microsoft SQL Server** so you can build reports in **SSMS** (or Power BI / Excel).  
It pulls:

- **Board configuration** (maps **Board Columns ↔ Jira Statuses**)
- **Board issues** (Key, Summary, Status, Column, Assignee, Due Date, Created/Updated)
- Writes/updates data in SQL Server using **MERGE (Upsert)** so you can run the script multiple times safely.

---

## What This Solves

Jira Kanban boards are great visually, but it's hard to create custom reports like:

- Count issues in each column (IDEA / TO DO / IN PROGRESS / IN REVIEW)
- Track due dates and overdue cards
- List recently updated work items
- Build custom dashboards from SQL queries

This repository converts board data into SQL tables that you can query.

---

## How It Works

1. Authenticates to Jira Cloud using **Email + API Token**
2. Calls Jira Agile API:
   - `/rest/agile/1.0/board/{boardId}/configuration`  
     → Returns board columns and status mapping
   - `/rest/agile/1.0/board/{boardId}/issue`  
     → Returns issues on the board (paginated)
3. Saves results to SQL Server tables:
   - `dbo.JiraBoardColumns` — board column ↔ status mapping
   - `dbo.JiraIssuesBoard` — issues with current status and mapped column

---

## Repository Contents

- `jira_board_to_sql.py` — main sync script
- `requirements.txt` — Python dependencies
- `.env` — configuration (NOT committed; add to `.gitignore`)
- `sql/` (optional) — SQL scripts for DB setup (you can create this folder)

---

## Prerequisites

### Jira Cloud
- Jira Cloud site (example: `https://18mcr007jira.atlassian.net`)
- An Atlassian **API token** (required for REST API)

Create API token:
- Atlassian Account → **Security** → **API tokens** → **Create API token**

> Jira Cloud does **not** allow direct database connections. Data must be fetched via API.

### SQL Server
- SQL Server installed locally or accessible on network
- SSMS 2022 for running SQL queries (optional but recommended)
- Install **ODBC Driver 18 for SQL Server** on the machine running the script

### Python
- Recommended Python: **3.11 (64-bit)** for easiest `pyodbc` installation.
- If `pyodbc` fails on very new Python versions, use Python 3.11.

---

## Setup Instructions

### 1) Database Setup (Run in SSMS)

Open SSMS and run the following script:

```sql
/* Create DB if it doesn't exist */
IF DB_ID(N'JiraReporting') IS NULL
BEGIN
    CREATE DATABASE JiraReporting;
END
GO

USE JiraReporting;
GO

/* Board column/status mapping */
IF OBJECT_ID(N'dbo.JiraBoardColumns', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.JiraBoardColumns (
        BoardId        INT NOT NULL,
        ColumnName     NVARCHAR(200) NOT NULL,
        StatusId       NVARCHAR(50) NOT NULL,
        StatusName     NVARCHAR(200) NULL,
        CONSTRAINT PK_JiraBoardColumns PRIMARY KEY (BoardId, StatusId)
    );
END
GO

/* Issues on the board */
IF OBJECT_ID(N'dbo.JiraIssuesBoard', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.JiraIssuesBoard (
        BoardId        INT NOT NULL,
        IssueKey       NVARCHAR(50) NOT NULL,
        Summary        NVARCHAR(500) NULL,
        StatusId       NVARCHAR(50)  NULL,
        StatusName     NVARCHAR(200) NULL,
        ColumnName     NVARCHAR(200) NULL,
        Assignee       NVARCHAR(200) NULL,
        DueDate        DATE          NULL,
        Created        DATETIME2     NULL,
        Updated        DATETIME2     NULL,
        CONSTRAINT PK_JiraIssuesBoard PRIMARY KEY (BoardId, IssueKey)
    );
END
GO
```

### 2) Project Setup

**Clone the repository:**
```bash
git clone https://github.com/iamkumar-gaurav/Jira-SQL-Analysis.git
cd Jira-SQL-Analysis
```

**Create & activate a virtual environment (Windows):**
```bash
python -m venv jiravenv
.\jiravenv\Scripts\Activate.ps1
```

**Create `requirements.txt` (or ensure it exists) with:**
```txt
requests==2.32.3
python-dotenv==1.0.1
pyodbc==5.1.0
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

### 3) Configuration (.env)

Create a file named `.env` in the repo root:

```env
JIRA_BASE_URL=https://YOUR-DOMAIN.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your_api_token_here

BOARD_ID=2

SQL_SERVER=localhost
SQL_DATABASE=JiraReporting
SQL_USERNAME=your_sql_username
SQL_PASSWORD=your_sql_password
```

**SQL_SERVER examples:**
- Local default instance: `localhost` or `.`
- SQL Express: `.\SQLEXPRESS`

### 4) Run the Sync Script

```bash
python jira_board_to_sql.py
```

**Expected output:**
```
Checking configuration...
Fetching board column mapping...
Fetching board issues...
Writing to SQL Server...
Done. Loaded X issues for board Y into SQL Server.
```

---

## Example SQL Queries

Once data is loaded, you can run queries like:

**Count issues by column:**
```sql
SELECT ColumnName, COUNT(*) AS IssueCount
FROM dbo.JiraIssuesBoard
WHERE BoardId = 2
GROUP BY ColumnName
ORDER BY IssueCount DESC;
```

**Find overdue issues:**
```sql
SELECT IssueKey, Summary, Assignee, DueDate
FROM dbo.JiraIssuesBoard
WHERE DueDate < GETDATE()
  AND StatusName NOT IN ('Done', 'Closed')
ORDER BY DueDate;
```

**Recently updated issues:**
```sql
SELECT TOP 10 IssueKey, Summary, Updated
FROM dbo.JiraIssuesBoard
ORDER BY Updated DESC;
```

---

## Troubleshooting

### `pyodbc` installation fails
- Use Python 3.11 (64-bit)
- Ensure ODBC Driver 18 for SQL Server is installed

### Connection to SQL Server fails
- Verify SQL Server is running
- Check server name (use `localhost` or `.\SQLEXPRESS`)
- Ensure SQL Server allows SQL authentication if using username/password

### Jira API returns 401 Unauthorized
- Verify your API token is correct
- Check that `JIRA_EMAIL` matches your Atlassian account email

---



## Contributing

Pull requests welcome! Please open an issue first to discuss major changes.
