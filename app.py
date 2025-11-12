# app.py (PRGパターン実装版 - 全文)

import os
import requests 
from openai import OpenAI
from flask import Flask, render_template, request, redirect, url_for, session # session を使用
from dotenv import load_dotenv
import time 

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') 
if not app.secret_key:
    print("WARNING: FLASK_SECRET_KEY not set in environment. Using a dummy key.")
    app.secret_key = 'a_fallback_key_for_local_testing_only'

# --- API設定 (省略) ---
# ... (APIキーやモデルの設定は変更なし) ...
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "meta-llama/llama-4-maverick:free" 
MODEL_NAME = "gpt-4o-mini-2024-07-18"

# --- Google Form設定 (省略) ---
FORM_ACTION_URL = "https://docs.google.com/forms/d/e/1FAIpQLSf03n6xv1fLukql1FsogaT4VD0MW07Q7vhF3GG6Gc4GaFHHSg/formResponse" 
ENTRY_ID_QUESTION = "entry.1028184207"  
ENTRY_ID_RESPONSE = "entry.1966575961"
ENTRY_ID_RANK     = "entry.2026372673" 

def send_to_google_form(question, response_text):
    # ... (Google Form送信ロジックは変更なし) ...
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

# ... (AI応答取得関数は変更なし) ...
SYSTEM_INSTRUCTION = """
あなたは、新入生にお勧めの部活ランキングを出す親切で熱意ある部活案内AIアシスタントです。
以下のルールに従って、ユーザーの興味に応える**部活ランキング（3位まで）**を作成し、回答してください。
... (システム指示は省略) ...
"""

def get_ai_response(user_question):
    # ... (AI呼び出しロジックは変更なし) ...
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
            response.raise_for_status()
            
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


#--- ルーティングの設定 (PRGパターン適用) ---

@app.route("/", methods=["GET", "POST"])
def index():
    initial_message = "こんにちは、新入生！あなたの興味や得意なこと、挑戦したいことを教えてください。AIがあなたにぴったりの部活をランキング形式で推薦します！"
    
    # 🚨 GETリクエスト時の処理：セッションからAI応答を取得し、セッションから削除 (一回きりの表示)
    ai_response = session.pop('ai_response', initial_message)
    
    if request.method == "POST":
        
        print("--- [DEBUG: 1] POSTリクエストを受信しました。---")
        
        # サーバー側：二重送信阻止ロジック
        current_time = time.time()
        LAST_REQUEST_TIME_KEY = 'last_request_time'
        
        last_time = session.get(LAST_REQUEST_TIME_KEY, 0)
        
        if current_time - last_time < 5.0:
            print(f"--- [DEBUG: 2] 5秒ルールによりブロックされました。経過時間: {current_time - last_time:.2f}秒 ---")
            # ブロックされた場合も、セッションにメッセージを保存してリダイレクト
            session['ai_response'] = "二重送信を検出しました。システムの保護のため、前のリクエストから5秒以上経過してから再度質問してください。"
            return redirect(url_for('index'))
        
        session[LAST_REQUEST_TIME_KEY] = current_time
        
        print(f"--- [DEBUG: 3] フォームデータ全体: {request.form} ---")
        
        user_question = request.form.get("question")
        
        print(f"--- [DEBUG: 4] 取得した質問内容 (question): '{user_question}' ---")
        
        if user_question:
            print("--- [DEBUG: 5] 質問が空でないため、AI処理に進みます ---")
            try:
                ai_response, source = get_ai_response(user_question)
                print(f"Response Source: {source}")
                
                if source != "Fallback":
                    send_to_google_form(user_question, ai_response)
                
            except Exception as e:
                ai_response = f"AIからの応答処理中に予期せぬエラーが発生しました: {e}"
                print(f"General Error: {e}")
                
            # 🚨 成功/失敗に関わらず、AI応答をセッションに保存
            session['ai_response'] = ai_response 
            
            # 🚨 PRGパターンの核心：POST処理後、必ずGETリクエストにリダイレクト
            return redirect(url_for('index'))
            
        else:
             print("--- [DEBUG: 6] 質問内容が空 (Noneまたは'') のため、エラーメッセージを返します ---")
             session['ai_response'] = "質問を入力してください。"
             return redirect(url_for('index')) # 🚨 エラーでもリダイレクト

    # GETリクエストの場合、セッションから取得した応答でテンプレートをレンダリング
    return render_template("index.html", response=ai_response, history=[])
    
# アプリケーションの実行
if __name__ == "__main__":
    app.run(debug=True)
