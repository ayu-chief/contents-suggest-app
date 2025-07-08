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

import time

def create_d7d17_index_sheet():
    INDEX_SHEET_NAME = "目次_D7D17"
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws_index = sh.worksheet(INDEX_SHEET_NAME)
        all_values = ws_index.get_all_values()
        df_index = pd.DataFrame(all_values[1:], columns=all_values[0])  # header行除く
    except Exception:
        ws_index = None
        df_index = pd.DataFrame(columns=["シート名", "D7", "D17"])

    sheets = sh.worksheets()
    updated_rows = []
    added_rows = []
    title_to_idx = {row["シート名"]: idx for idx, row in df_index.iterrows()}

    for ws in sheets:
        if ws.title == INDEX_SHEET_NAME:
            continue
        d7 = safe_acell(ws, "D7")
        d17 = safe_acell(ws, "D17")

        if ws.title in title_to_idx:
            idx = title_to_idx[ws.title]
            if (not df_index.loc[idx, "D7"]) or (not df_index.loc[idx, "D17"]):
                df_index.at[idx, "D7"] = d7
                df_index.at[idx, "D17"] = d17
                updated_rows.append(idx)
        else:
            df_index.loc[len(df_index)] = [ws.title, d7, d17]
            added_rows.append(len(df_index))
        time.sleep(1)  # ★ここで1秒ウェイトを追加！

    # まとめて更新（全体一括上書き）
    values = [df_index.columns.tolist()] + df_index.values.tolist()
    if ws_index:
        ws_index.update(f"A1:C{len(values)}", values)
    else:
        ws_index = sh.add_worksheet(title=INDEX_SHEET_NAME, rows=len(df_index)+10, cols=3)
        ws_index.update(f"A1:C{len(values)}", values)
    
    return len(updated_rows), len(added_rows)

# --- 管理者用：AI分類→保存のボタン ---
with st.expander("⚡ 管理者メニュー：AI分類ラベルを保存", expanded=True):
    if st.button("目次_D7D17シートを作成/更新（空欄補完＆新規追加）"):
        upd, add = create_d7d17_index_sheet()
        st.success(f"目次_D7D17シートを作成・更新しました！空欄補完: {upd}件、新規追加: {add}件")

# --- AI分類: 通常版 ---
def categorize_content_for_index(sheet_name, d7, d17):
    prompt = f"""
あなたは学校教育アクティビティの分類の専門家です。
以下の「活動名」「D7内容」「D17内容」から、一般的な2階層のカテゴリーを日本語で推定してください。
出力例：「第一階層 > 第二階層」
---
活動名: {sheet_name}
D7: {d7}
D17: {d17}
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

# --- AI分類: リトライ付き ---
def categorize_content_for_index_with_retry(sheet_name, d7, d17, retries=5, wait_sec=10):
    for attempt in range(retries):
        try:
            return categorize_content_for_index(sheet_name, d7, d17)
        except openai.RateLimitError:
            if attempt < retries - 1:
                st.warning(f"OpenAIの利用制限。{wait_sec}秒待機してリトライ({attempt+1}/{retries})...")
                time.sleep(wait_sec)
            else:
                st.error("リトライ上限でスキップします。")
                return "", ""
        except Exception as e:
            st.error(f"予期せぬエラー: {e}")
            return "", ""

# --- 目次_D7D17シートの空欄にAI分類（二層）を追記 ---
def categorize_d7d17_index_sheet_only_empty():
    INDEX_SHEET_NAME = "目次_D7D17"
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws_index = sh.worksheet(INDEX_SHEET_NAME)
    records = ws_index.get_all_values()
    if len(records) < 2:
        return 0
    updated = 0
    # 既存値のまま配列化
    all_values = records
    # 必要に応じてD列・E列を拡張
    for row in all_values:
        while len(row) < 5:
            row.append("")
    # 書き換えリスト用意
    for i, row in enumerate(all_values[1:], start=2):  # 2行目から
        sheet_name = row[0]
        d7 = row[1]
        d17 = row[2]
        cat1 = row[3]
        cat2 = row[4]
        if not cat1 and not cat2:
            cat1, cat2 = categorize_content_for_index_with_retry(sheet_name, d7, d17)
            all_values[i-1][3] = cat1
            all_values[i-1][4] = cat2
            time.sleep(1.5)
            updated += 1
    # 一括アップロード
    ws_index.update(f"A1:E{len(all_values)}", all_values)
    return updated

# --- 管理者メニュー Streamlit ボタン ---
with st.expander("⚡ 管理者メニュー：目次シートAI分類", expanded=True):
    if st.button("目次_D7D17シートの空欄のみAI分類（二層）で追記"):
        n = categorize_d7d17_index_sheet_only_empty()
        st.success(f"{n}件の分類ラベルを書き込みました！")

    if st.button("デバッグ：2行目だけAI分類テスト"):
       try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws_index = sh.worksheet("目次_D7D17")
        sheet_name = ws_index.acell("A2").value
        d7 = ws_index.acell("B2").value
        d17 = ws_index.acell("C2").value

        # 必ずリトライ付きの関数で
        cat1, cat2 = categorize_content_for_index_with_retry(sheet_name, d7, d17)
        st.write(f"{sheet_name}: {cat1} > {cat2}")

        ws_index.update("D2", [[cat1]])
        ws_index.update("E2", [[cat2]])
        st.success(f"2行目: {sheet_name} の分類を書き込みました")
       except Exception as e:
        st.error(f"エラー: {e}")
          
# --- サジェスト用データ読込 ---
@st.cache_data
def load_contents_for_search():
    sh = gc.open_by_key(SPREADSHEET_ID)
    sheets = sh.worksheets()
    data = []
    for ws in sheets:
        sheet_name = ws.title
        gid = ws.id
        d7 = safe_acell(ws, "D7")
        d17 = safe_acell(ws, "D17")
        data.append({
            "シート名": sheet_name,
            "gid": gid,
            "D7": d7,
            "D17": d17,
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
        # ↓ここを「分類①」「分類②」に変更
        cond = (user_input in str(row["分類①"])) or (user_input in str(row["分類②"])) \
             or (user_input in str(row["D7"])) or (user_input in str(row["D17"])) \
             or (user_input in str(row["シート名"]))
        if cond:
            recs.append(row)
    top3 = recs[:3]
    others = recs[3:10]
    if top3:
        st.subheader("おすすめコンテンツ")
        for rec in top3:
            st.write(f'### {rec["シート名"]}')
            st.write(f'第一階層: {rec["分類①"]}')
            st.write(f'第二階層: {rec["分類②"]}')
            st.write(f'D7: {rec["D7"]}')
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
