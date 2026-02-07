
import os, requests
from dotenv import load_dotenv
load_dotenv()
base=os.getenv("JIRA_BASE_URL")
email=os.getenv("JIRA_EMAIL")
token=os.getenv("JIRA_API_TOKEN")
r=requests.get(f"{base}/rest/agile/1.0/board", auth=(email, token))
print(r.status_code)
print(r.text[:800])

