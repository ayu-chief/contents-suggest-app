import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import openai
import time

# OpenAI APIキーはSecretsから
OPENAI_API_KEY = st.secrets["openai_api_key"]
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Google Sheets認証情報もSecretsから
SERVICE_ACCOUNT_INFO = st.secrets["google_service_account"]  # Secrets名は後述
SPREADSHEET_ID = "15cpB2PddSHA6s_dNOuPzaTshMq9yE0WPVD8dqj_TXag"
SHEET_BASE_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid="

# 認証
scopes = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
gc = gspread.authorize(creds)

# --- OpenAI新APIクライアントを1回だけ作成 ---
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- ヘルパー関数 ---
def safe_acell(ws, cell):
    try:
        return ws.acell(cell).value or ""
    except Exception:
        return ""

def set_acell(ws, cell, value):
    try:
        ws.update_acell(cell, value)
    except Exception as e:
        print(f"{ws.title} {cell}書き込み失敗: {e}")

def categorize_content(content_name, summary):
    prompt = f"""
あなたは学校教育アクティビティの分類の専門家です。
次の「コンテンツ名」と「説明（本文）」から、できるだけ一般的な2階層のカテゴリーを日本語で推定してください。
出力例：「第一階層 > 第二階層」
---
コンテンツ名: {content_name}
説明: {summary}
カテゴリー:
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    res = response.choices[0].message.content.strip()
    if ">" in res:
        cat1, cat2 = [x.strip() for x in res.split(">", 1)]
    elif "＞" in res:
        cat1, cat2 = [x.strip() for x in res.split("＞", 1)]
    else:
        cat1, cat2 = res, ""
    return cat1, cat2

def categorize_content_with_retry(content_name, summary, retries=5, wait_sec=10):
    for attempt in range(retries):
        try:
            return categorize_content(content_name, summary)
        except openai.RateLimitError:
            if attempt < retries - 1:
                st.warning(f"OpenAIの利用制限。{wait_sec}秒待機してリトライ({attempt+1}/{retries})...")
                time.sleep(wait_sec)
            else:
                st.error("リトライ上限でスキップします。")
                return "", ""

# --- 新しいシートのみAI分類＆結果をB23/B24に保存 ---
def ai_categorize_new_sheets():
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheets = sh.worksheets()
    categorized = 0
    for ws in worksheets:
        b23 = safe_acell(ws, "B23")
        b24 = safe_acell(ws, "B24")
        if not b23 or not b24:
            b5 = safe_acell(ws, "B5")
            b15 = safe_acell(ws, "B15")
            b17 = safe_acell(ws, "B17")
            summary = f"{b5} {b15} {b17}"
            cat1, cat2 = categorize_content_with_retry(ws.title, summary)
            set_acell(ws, "B23", cat1)
            set_acell(ws, "B24", cat2)
            categorized += 1
            time.sleep(2)  # さらに余裕をもって待機
    return categorized

# --- 管理者用：AI分類→B23/B24保存のボタン ---
with st.expander("⚡ 管理者メニュー：AI分類ラベルを保存", expanded=True):
    if st.button("全シートでAI分類→B23/B24に保存（本番実行）"):
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheets = sh.worksheets()
        count = 0
        for ws in worksheets:
            b23 = safe_acell(ws, "B23")
            b24 = safe_acell(ws, "B24")
            # デバッグ：現在のB23/B24を表示
            st.write(f"{ws.title} B23:『{b23}』 B24:『{b24}』")
            if (not b23 or b23.strip() == "") or (not b24 or b24.strip() == ""):
                b5 = safe_acell(ws, "B5")
                b15 = safe_acell(ws, "B15")
                b17 = safe_acell(ws, "B17")
                summary = f"{b5} {b15} {b17}"
                cat1, cat2 = categorize_content_with_retry(ws.title, summary)
                st.write(f"→AI分類結果: {cat1} | {cat2}")
                set_acell(ws, "B23", cat1)
                set_acell(ws, "B24", cat2)
                st.success(f"{ws.title} にAI分類を書き込みました")
                count += 1
                time.sleep(2)
            else:
                st.info(f"{ws.title} はすでに分類済みなのでスキップ")
        st.success(f"{count}件のシートにAI分類ラベルを保存しました！")

# --- サジェスト用データ読込 ---
@st.cache_data
def load_contents_for_search():
    sh = gc.open_by_key(SPREADSHEET_ID)
    sheets = sh.worksheets()
    data = []
    for ws in sheets:
        sheet_name = ws.title
        gid = ws.id
        cat1 = safe_acell(ws, "B23")
        cat2 = safe_acell(ws, "B24")
        b5 = safe_acell(ws, "B5")
        b15 = safe_acell(ws, "B15")
        b17 = safe_acell(ws, "B17")
        data.append({
            "シート名": sheet_name,
            "gid": gid,
            "B5": b5,
            "B15": b15,
            "B17": b17,
            "cat1": cat1,
            "cat2": cat2,
        })
    return pd.DataFrame(data)

contents_df = load_contents_for_search()

# --- サジェスト検索UI ---
st.title("おすすめ活動サジェスト")
user_input = st.text_input("どんな活動を探していますか？（例：自然系、小学生向け、運動など）")
search_btn = st.button("おすすめを表示")

if search_btn and user_input:
    recs = []
    for _, row in contents_df.iterrows():
        cond = (user_input in str(row["cat1"])) or (user_input in str(row["cat2"])) \
             or (user_input in str(row["B5"])) or (user_input in str(row["B15"])) or (user_input in str(row["B17"])) \
             or (user_input in str(row["シート名"]))
        if cond:
            recs.append(row)
    top3 = recs[:3]
    others = recs[3:10]
    if top3:
        st.subheader("おすすめコンテンツ")
        for rec in top3:
            st.write(f'### {rec["シート名"]}')
            st.write(f'第一階層: {rec["cat1"]}')
            st.write(f'第二階層: {rec["cat2"]}')
            st.write(f'B5: {rec["B5"]}')
            st.write(f'B15: {rec["B15"]}')
            st.write(f'B17: {rec["B17"]}')
            sheet_url = SHEET_BASE_URL + str(rec["gid"])
            st.markdown(f'<a href="{sheet_url}" target="_blank" style="font-size:18px; color:blue; text-decoration:underline;">詳細を見る</a>', unsafe_allow_html=True)
            st.write("---")
        if others:
            st.subheader("その他の近いコンテンツ")
            st.write("、".join([rec["シート名"] for rec in others]))
    else:
        st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")
else:
    st.write("上の検索欄に希望を入力して「おすすめを表示」ボタンを押してください。")
