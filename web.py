from flask import Flask, render_template, request

from datetime import datetime
app = Flask(__name__)

@app.route("/")
def index():
    link = "<h1>歡迎進入徐瑞穎的網站!</h1>"
    link += "<a href = /mis>課程</a><hr>"
    link += "<a href = /today>現在日期時間</a><hr>"
    link += "<a href = /me>關於我</a><hr>"
    link += "<a href = /welcome?u=瑞穎&d=靜宜資管&c=資訊管理導論>Get傳值</a><hr>"
    link += "<a href = /account>Post傳值</a><hr>"
    link += "<a href = /math>次方與根號計算</a><hr>"

    return link

@app.route("/mis")
def course():
    return "<h1>資訊管理導論</h1><a href=/>返回首頁</a>"

@app.route("/today")
def today():
    now = datetime.now()
    return render_template("today.html", datetime = str(now))

@app.route("/me")
def me():    
    return render_template("mis2B.html")

@app.route("/welcome", methods=["GET"])
def welcome():
    user = request.values.get("u")
    d = request.values.get("d")
    c = request.values.get("c")
    return render_template("welcome.html", name=user,dep=d,course=c)

@app.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        user = request.form["user"]
        pwd = request.form["pwd"]
        result = "您輸入的帳號是：" + user + "; 密碼為：" + pwd 
        return result
    else:
        return render_template("account.html")

@app.route("/math", methods=["GET", "POST"])
def math():
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
        except ValueError:
            result = "請輸入有效的數字"

        return render_template("math.html", final_result=result)
    
    return render_template("math.html")


if __name__ == "__main__":
    app.run(debug=True)