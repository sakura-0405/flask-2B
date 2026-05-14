from flask import Flask, render_template, request, render_template_string, make_response, jsonify
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase 初始化配置 ---
if os.path.exists('serviceAccountKey.json'):
    # 本地環境
    cred = credentials.Certificate('serviceAccountKey.json')
else:
    # 雲端環境 (例如 Vercel)
    firebase_config = os.getenv('FIREBASE_CONFIG')
    if firebase_config:
        cred_dict = json.loads(firebase_config)
        cred = credentials.Certificate(cred_dict)
    else:
        # 如果環境變數也沒抓到，這裡可以放個備案或拋出錯誤
        cred = None 

if cred and not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

app = Flask(__name__)

# --- 1. 首頁 ---
@app.route("/")
def index():
    link = "<h1>歡迎進入徐瑞穎的網站!</h1>"
    link += "<a href=/mis>課程</a><hr>"
    link += "<a href=/today>現在日期時間</a><hr>"
    link += "<a href=/me>關於我</a><hr>"
    link += "<a href='/welcome?u=瑞穎&d=靜宜資管&c=資訊管理導論'>Get傳值</a><hr>"
    link += "<a href=/account>Post傳值</a><hr>"
    link += "<a href=/math>次方與根號計算</a><hr>"
    link += "<a href=/read>讀取Firestore資料</a><hr>"
    link += "<a href=/ready>讀取Firestore資料(根據關鍵字)</a><hr>"
    link += "<a href=/spider_course>爬取子青老師本學期課程</a><hr>"
    link += "<a href=/get_movies>爬取即將上映電影</a><hr>"
    link += "<a href=/get_moviesbase>爬取即將上映電影並存入資料庫</a><hr>"
    link += "<a href=/search>查詢資料庫內的電影</a><hr>"
    link += "<a href=/road>台中市十大肇事路口</a><hr>"
    link += "<a href=/weather>台中市天氣和降雨機率</a><hr>"
    link += "<a href=/rate>本周新片進DB</a><hr>"
    link += "<a href=/webhook>webhook</a><hr>"
    return link

app.route("/webhook", methods=["POST"])
def webhook():
    # build a request object
    req = request.get_json(force=True)
    # fetch queryResult from json
    action =  req.get("queryResult").get("action")
    msg =  req.get("queryResult").get("queryText")
    info = "動作：" + action + "； 查詢內容：" + msg
    return make_response(jsonify({"fulfillmentText": info}))


# --- 2. 靜態/簡單頁面 ---
@app.route("/mis")
def course_info(): # 變數名改為 course_info
    return "<h1>資訊管理導論</h1><a href=/>返回首頁</a>"

@app.route("/today")
def show_today(): # 變數名改為 show_today
    now = datetime.now()
    return render_template("today.html", datetime=str(now))

@app.route("/me")
def about_me(): # 變數名改為 about_me
    return render_template("mis2B.html")

# --- 3. 傳值與計算 ---
@app.route("/welcome", methods=["GET"])
def welcome_user(): # 變數名改為 welcome_user
    user = request.args.get("u")
    d = request.args.get("d")
    c = request.args.get("c")
    return render_template("welcome.html", name=user, dep=d, course=c)

@app.route("/account", methods=["GET", "POST"])
def handle_account(): # 變數名改為 handle_account
    if request.method == "POST":
        user = request.form.get("user")
        pwd = request.form.get("pwd")
        result = f"您輸入的帳號是：{user}; 密碼為：{pwd}"
        return result
    return render_template("account.html")

@app.route("/math", methods=["GET", "POST"])
def calculate_math(): # 變數名改為 calculate_math
    result = ""
    if request.method == "POST":
        try:
            x = float(request.form.get("x"))
            y = float(request.form.get("y"))
            opt = request.form.get("opt")
            
            if opt == "∧":
                result = x ** y
            elif opt == "√":
                if y == 0:
                    result = "錯誤：數學不能開 0 的根"
                else:
                    result = x ** (1 / y)
            else:
                result = "請選擇正確的運算符號"
        except (ValueError, TypeError):
            result = "請輸入有效的數字"
    return render_template("math.html", final_result=result)

# --- 4. Firestore 資料讀取 ---
@app.route("/read")
def read_firestore_all(): # 變數名改為 read_firestore_all
    output = ""
    db = firestore.client()
    collection_ref = db.collection("靜宜資管")    
    docs = collection_ref.order_by("lab", direction=firestore.Query.DESCENDING).get()    
    for doc in docs:         
        output += str(doc.to_dict()) + "<br>"    
    return output

@app.route("/ready")
def search_teacher(): # 變數名改為 search_teacher
    keyword = request.args.get("keyword", "").strip()
    db = firestore.client()
    collection_ref = db.collection("靜宜資管")
    teachers_found = []

    if keyword:
        docs = collection_ref.get()
        for doc in docs:
            teacher = doc.to_dict()
            if keyword in teacher.get("name", ""):
                teachers_found.append(teacher)
    
    return render_template("search.html", keyword=keyword, results=teachers_found)

# --- 5. 爬蟲部分 ---
@app.route("/spider_course")
def spider_pu_course(): # 變數名改為 spider_pu_course
    info = ""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = "https://www1.pu.edu.tw/~tcyang/course.html"
    response = requests.get(url, verify=False)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    result = soup.select(".team-box a")
    for i in result:
        info += f"{i.text} : <a href='{i.get('href')}'>{i.get('href')}</a><br>"
    return info

@app.route("/get_movies")
def movie_crawler():
    # 1. 取得使用者輸入的關鍵字 (例如: /get_movies?keyword=英雄)
    keyword = request.args.get("keyword", "").strip()
    
    html_output = f"<h1>即將上映電影查詢</h1>"
    html_output += f"""
        <form action="/get_movies" method="get">
            <input type="text" name="keyword" placeholder="輸入電影名稱關鍵字" value="{keyword}">
            <button type="submit">搜尋</button>
        </form><hr>
    """

    url = "https://www.atmovies.com.tw/movie/next/"
    try:
        response = requests.get(url)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(".filmListAllX li")
        
        found_count = 0
        for item in items:
            link_tag = item.find("a")
            img_tag = item.find("img")
            
            if link_tag and img_tag:
                title = img_tag.get("alt", "")
                
                # 2. 關鍵字過濾邏輯：如果關鍵字不在片名中，就跳過這一個
                if keyword and keyword not in title:
                    continue
                
                introduce = "https://www.atmovies.com.tw" + link_tag.get("href")
                img_src = img_tag.get("src")
                
                if not img_src.startswith("http"):
                    img_src = "https://www.atmovies.com.tw" + img_src

                # 3. 拼接符合條件的 HTML
                html_output += f'<a href="{introduce}"><b>{title}</b></a><br>'
                html_output += f'<img src="{img_src}" style="max-width:200px;"><br><br>'
                found_count += 1
        
        if found_count == 0:
            html_output += f"<p>抱歉，找不到包含『{keyword}』的電影。</p>"
            
    except Exception as e:
        html_output += f"抓取資料發生錯誤: {e}"

    html_output += '<br><a href="/">返回首頁</a>'
    return html_output

@app.route("/rate")
def rate():
    #本週新片
    url = "https://www.atmovies.com.tw/movie/new/"
    Data = requests.get(url)
    Data.encoding = "utf-8"
    sp = BeautifulSoup(Data.text, "html.parser")
    lastUpdate = sp.find(class_="smaller09").text[5:]
    print(lastUpdate)
    print()

    result=sp.select(".filmList")

    for x in result:
        title = x.find("a").text
        introduce = x.find("p").text

        movie_id = x.find("a").get("href").replace("/", "").replace("movie", "")
        hyperlink = "http://www.atmovies.com.tw/movie/" + movie_id
        picture = "https://www.atmovies.com.tw/photo101/" + movie_id + "/pm_" + movie_id + ".jpg"

        r = x.find(class_="runtime").find("img")
        rate = ""
        if r != None:
            rr = r.get("src").replace("/images/cer_", "").replace(".gif", "")
            if rr == "G":
                rate = "普遍級"
            elif rr == "P":
                rate = "保護級"
            elif rr == "F2":
                rate = "輔12級"
            elif rr == "F5":
                rate = "輔15級"
            else:
                rate = "限制級"

        t = x.find(class_="runtime").text

        t1 = t.find("片長")
        t2 = t.find("分")
        showLength = t[t1+3:t2]

        t1 = t.find("上映日期")
        t2 = t.find("上映廳數")
        showDate = t[t1+5:t2-8]

        doc = {
            "title": title,
            "introduce": introduce,
            "picture": picture,
            "hyperlink": hyperlink,
            "showDate": showDate,
            "showLength": int(showLength),
            "rate": rate,
            "lastUpdate": lastUpdate
        }

        db = firestore.client()
        doc_ref = db.collection("本週新片含分級").document(movie_id)
        doc_ref.set(doc)
    return "本週新片已爬蟲及存檔完畢，網站最近更新日期為：" + lastUpdate

@app.route("/get_moviesbase")
def movie_base():
    R = ""

    db = firestore.client()
    url = "http://www.atmovies.com.tw/movie/next/"
    Data = requests.get(url)
    Data.encoding = "utf-8"

    sp = BeautifulSoup(Data.text, "html.parser")
    lastUpdate = sp.find(class_="smaller09").text.replace("更新時間：", "")


    result=sp.select(".filmListAllX li")
    total = 0
    for item in result:
      total += 1
      movie_id = item.find("a").get("href").replace("/movie/", "").replace("/", "")
      title = item.find(class_="filmtitle").text
      picture = "https://www.atmovies.com.tw" + item.find("img").get("src")
      hyperlink = "https://www.atmovies.com.tw" + item.find("a").get("href")

      showDate = item.find(class_="runtime").text[5:15]

      doc = {
          "title": title,
          "picture": picture,
          "hyperlink": hyperlink,
          "showDate": showDate,
          "lastUpdate": lastUpdate
      }

      doc_ref = db.collection("電影2B").document(movie_id)
      doc_ref.set(doc)

    R += "網站最近更新日期:" + lastUpdate + "<br>"
    R += "總共爬取" + str(total) + "部電影到資料庫"

    return R

@app.route("/search")
def search():
    # 取得使用者輸入的關鍵字
    keyword = request.args.get("keyword", "")
    
    db = firestore.client()
    # 這裡抓取「電影2B」集合中所有的文件
    # 注意：若電影數量超過數百部，建議使用 Firestore 的 where 查詢來優化
    docs = db.collection("電影2B").stream()

    results_html = ""
    found_count = 0

    for doc in docs:
        movie = doc.to_dict()
        # 檢查關鍵字是否在電影標題中 (包含搜尋)
        if keyword in movie.get("title", ""):
            found_count += 1
            results_html += f"""
                <div style="border: 1px solid #ddd; padding: 10px; margin: 10px; border-radius: 8px;">
                    <img src="{movie['picture']}" style="width: 120px; float: left; margin-right: 15px;">
                    <h4>{movie['title']}</h4>
                    <p>上映日期：{movie['showDate']}</p>
                    <a href="{movie['hyperlink']}" target="_blank">點我查看詳情</a>
                    <div style="clear: both;"></div>
                </div>
            """

    # 組合搜尋頁面的外殼
    html_layout = f"""
    <html>
        <head><title>電影搜尋</title></head>
        <body style="font-family: sans-serif; max-width: 800px; margin: auto;">
            <h2>電影資料庫搜尋</h2>
            <form action="/search" method="GET">
                <input type="text" name="keyword" value="{keyword}" placeholder="輸入電影名稱..." style="padding: 5px; width: 200px;">
                <button type="submit">搜尋</button>
            </form>
            <hr>
            <p>搜尋結果：找到 {found_count} 部電影</p>
            {results_html if found_count > 0 else "<p>沒有找到符合的電影。</p>"}
            <br>
            <a href="/">回首頁</a>
        </body>
    </html>
    """
    return html_layout

@app.route("/road")
def road(): 
    Ro = "<h1>台中市十大肇事路口(113年10月) 作者 : 徐瑞穎</h1><br>"
    url = "https://datacenter.taichung.gov.tw/swagger/OpenData/a1b899c0-511f-4e3d-b22b-814982a97e41"
    Data = requests.get(url)

    JsonData = json.loads(Data.text)
    for item in JsonData:
        Ro += item["路口名稱"] + "，原因 : " + item["主要肇因"]  + "，件數" + item["總件數"] + "<br>"
    return Ro

# 全台縣市與 API 代碼對照表 (F-D0047 系列)
CITY_CODES = {
    "臺北市": "F-D0047-061", "新北市": "F-D0047-069", "桃園市": "F-D0047-005",
    "臺中市": "F-D0047-073", "臺南市": "F-D0047-077", "高雄市": "F-D0047-065",
    "基隆市": "F-D0047-049", "新竹縣": "F-D0047-009", "新竹市": "F-D0047-053",
    "苗栗縣": "F-D0047-013", "彰化縣": "F-D0047-017", "南投縣": "F-D0047-021",
    "雲林縣": "F-D0047-025", "嘉義縣": "F-D0047-029", "嘉義市": "F-D0047-057",
    "屏東縣": "F-D0047-033", "宜蘭縣": "F-D0047-001", "花蓮縣": "F-D0047-041",
    "臺東縣": "F-D0047-037", "澎湖縣": "F-D0047-045", "金門縣": "F-D0047-085",
    "連江縣": "F-D0047-081"
}

@app.route("/weather")
def weather():
    target_city = request.args.get("city", "臺中市")
    city_code = CITY_CODES.get(target_city, "F-D0047-073")
    
    # 修改處：從環境變數讀取 CWA_TOKEN
    token = os.environ.get("CWA_TOKEN")
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{city_code}?Authorization={token}"

    response = requests.get(url)
    data = response.json()
    locations_root = data["records"]["Locations"][0]["Location"]

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: "Microsoft JhengHei", sans-serif; background-color: #f0f2f5; padding: 20px; }
            .container { max-width: 800px; margin: auto; background: white; padding: 25px; border-radius: 15px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
            .selector-section { text-align: center; margin-bottom: 30px; padding: 20px; background: #e8f0fe; border-radius: 10px; }
            select { padding: 10px 20px; font-size: 16px; border-radius: 5px; border: 1px solid #ddd; outline: none; }
            button { padding: 10px 20px; font-size: 16px; background: #1a73e8; color: white; border: none; border-radius: 5px; cursor: pointer; }
            h2 { color: #1a73e8; text-align: center; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th { background: #1a73e8; color: white; padding: 12px; }
            td { padding: 12px; border-bottom: 1px solid #eee; text-align: center; }
            .temp { color: #e67e22; font-weight: bold; }
            .rain-high { color: #d93025; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="selector-section">
                <form action="/weather" method="get">
                    <label>選擇縣市：</label>
                    <select name="city">
                        {% for city in city_list %}
                        <option value="{{ city }}" {% if city == current_city %}selected{% endif %}>{{ city }}</option>
                        {% endfor %}
                    </select>
                    <button type="submit">查詢</button>
                </form>
            </div>
            <h2>📍 {{ current_city }} 各區天氣預報</h2>
            <table>
                <tr><th>區域</th><th>天氣</th><th>氣溫</th><th>降雨機率</th></tr>
                {% for item in weather_data %}
                <tr>
                    <td><strong>{{ item.district }}</strong></td>
                    <td>{{ item.wx }}</td>
                    <td class="temp">{{ item.temp }}°C</td>
                    <td class="{{ 'rain-high' if item.rain_prob|int >= 30 else '' }}">{{ item.rain_prob }}%</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </body>
    </html>
    """

    weather_data = []
    for loc in locations_root:
        district = loc.get("LocationName", "未知")
        wx, rain_prob, temp = "無資料", "0", "--"
        for element in loc.get("WeatherElement", []):
            ename = element.get("ElementName")
            val_obj = element["Time"][0]["ElementValue"][0]
            if ename in ["天氣現象", "天氣", "Weather"]:
                wx = val_obj.get("Weather", val_obj.get("value", "未知"))
            elif ename in ["降雨機率", "ProbabilityOfPrecipitation"]:
                rain_prob = val_obj.get("ProbabilityOfPrecipitation", val_obj.get("value", "0"))
            elif ename in ["溫度", "Temperature"]:
                temp = val_obj.get("Temperature", val_obj.get("value", "--"))
        weather_data.append({"district": district, "wx": wx, "rain_prob": rain_prob, "temp": temp})

    return render_template_string(html_template, weather_data=weather_data, city_list=list(CITY_CODES.keys()), current_city=target_city)

if __name__ == "__main__":
    app.run()