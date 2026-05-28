from flask import Flask, render_template, request, render_template_string, make_response, jsonify
from google import genai
from google.genai import types
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
    cred = credentials.Certificate('serviceAccountKey.json')
else:
    firebase_config = os.getenv('FIREBASE_CONFIG')
    if firebase_config:
        cred_dict = json.loads(firebase_config)
        cred = credentials.Certificate(cred_dict)
    else:
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
    link += "<a href=/webdemo>聊天機器人</a><hr>"
    link += "<a href=/AI>AI</a><hr>"    
    return link


# --- 2. Tool 函式 (強化極速響應，避免超時) ---
def get_movies_by_rate(user_rate: str) -> str:
    """
    根據使用者指定或提及的電影分級（如：普遍級、保護級、輔12級、輔15級、限制級），從資料庫查詢本週對應分級的新片清單。
    """
    try:
        db = firestore.client() 
        # 💡 請確保你的資料庫真的有「本週新片含分級」這個 Collection
        collection_ref = db.collection("本週新片含分級")
        query = collection_ref.where("rate", "==", user_rate).stream()
        
        results = []
        for doc in query:
            movie_data = doc.to_dict()
            name = movie_data.get("title", "未知電影")
            results.append(f"🎬 {name}")
        
        if results:
            content = "、".join(results)
            return f"為您找到「{user_rate}」的本週新片有：{content}"
        else:
            return f"後端查詢成功，但目前資料庫的「本週新片含分級」集合中，找不到分級為「{user_rate}」的電影物件。請確認是否有先執行過 /rate 爬蟲存檔。"
            
    except Exception as e:
        return f"後端在讀取 Firestore 時發生錯誤：{str(e)}。請檢查 Firebase 金鑰與網路連線。"


# --- 3. 穩定版 Webhook 路由 ---
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return jsonify({"fulfillmentText": "後端錯誤：未在 Vercel 環境變數中設定 GEMINI_API_KEY。"})
            
        client = genai.Client(api_key=api_key)

        req = request.get_json(force=True)
        query_result = req.get("queryResult", {})
        
        user_query = query_result.get("queryText", "").strip()
        action = query_result.get("action", "")
        intent_name = query_result.get("intent", {}).get("displayName", "")

        if not user_query:
            return jsonify({"fulfillmentText": "哈囉！我是徐瑞穎設計的電影助理，今天想聊點什麼？"})

        # 判定是否要開啟純聊天/接梗模式 (Fallback 或 Welcome)
        if action == "input.unknown" or "Fallback" in intent_name or "Welcome" in intent_name:
            system_instruction = (
                "你是徐瑞穎設計的 AI 助理。目前使用者跟你聊一些日常八卦、打招呼、或是奇奇怪怪的話題。\n"
                "請展現你的高情商與幽默感，熱情地接梗、陪使用者天南地北地聊天！不需要硬扯回電影，有趣好玩最重要！"
            )
        else:
            # 正常觸發「影片」Intent 時的設定
            system_instruction = (
                "你是徐瑞穎設計的電影推薦機器人助理。你非常有智慧、幽默且親切。\n"
                "當使用者詢問關於特定電影分級（如普遍級、保護級、限制級等）時，你必須且只能調用 `get_movies_by_rate` 工具來取得最新的資料庫電影名單，並以此回答。"
            )

        # 呼叫 Gemini
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[get_movies_by_rate],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="AUTO")
                )
            )
        )

        bot_reply = response.text
        if not bot_reply:
            bot_reply = "恩恩！聽起來很有意思。還有什麼想跟我聊聊的嗎？"

        return jsonify({
            "fulfillmentText": bot_reply,
            "fulfillmentMessages": [{"text": {"text": [bot_reply]}}]
        })

    except Exception as e:
        error_msg = f"後端 Webhook 崩潰，錯誤訊息：{str(e)}"
        return jsonify({
            "fulfillmentText": error_msg,
            "fulfillmentMessages": [{"text": {"text": [error_msg]}}]
        })


# --- 4. 靜態與簡單頁面 ---
@app.route("/mis")
def course_info(): 
    return "<h1>資訊管理導論</h1><a href=/>返回首頁</a>"

@app.route("/today")
def show_today(): 
    now = datetime.now()
    return render_template("today.html", datetime=str(now))

@app.route("/me")
def about_me(): 
    return render_template("mis2B.html")

@app.route("/webdemo")
def webdemo():
    return render_template("webdemo.html")


# --- 5. 傳值與計算 ---
@app.route("/welcome", methods=["GET"])
def welcome_user(): 
    user = request.args.get("u")
    d = request.args.get("d")
    c = request.args.get("c")
    return render_template("welcome.html", name=user, dep=d, course=c)

@app.route("/account", methods=["GET", "POST"])
def handle_account(): 
    if request.method == "POST":
        user = request.form.get("user")
        pwd = request.form.get("pwd")
        result = f"您輸入的帳號是：{user}; 密碼為：{pwd}"
        return result
    return render_template("account.html")

@app.route("/math", methods=["GET", "POST"])
def calculate_math(): 
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


# --- 6. Firestore 資料讀取 ---
@app.route("/read")
def read_firestore_all(): 
    output = ""
    db = firestore.client()
    collection_ref = db.collection("靜宜資管")    
    docs = collection_ref.order_by("lab", direction=firestore.Query.DESCENDING).get()    
    for doc in docs:         
        output += str(doc.to_dict()) + "<br>"    
    return output

@app.route("/ready")
def search_teacher(): 
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


# --- 7. 爬蟲與資料庫儲存 ---
@app.route("/spider_course")
def spider_pu_course(): 
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
                if keyword and keyword not in title:
                    continue
                introduce = "https://www.atmovies.com.tw" + link_tag.get("href")
                img_src = img_tag.get("src")
                if not img_src.startswith("http"):
                    img_src = "https://www.atmovies.com.tw" + img_src
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
    url = "https://www.atmovies.com.tw/movie/new/"
    Data = requests.get(url)
    Data.encoding = "utf-8"
    sp = BeautifulSoup(Data.text, "html.parser")
    lastUpdate = sp.find(class_="smaller09").text[5:]
    result = sp.select(".filmList")
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
            if rr == "G": rate = "普遍級"
            elif rr == "P": rate = "保護級"
            elif rr == "F2": rate = "輔12級"
            elif rr == "F5": rate = "輔15級"
            else: rate = "限制級"
        t = x.find(class_="runtime").text
        t1 = t.find("片長")
        t2 = t.find("分")
        showLength = t[t1+3:t2]
        t1 = t.find("上映日期")
        t2 = t.find("上映廳數")
        showDate = t[t1+5:t2-8]
        doc = {
            "title": title, "introduce": introduce, "picture": picture, "hyperlink": hyperlink,
            "showDate": showDate, "showLength": int(showLength), "rate": rate, "lastUpdate": lastUpdate
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
    result = sp.select(".filmListAllX li")
    total = 0
    for item in result:
        total += 1
        movie_id = item.find("a").get("href").replace("/movie/", "").replace("/", "")
        title = item.find(class_="filmtitle").text
        picture = "https://www.atmovies.com.tw" + item.find("img").get("src")
        hyperlink = "https://www.atmovies.com.tw" + item.find("a").get("href")
        showDate = item.find(class_="runtime").text[5:15]
        doc = { "title": title, "picture": picture, "hyperlink": hyperlink, "showDate": showDate, "lastUpdate": lastUpdate }
        doc_ref = db.collection("電影2B").document(movie_id)
        doc_ref.set(doc)
    R += "網站最近更新日期:" + lastUpdate + "<br>"
    R += "總共爬取" + str(total) + "部電影到資料庫"
    return R

@app.route("/search")
def search():
    keyword = request.args.get("keyword", "")
    db = firestore.client()
    docs = db.collection("電影2B").stream()
    results_html = ""
    found_count = 0
    for doc in docs:
        movie = doc.to_dict()
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
    html_layout = f"""
    <html>
        <body style="font-family: sans-serif; max-width: 800px; margin: auto;">
            <h2>電影資料庫搜尋</h2>
            <form action="/search" method="GET">
                <input type="text" name="keyword" value="{keyword}" style="padding: 5px; width: 200px;">
                <button type="submit">搜尋</button>
            </form><hr>
            <p>搜尋結果：找到 {found_count} 部電影</p>
            {results_html if found_count > 0 else "<p>沒有找到符合的電影。</p>"}
            <br><a href="/">回首頁</a>
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

CITY_CODES = {
    "臺北市": "F-D0047-061", "新北市": "F-D0047-069", "桃園市": "F-D0047-005", "臺中市": "F-D0047-073", 
    "臺南市": "F-D0047-077", "高雄市": "F-D0047-065", "基隆市": "F-D0047-049", "新竹縣": "F-D0047-009", 
    "新竹市": "F-D0047-053", "苗栗縣": "F-D0047-013", "彰化縣": "F-D0047-017", "南投縣": "F-D0047-021", 
    "雲林縣": "F-D0047-025", "嘉義縣": "F-D0047-029", "嘉義市": "F-D0047-057", "屏東縣": "F-D0047-033", 
    "宜蘭縣": "F-D0047-001", "花蓮縣": "F-D0047-041", "臺東縣": "F-D0047-037", "澎湖縣": "F-D0047-045", 
    "金門縣": "F-D0047-085", "連江縣": "F-D0047-081"
}

@app.route("/AI", methods=["GET", "POST"])
def AI():
    ai_response = ""
    user_question = ""
    if request.method == "POST":
        user_question = request.form.get("question", "").strip()
        if user_question:
            try:
                api_key = os.environ.get("GEMINI_API_KEY", "")
                if not api_key: ai_response = "錯誤：尚未設定 GEMINI_API_KEY 環境變數。"
                else:
                    client_ai = genai.Client(api_key=api_key)
                    response = client_ai.models.generate_content(model='gemini-2.5-flash', contents=user_question)
                    ai_response = response.text
            except Exception as e: ai_response = f"AI 發生錯誤：{str(e)}"
    html_template = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>瑞穎的簡易小 AI</title></head>
    <body style="font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 20px;">
        <form action="/AI" method="POST">
            <textarea name="question" style="width:100%; height:80px;">{{ user_question }}</textarea>
            <button type="submit" style="float:right; margin-top:10px;">送出</button>
        </form>
        {% if ai_response %}<div style="margin-top:30px; background:#f1f3f4; padding:15px; white-space:pre-wrap;">{{ ai_response }}</div>{% endif %}
        <br style="clear:both;"><hr><a href="/">返回首頁</a>
    </body></html>
    """
    return render_template_string(html_template, user_question=user_question, ai_response=ai_response)

@app.route("/weather")
def weather():
    target_city = request.args.get("city", "臺中市")
    city_code = CITY_CODES.get(target_city, "F-D0047-073")
    token = os.environ.get("CWA_TOKEN")
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{city_code}?Authorization={token}"
    response = requests.get(url)
    data = response.json()
    locations_root = data["records"]["Locations"][0]["Location"]
    weather_data = []
    for loc in locations_root:
        district = loc.get("LocationName", "未知")
        wx, rain_prob, temp = "無資料", "0", "--"
        for element in loc.get("WeatherElement", []):
            ename = element.get("ElementName")
            val_obj = element["Time"][0]["ElementValue"][0]
            if ename in ["天氣現象", "天氣", "Weather"]: wx = val_obj.get("Weather", val_obj.get("value", "未知"))
            elif ename in ["降雨機率", "ProbabilityOfPrecipitation"]: rain_prob = val_obj.get("ProbabilityOfPrecipitation", val_obj.get("value", "0"))
            elif ename in ["溫度", "Temperature"]: temp = val_obj.get("Temperature", val_obj.get("value", "--"))
        weather_data.append({"district": district, "wx": wx, "rain_prob": rain_prob, "temp": temp})
    html_template = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"></head><body><h2>{{ current_city }} 天氣預報</h2>
    <table border="1" cellpadding="5" style="border-collapse:collapse;">
        <tr><th>區域</th><th>天氣</th><th>氣溫</th><th>降雨機率</th></tr>
        {% for item in weather_data %}<tr><td>{{ item.district }}</td><td>{{ item.wx }}</td><td>{{ item.temp }}°C</td><td>{{ item.rain_prob }}%</td></tr>{% endfor %}
    </table></body></html>
    """
    return render_template_string(html_template, weather_data=weather_data, current_city=target_city)

if __name__ == "__main__":
    app.run(debug=True) 