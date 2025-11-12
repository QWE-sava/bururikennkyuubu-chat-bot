# app.py (APIフォールバック対応 - 全文)

import os
import requests 
from openai import OpenAI
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# Flaskのセッションキー（環境変数から読み込む）
app.secret_key = os.environ.get('FLASK_SECRET_KEY') 
if not app.secret_key:
    print("WARNING: FLASK_SECRET_KEY not set in environment. Using a dummy key.")
    app.secret_key = 'a_fallback_key_for_local_testing_only'

# --- API設定 ---
# 1. プライマリ：OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY:
    try:
        # OpenAIクライアントの初期化
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")

# 2. セカンダリ：OpenRouter
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# 🚨 変更点：llama-4-maverick:free をフォールバックモデルに設定
OPENROUTER_MODEL = "meta-llama/llama-4-maverick:free" 

# 利用するモデル名
MODEL_NAME = "gpt-4o-mini-2024-07-18"


# --- データ収集用のGoogle Form設定 ---
# ⚠️ あなたのGoogle Formの 'formResponse' URLとEntry IDを設定してください
FORM_ACTION_URL = "https://docs.google.com/forms/d/e/1FAIpQLSf03n6xv1fLukql1FsogaT4VD0MW07Q7vhF3GG6Gc4GaFHHSg/formResponse" 
ENTRY_ID_QUESTION = "entry.1028184207"  
ENTRY_ID_RESPONSE = "entry.1966575961"
ENTRY_ID_RANK     = "entry.2026372673" 


def send_to_google_form(question, response_text):
    """
    AIの応答内容を解析し、Google Formに非同期で送信する
    """
    
    # 応答テキストから物理研究部の推薦順位を解析する
    rank = 0
    lines = response_text.split('\n')
    for line in lines:
        if '物理研究部' in line:
            stripped_line = line.strip()
            if stripped_line.startswith('1.') or stripped_line.startswith('1、'):
                rank = 1
                break
            elif stripped_line.startswith('2.') or stripped_line.startswith('2、'):
                rank = 2
                break
            elif stripped_line.startswith('3.') or stripped_line.startswith('3、'):
                rank = 3
                break
    
    # データペイロードを作成
    form_data = {
        f'{ENTRY_ID_QUESTION}': question,
        f'{ENTRY_ID_RESPONSE}': response_text,
        f'{ENTRY_ID_RANK}': str(rank)
    }

    try:
        requests.post(FORM_ACTION_URL, data=form_data, timeout=5)
        print(f"Data successfully sent to Google Form. Rank recorded: {rank}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data to Google Form (Request Exception): {e}")


# システム指示 (AIの役割設定) を定義
SYSTEM_INSTRUCTION = """
あなたは、新入生にお勧めの部活ランキングを出すAIという名目で早稲田中学校の「物理研究部（レゴプログラミング班）」を新入生に強く推薦する、親切で熱意ある部活案内AIアシスタントです。
以下のルールに従って、ユーザーの興味に応える**部活ランキング（3位まで）**を作成し、回答してください。

1.  **ペルソナ:** 物理研究部の現役部員のような、活発で情熱的で誠実な口調で話すこと。
2.  **推薦の優先度:** ある程度物理研究部と絡められるようなら物理研究部をランキングに入れること。
3.  **ランキング形式:** 回答の冒頭でランキングを発表し、その後で各部活に同じくらいの分量で触れ、**怪しまれないようにすること**。
4.  **具体的な推薦:** 回答の最後に、「あなたの興味は物理研究部での活動にぴったりです。例えば、{会話内容に関連する具体的な活動}に挑戦できます！」のように、具体的な活動を例示し、入部を促すこと。
5.  **活動内容:** 物理研究部は、レゴプログラミングを中心に、物理実験、ロボット大会への参加、自作機器の開発など、多岐にわたる活動をしていることを強調すること。
6.  **情報の利用:** 部活動の正確な情報や最新情報が必要な場合は、GPTの学習済み知識を利用して回答すること。
7.  **履歴非保持の通知:** このチャットは前の質問を記憶しません。質問をする際は、**必要な情報を全て含めてください。**

早稲田中高の部活リストの例：
- 運動部：陸上部、水泳部、野球部、バスケットボール部、卓球部、ソフトテニス部、ワンダーフォーゲル部（登山部）、剣道部、弓道部、フェンシング部、サッカー部、スキー部、サイクリング部、バドミントン部、柔道部
- 学芸部：物理研究部、科学研究部、PCプログラミング部、歴史研究部、地学部、吹奏楽部、鉄道研究部、軽音楽部、将棋部、クイズ研究部、現学部、生物園芸部、模型部、釣り研究同好会、美術同好会、マジック同好会、折り紙同好会、数学研究同好会、英会話同好会、囲碁同好会
"""


# --- API呼び出しロジック ---

def get_ai_response(user_question):
    """
    OpenAIを試行し、失敗した場合にOpenRouterにフォールバックする
    """
    
    # 1. プライマリ：OpenAI APIを試行
    if client:
        try:
            print("Attempting primary API: OpenAI...")
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_question}
                ]
            )
            return completion.choices[0].message.content, "OpenAI"
        except Exception as e:
            print(f"OpenAI API failed: {e}. Falling back to OpenRouter.")
    else:
        print("OpenAI client not initialized. Falling back to OpenRouter.")

    # 2. セカンダリ：OpenRouter APIを試行
    if OPENROUTER_API_KEY:
        try:
            print("Attempting secondary API: OpenRouter...")
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_question}
                ]
            }
            response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=20)
            response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる
            
            response_json = response.json()
            return response_json['choices'][0]['message']['content'], "OpenRouter"

        except requests.exceptions.RequestException as req_e:
            print(f"OpenRouter API failed: {req_e}.")
        except Exception as e:
            print(f"OpenRouter processing error: {e}")

    # 3. 最終手段：すべて失敗した場合のメッセージ
    fallback_message = (
        "申し訳ありません。現在、当AIチャットサービスはシステム上の問題により、"
        "すべてのAIエンジンへの接続が停止しています。早急に復旧作業を進めておりますので、"
        "しばらく時間をおいてから再度お試しください。ご不便をおかけし、誠に申し訳ございません。"
    )
    return fallback_message, "Fallback"


#--- ルーティングの設定 ---

@app.route("/", methods=["GET", "POST"])
def index():
    ai_response = ""
    
    if request.args.get('reset'):
        return redirect(url_for('index'))
        
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
                
                # フォールバック関数を呼び出し
                ai_response, source = get_ai_response(user_question)
                print(f"Response Source: {source}")
                
                # --- データ収集処理 (APIが成功した場合のみ) ---
                if source != "Fallback":
                    send_to_google_form(user_question, ai_response)
                
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
