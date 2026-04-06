import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    response = requests.get("https://lms.lilit.lk/all-courses", verify=False)
    with open("courses.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Saved courses.html")
except Exception as e:
    print(e)
