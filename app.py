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

def create_d7d17_index_sheet():
    INDEX_SHEET_NAME = "目次_D7D17"
    sh = gc.open_by_key(SPREADSHEET_ID)
    # 既存シートがあれば削除
    try:
        sh.del_worksheet(sh.worksheet(INDEX_SHEET_NAME))
    except Exception:
        pass
    # データ収集
    rows = []
    for ws in sh.worksheets():
        if ws.title == INDEX_SHEET_NAME:
            continue
        sheet_name = ws.title
        d5 = safe_acell(ws, "D7")
        d7 = safe_acell(ws, "D17")
        rows.append([sheet_name, d7, d17])
    # 新しいシート作成＆書き込み
    ws_index = sh.add_worksheet(title=INDEX_SHEET_NAME, rows=len(rows)+10, cols=3)
    ws_index.update("A1", [["シート名", "D7", "D17"]])
    if rows:
        ws_index.update("A2", rows)
    return len(rows)

# --- 管理者用：AI分類→保存のボタン ---
with st.expander("⚡ 管理者メニュー：AI分類ラベルを保存", expanded=True):
    # ...既存のボタン...
    if st.button("目次_D7D17シートを作成/更新（全シートD7・D17一覧）"):
        n = create_d5d7_index_sheet()
        st.success(f"目次_D7D17シートを作成・更新しました！（{n}件）")

   

# --- サジェスト用データ読込 ---
@st.cache_data
def load_contents_for_search():
    sh = gc.open_by_key(SPREADSHEET_ID)
    sheets = sh.worksheets()
    data = []
    for ws in sheets:
        sheet_name = ws.title
        gid = ws.id
        d5 = safe_acell(ws, "D5")
        d7 = safe_acell(ws, "D7")
        data.append({
            "シート名": sheet_name,
            "gid": gid,
            "D5": d5,
            "D7": d7,
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
             or (user_input in str(row["D5"])) or (user_input in str(row["D15"])) or (user_input in str(row["D17"])) \
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
            st.write(f'D5: {rec["D5"]}')
            st.write(f'D15: {rec["D15"]}')
            st.write(f'D17: {rec["D17"]}')
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
