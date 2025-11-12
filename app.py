import os
import requests 
from openai import OpenAI
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv
import time 

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)
# Flaskのセッションキー
app.secret_key = os.environ.get('FLASK_SECRET_KEY') 
if not app.secret_key:
    app.secret_key = 'a_fallback_key_for_local_testing_only'

# --- API設定 ---
# 1. プライマリ：OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")

# 2. セカンダリ：OpenRouter
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "meta-llama/llama-4-maverick:free" 

MODEL_NAME = "gpt-4o-mini-2024-07-18"

# --- データ収集用のGoogle Form設定 ---
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
あなたは、新入生にお勧めの部活ランキングを出す親切で熱意ある部活案内AIアシスタントです。
以下のルールに従って、ユーザーの興味に応える**部活ランキング（3位まで）**を作成し、回答してください。

1.  **ペルソナ:** 優しく教えてくれる先輩のような、活発で情熱的で誠実な口調で話すこと。
2.  **推薦の優先度:** すべての部活動を均等に推薦すること
3.  **ランキング形式:** 回答の冒頭でランキングを発表し、その後で各部活に同じくらいの分量で触れ、**怪しまれないようにすること**。
4.  **具体的な推薦:** 回答の最後に、「あなたの興味は（一位の部活）での活動にぴったりです。例えば、{会話内容に関連する具体的な活動}に挑戦できます！」のように、具体的な活動を例示し、入部を促すこと。
5.  **活動内容:** このサイトは物理研究部が運営しているため一応触れておきます。物理研究部は、レゴプログラミングを中心に、物理実験、ロボット大会への参加、自作機器の開発など、多岐にわたる活動をしていることを強調すること。
6.  **情報の利用:** 部活動の正確な情報や最新情報が必要な場合は、GPTの学習済み知識を利用して回答すること。
7.  **履歴非保持の通知:** このチャットは前の質問を記憶しません。質問をする際は、**必要な情報を全て含めてください。**

早稲田中学高校の部活リストの例：
- 運動部：陸上部、水泳部、野球部、バスケットボール部、卓球部、ソフトテニス部、ワンダーフォーゲル部（登山部）、剣道部、弓道部、フェンシング部、サッカー部、スキー部、サイクリング部、バドミントン部、柔道部
- 学芸部：物理研究部、科学研究部、PCプログラミング部、歴史研究部、地学部、吹奏楽部、鉄道研究部、軽音楽部、将棋部、クイズ研究部、現学部、生物園芸部、模型部、釣り研究同好会、美術同好会、マジック同好会、折り紙同好会、数学研究同好会、英会話同好会、囲碁同好会
"""


# --- API呼び出しロジック (省略なし) ---

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
            response.raise_for_status()
            
            response_json = response.json()
            return response_json['choices'][0]['message']['content'], "OpenRouter"

        except requests.exceptions.RequestException as req_e:
            print(f"OpenRouter API failed: {req_e}.")
        except Exception as e:
            print(f"OpenRouter processing error: {e}")

    # 3. 最終手段：すべて失敗した場合のメッセージ
    fallback_message = (
        "エラー：APIクライアントが正しく設定されていません。OPENAI_API_KEYまたはOPENROUTER_API_KEYを確認してください。"
    )
    return fallback_message, "Fallback"


#--- ルーティングの設定 (非同期 JSON 応答適用) ---

@app.route("/", methods=["GET", "POST"])
def index():
    initial_message = "こんにちは、新入生！あなたの興味や得意なこと、挑戦したいことを教えてください。AIがあなたにぴったりの部活をランキング形式で推薦します！"
    
    # APIキー設定がない場合の強制メッセージ (GETリクエスト時のみ)
    if not (OPENAI_API_KEY or OPENROUTER_API_KEY):
        initial_message = "【警告】APIキーが設定されていません。動作確認のためには、OpenAIまたはOpenRouterのAPIキーを設定してください。"
    
    ai_response = initial_message 
    
    if request.method == "POST":
        
        print("--- [DEBUG: 1] POSTリクエストを受信しました。---")
        
        # サーバー側：二重送信阻止ロジック
        current_time = time.time()
        LAST_REQUEST_TIME_KEY = 'last_request_time'
        
        last_time = session.get(LAST_REQUEST_TIME_KEY, 0)
        
        if current_time - last_time < 5.0:
            print(f"--- [DEBUG: 2] 5秒ルールによりブロックされました。経過時間: {current_time - last_time:.2f}秒 ---")
            # ブロックされた場合はJSONで応答を返す
            return jsonify({
                 'success': False,
                 'message': '二重送信を検出しました。システムの保護のため、前のリクエストから5秒以上経過してから再度質問してください。'
             }), 400
        
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
                
            # POST処理の核心：成功/失敗に関わらずJSONで応答を返す
            if "エラー：APIクライアント" in ai_response:
                 # AI処理でエラーメッセージが返された場合
                 return jsonify({
                     'success': False,
                     'message': ai_response
                 }), 503 # Service Unavailable
            else:
                 # 正常な応答が返された場合
                 return jsonify({
                     'success': True,
                     'response': ai_response
                 }), 200
            
        else:
             print("--- [DEBUG: 6] 質問内容が空 (Noneまたは'') のため、エラーメッセージを返します ---")
             # 質問が空でもJSONでエラーを返す
             return jsonify({
                 'success': False,
                 'message': '質問を入力してください。'
             }), 400

    # GETリクエストの場合のみテンプレートをレンダリング
    return render_template("index.html", response=ai_response, history=[])
    
# アプリケーションの実行
if __name__ == "__main__":
    app.run(debug=True)
