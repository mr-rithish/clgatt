from fastapi import FastAPI
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

app = FastAPI()

# Define request schema
class LoginRequest(BaseModel):
    htno: str
    password: str

@app.post("/get_student_data")
def get_student_data(login: LoginRequest):
    htno = login.htno
    password = login.password
    
    BASE_URL = "https://erp.vce.ac.in/sinfo/"
    LOGIN_URL = BASE_URL + "Default.aspx"
    ATTENDANCE_URL = BASE_URL + "DashBoard.aspx"

    session = requests.Session()

    # Step 1: Get login page
    resp = session.get(LOGIN_URL)
    soup = BeautifulSoup(resp.text, "html.parser")

    viewstate = soup.find("input", {"id": "__VIEWSTATE"})["value"]
    viewstategen = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"]
    eventvalidation = soup.find("input", {"id": "__EVENTVALIDATION"})["value"]

    # Step 2: Login payload
    payload = {
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstategen,
        "__EVENTVALIDATION": eventvalidation,
        "txt_HTNO": htno,
        "txt_Password": password,
        "btn_Login": "Sign in"
    }

    # Step 3: Post login
    resp2 = session.post(LOGIN_URL, data=payload)

    # Step 4: Load attendance dashboard
    resp3 = session.get(ATTENDANCE_URL)
    soup = BeautifulSoup(resp3.text, "html.parser")

    # Step 5: Find popup link
    att_div = soup.find("div", {"id": "divAttSummary"})
    popup_url = None
    if att_div:
        for a in att_div.find_all("a", onclick=True):
            onclick = a["onclick"]
            m = re.search(r"popUp\('([^']+)'", onclick)
            if m:
                popup_url = m.group(1)
                break
    if not popup_url:
        return {"error": "Attendance popup not found"}

    full_popup_url = BASE_URL + popup_url
    resp4 = session.get(full_popup_url)
    soup = BeautifulSoup(resp4.text, "html.parser")

    # Extract tables
    table1 = soup.find_all("table", {"class": "tableclass"})
    df_overall, df_subject = None, None

    if len(table1) > 0:
        df_overall = pd.read_html(str(table1[0]))[0]
    if len(table1) > 1:
        df_subject = pd.read_html(str(table1[1]))[0]

    # Student info
    stu_table_outer = soup.find("table", {"id": "TblStuInfo"})
    stu_table_inner = stu_table_outer.find("table") if stu_table_outer else None
    student_data = {}
    if stu_table_inner:
        for tr in stu_table_inner.find_all("tr"):
            tds = tr.find_all("td")
            tds = [td for td in tds if not td.find("img")]
            for i in range(0, len(tds), 3):
                if i+2 < len(tds):
                    key = tds[i].get_text(strip=True)
                    val = tds[i+2].get_text(strip=True)
                    student_data[key] = val

    # Return JSON
    return {
        "student_info": student_data,
        "overall_summary": df_overall.to_dict(orient="records") if df_overall is not None else [],
        "subject_summary": df_subject.to_dict(orient="records") if df_subject is not None else []
    }