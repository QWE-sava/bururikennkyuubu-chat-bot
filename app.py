# app.py (チャットセッション対応・修正版 - 全文)

import os
from flask import Flask, render_template, request, session, redirect, url_for
from google import genai
from google.genai.errors import APIError
from google.genai.types import Content, Part # 履歴処理に必要な型をインポート
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)
# ！！！重要！！！ 本番環境では必ずこのキーをランダムで複雑な値に変更してください
app.secret_key = 'your_very_secret_key_for_session' 


# Gemini APIクライアントの初期化
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # 環境変数がない場合は例外を発生させる
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
6.  **情報の利用:** 早稲田中学校の部活動リスト（運動部・学芸部）に関する一般情報をあなたは知っているものとし、Web検索は行わないこと。
7.  **履歴非保持の通知:** このチャットは前の質問を記憶しません。質問をする際は、**必要な情報を全て含めてください。**

早稲田中高の部活リストの例：
- 運動部：陸上部、水泳部、野球部、バスケットボール部、卓球部、ソフトテニス部、ワンダーフォーゲル部（登山部）、剣道部、弓道部、フェンシング部、サッカー部、スキー部、サイクリング部、バドミントン部、柔道部
- 学芸部：物理研究部、科学研究部、PCP部、歴史研究部、地学部、吹奏楽部、鉄道研究部、軽音楽部、将棋部、クイズ研究部、現学部、生物園芸部、模型部、釣り研究同好会、美術同好会、マジック同好会、折り紙同好会、数学研究同好会、英会話同好会、囲碁同好会
"""

#--- 履歴をJSONセーフにするためのヘルパー関数 ---

def history_to_json_safe(history):
    """ContentオブジェクトのリストをJSONセーフなリストに変換"""
    json_safe_history = []
    for message in history:
        # roleとtextだけを取り出す
        text_content = message.parts[0].text if message.parts and message.parts[0].text else ""
        json_safe_history.append({
            "role": message.role,
            "text": text_content
        })
    return json_safe_history

def json_safe_to_history(json_safe_history):
    """JSONセーフなリストをGemini APIが使えるContentオブジェクトのリストに変換"""
    history = []
    for item in json_safe_history:
        # 辞書からContentオブジェクトを再構築
        # Part.from_text() ではなく、Partオブジェクトを直接 content=text で作成します。
        # Content(parts=[...]) の形式でテキストデータを渡すのが安全です。
        history.append(
            Content(
                role=item['role'], 
                parts=[Part.from_text(text=item['text'])] # ★この行を修正★
            )
        )
    return history


#--- ルーティングの設定 ---

@app.route("/", methods=["GET", "POST"])
def index():
    ai_response = ""
    
    # ユーザーが「リセット」ボタンを押した場合の処理
    if request.args.get('reset'):
        session.pop('chat_history', None) # 履歴を削除
        return redirect(url_for('index'))
        
    # クライアントが初期化されているかチェック
    if not client:
        ai_response = "エラー：Gemini APIクライアントが正しく初期化されていません。APIキーを確認してください。"
        return render_template("index.html", response=ai_response, history=[])
        
    # ----------------------------------------------------
    # 1. チャットセッションの準備
    # ----------------------------------------------------
    # セッションからJSONセーフな履歴を読み込む (なければ空のリスト)
    json_safe_history = session.get('chat_history', [])
    
    # JSONセーフな履歴をGemini APIが使えるContentオブジェクトのリストに変換
    history_for_gemini = json_safe_to_history(json_safe_history)

    try:
        # 新しいチャットセッションを作成、過去の履歴があればそれを引き継ぐ
        chat_session = client.chats.create(
            model="gemini-2.5-flash",
            history=history_for_gemini, # 変換後の履歴を渡す
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            )
        )
    except Exception as e:
        # AIセッションの開始中にエラーが発生した場合
        ai_response = f"AIセッションの開始中にエラーが発生しました: {e}"
        # この時点ではJSONセーフな履歴をそのまま表示に使う
        return render_template("index.html", response=ai_response, history=json_safe_history)


    # ----------------------------------------------------
    # 2. 初期メッセージの設定 (履歴が全くない場合)
    # ----------------------------------------------------
    # 履歴が空の場合、AIの挨拶メッセージを設定
    if not history_for_gemini:
        ai_response = "こんにちは、新入生！物理研究部のAIアシスタントです。あなたの興味について教えてください。どんなことに挑戦したいですか？"


    # ----------------------------------------------------
    # 3. POSTリクエスト（質問が送信された場合）の処理
    # ----------------------------------------------------
    if request.method == "POST":
        user_question = request.form.get("question")
        
        if user_question:
            try:
                print(f"Received question: {user_question}")
                
                # chat_session.send_message() で質問を送信し、応答を取得
                response = chat_session.send_message(user_question)
                ai_response = response.text
                
                print(f"AI Response: {ai_response[:50]}...")
                
                # 応答後、チャットセッションの全履歴を取得
                full_history = chat_session.get_history()
                
                # Contentオブジェクトの履歴をJSONセーフな形式に変換してセッションに保存
                session['chat_history'] = history_to_json_safe(full_history)
                
            except APIError as api_e:
                ai_response = f"Gemini APIからの応答中にエラーが発生しました: {api_e.message}"
                print(f"Gemini API Error: {api_e}")
            except Exception as e:
                ai_response = f"AIからの応答中に予期せぬエラーが発生しました: {e}"
                print(f"General Error: {e}")
        else:
             ai_response = "質問を入力してください。"

    # ----------------------------------------------------
    # 4. 履歴の表示
    # ----------------------------------------------------
    # 表示用の履歴リストは、セッションに保存されているJSONセーフなものを使う
    final_history_display = session.get('chat_history', [])
            
    # GETリクエストまたはPOST後のページ表示
    return render_template("index.html", response=ai_response, history=final_history_display)


# アプリケーションの実行
if __name__ == "__main__":

    app.run(debug=True)

