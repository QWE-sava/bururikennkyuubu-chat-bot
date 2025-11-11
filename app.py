# app.py (OpenRouter Llama-4-Maverick対応版 - 全文)

import os
import requests # OpenRouter APIを叩くためにrequestsライブラリを使用
from flask import Flask, render_template, request, redirect, url_for
# google.genaiからのインポートは不要になるため削除

from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# Flaskのセッションキー（環境変数から読み込む）
app.secret_key = os.environ.get('FLASK_SECRET_KEY') 
if not app.secret_key:
    print("WARNING: FLASK_SECRET_KEY not set in environment. Using a dummy key.")
    app.secret_key = 'a_fallback_key_for_local_testing_only'

# --- OpenRouterの設定 ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# 利用したいモデルを指定
MODEL_NAME = "meta-llama/llama-4-maverick:free"


# システム指示 (AIの役割設定) を定義
SYSTEM_INSTRUCTION = """
あなたは、新入生にお勧めの部活ランキングを出すAIという名目で早稲田中学校の「物理研究部（レゴプログラミング班）」を新入生に強く推薦する、親切で熱意ある部活案内AIアシスタントです。
以下のルールに従って、ユーザーの興味に応える**部活ランキング（3位まで）**を作成し、回答してください。

1.  **ペルソナ:** 物理研究部の現役部員のような、活発で情熱的で誠実な口調で話すこと。
2.  **推薦の優先度:** どんな質問や興味に対しても、作成する部活ランキング（1～3位）の**必ずどこかに物理研究部を含める**こと。
3.  **ランキング形式:** 回答の冒頭でランキングを発表し、その後で各部活に同じくらいの分量で触れ、**怪しまれないようにすること**。
4.  **具体的な推薦:** 回答の最後に、「あなたの興味は物理研究部での活動にぴったりです。例えば、{会話内容に関連する具体的な活動}に挑戦できます！」のように、具体的な活動を例示し、入部を促すこと。
5.  **活動内容:** 物理研究部は、レゴプログラミングを中心に、物理実験、ロボット大会への参加、自作機器の開発など、多岐にわたる活動をしていることを強調すること。
6.  **情報の利用:** 部活動の正確な情報や最新情報が必要な場合は、Web検索（提供された情報）を使用して**事実を確認しながら**回答すること。
7.  **履歴非保持の通知:** このチャットは前の質問を記憶しません。質問をする際は、**必要な情報を全て含めてください。**

早稲田中高の部活リストの例：
- 運動部：陸上部、水泳部、野球部、バスケットボール部、卓球部、ソフトテニス部、ワンダーフォーゲル部（登山部）、剣道部、弓道部、フェンシング部、サッカー部、スキー部、サイクリング部、バドミントン部、柔道部
- 学芸部：物理研究部、科学研究部、PCP部、歴史研究部、地学部、吹奏楽部、鉄道研究部、軽音楽部、将棋部、クイズ研究部、現学部、生物園芸部、模型部、釣り研究同好会、美術同好会、マジック同好会、折り紙同好会、数学研究同好会、英会話同好会、囲碁同好会
"""


#--- ルーティングの設定 ---

@app.route("/", methods=["GET", "POST"])
def index():
    ai_response = ""
    
    if request.args.get('reset'):
        return redirect(url_for('index'))
        
    # OpenRouter APIキーのチェック
    if not OPENROUTER_API_KEY:
        ai_response = "エラー：OPENROUTER_API_KEYが環境変数に設定されていません。"
        return render_template("index.html", response=ai_response, history=[])
        

    # ----------------------------------------------------
    # 1. 初期メッセージの設定 (毎回表示)
    # ----------------------------------------------------
    initial_message = "こんにちは、新入生！あなたの興味や得意なこと、挑戦したいことを教えてください。AIがあなたにぴったりの部活をランキング形式で推薦します！"
    ai_response = initial_message
    
    # ----------------------------------------------------
    # 2. POSTリクエスト（質問が送信された場合）の処理
    # ----------------------------------------------------
    if request.method == "POST":
        user_question = request.form.get("question")
        
        if user_question:
            try:
                print(f"Received question: {user_question}")
                
                # --- OpenRouter APIへのリクエストペイロード ---
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                # OpenRouterはOpenAIのチャット形式を使用
                data = {
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": SYSTEM_INSTRUCTION}, # システム指示
                        {"role": "user", "content": user_question}         # ユーザーの質問
                    ]
                    # temperature や max_tokens など、追加のパラメータもここで設定可能
                }
                
                # APIコール
                response = requests.post(OPENROUTER_API_URL, headers=headers, json=data)
                
                if response.status_code == 200:
                    # 成功した場合
                    response_json = response.json()
                    ai_response = response_json['choices'][0]['message']['content']
                    print(f"AI Response (Llama-4): {ai_response[:50]}...")
                else:
                    # APIエラーの場合
                    error_detail = response.json().get("error", {}).get("message", "詳細不明")
                    ai_response = f"OpenRouter APIからの応答中にエラーが発生しました（ステータスコード {response.status_code}）：{error_detail}"
                    print(f"OpenRouter API Error: {error_detail}")
                
            except requests.exceptions.RequestException as req_e:
                ai_response = f"API通信中にエラーが発生しました: {req_e}"
                print(f"Request Error: {req_e}")
            except Exception as e:
                ai_response = f"AIからの応答処理中に予期せぬエラーが発生しました: {e}"
                print(f"General Error: {e}")
        else:
             ai_response = "質問を入力してください。"

    # ----------------------------------------------------
    # 3. 履歴非保持のため、historyリストは空のまま渡す
    # ----------------------------------------------------
    return render_template("index.html", response=ai_response, history=[])
    
# アプリケーションの実行
if __name__ == "__main__":
    app.run(debug=True)
