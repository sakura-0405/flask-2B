import requests
import urllib3
from bs4 import BeautifulSoup

url = "https://www1.pu.edu.tw/~tcyang/course.html"
Data = requests.get(url, verify=False)
Data.encoding = "utf-8"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sp = BeautifulSoup(Data.text, "html.parser")
result=sp.select(".team-box a")
for i in result:
	print(i.text, i.get("href"))
	print()
