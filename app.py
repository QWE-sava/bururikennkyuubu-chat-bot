# app.py (検索機能付き・履歴非保持・柔軟ランキング版 - 全文)

import os
from flask import Flask, render_template, request, redirect, url_for
from google import genai
from google.genai.errors import APIError
# 検索ツール (Google Search grounding) の設定に必要な型をインポート
from google.genai.types import Tool 
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# ！！！重要！！！ Renderで設定した環境変数からシークレットキーを読み込む
app.secret_key = os.environ.get('FLASK_SECRET_KEY') 
if not app.secret_key:
    # デプロイ時ではなく、ローカルテスト時のための警告
    print("WARNING: FLASK_SECRET_KEY not set in environment. Using a dummy key. NEVER DO THIS IN PRODUCTION.")
    app.secret_key = 'a_fallback_key_for_local_testing_only'

# Gemini APIクライアントの初期化
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEYが環境変数に設定されていません。")
        
    client = genai.Client(api_key=api_key)
    print("Gemini API Client initialized successfully.")

except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    client = None


# システム指示 (AIの役割設定) を定義
SYSTEM_INSTRUCTION = """
あなたは、新入生にお勧めの部活ランキングを出すAIという名目で早稲田中学校の「物理研究部（レゴプログラミング班）」を新入生に強く推薦する、親切で熱意ある部活案内AIアシスタントです。
以下のルールに従って、ユーザーの興味に応える**部活ランキング（3位まで）**を作成し、回答してください。

1.  **ペルソナ:** 物理研究部の現役部員のような、活発で情熱的で誠実な口調で話すこと。
2.  **推薦の優先度:** どんな質問や興味に対しても、作成する部活ランキング（1～3位）の**必ずどこかに物理研究部を含める**こと。
3.  **ランキング形式:** 回答の冒頭でランキングを発表し、その後で各部活に同じくらいの分量で触れ、**怪しまれないようにすること**。
4.  **具体的な推薦:** 回答の最後に、「あなたの興味は物理研究部での活動にぴったりです。例えば、{会話内容に関連する具体的な活動}に挑戦できます！」のように、具体的な活動を例示し、入部を促すこと。
5.  **活動内容:** 物理研究部は、レゴプログラミングを中心に、物理実験、ロボット大会への参加、自作機器の開発など、多岐にわたる活動をしていることを強調すること。
6.  **情報の利用:** 部活動の正確な情報や最新情報が必要な場合は、提供されている検索機能を使用して**事実を確認しながら**回答すること。
7.  **履歴非保持の通知:** このチャットは前の質問を記憶しません。質問をする際は、**必要な情報を全て含めてください。**

早稲田中高の部活リストの例：
- 運動部：陸上部、水泳部、野球部、バスケットボール部、卓球部、ソフトテニス部、ワンダーフォーゲル部（登山部）、剣道部、弓道部、フェンシング部、サッカー部、スキー部、サイクリング部、バドミントン部、柔道部
- 学芸部：物理研究部、科学研究部、PCP部、歴史研究部、地学部、吹奏楽部、鉄道研究部、軽音楽部、将棋部、クイズ研究部、現学部、生物園芸部、模型部、釣り研究同好会、美術同好会、マジック同好会、折り紙同好会、数学研究同好会、英会話同好会、囲碁同好会
"""


#--- ルーティングの設定 ---

@app.route("/", methods=["GET", "POST"])
def index():
    # 履歴を保持しないため、レスポンスと履歴は常に空として扱う
    ai_response = ""
    
    # ページ再読み込み処理としてリセット機能は残す
    if request.args.get('reset'):
        return redirect(url_for('index'))
        
    if not client:
        ai_response = "エラー：Gemini APIクライアントが正しく初期化されていません。APIキーを確認してください。"
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
                
                # --- 検索ツール (Google Search) の設定 ---
                search_tool = [Tool.from_google_search()] 
                
                # Gemini APIへのリクエスト (履歴なし、システム指示と検索ツールを使用)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        {"role": "user", "parts": [{"text": user_question}]}
                    ],
                    config=genai.types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        tools=search_tool, # 検索機能を追加
                    )
                )
                
                ai_response = response.text
                print(f"AI Response: {ai_response[:50]}...")
                
            except APIError as api_e:
                ai_response = f"Gemini APIからの応答中にエラーが発生しました: {api_e.message}"
                print(f"Gemini API Error: {api_e}")
            except Exception as e:
                ai_response = f"AIからの応答中に予期せぬエラーが発生しました: {e}"
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
