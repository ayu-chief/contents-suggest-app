import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import openai

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

# --- シートからコンテンツ情報を取得 ---
@st.cache_data
def load_all_contents():
    sh = gc.open_by_key(SPREADSHEET_ID)
    sheets = sh.worksheets()
    data = []
    for ws in sheets:
        sheet_name = ws.title
        gid = ws.id
        def safe_acell(cell):
            try:
                return ws.acell(cell).value or ""
            except Exception:
                return ""
        b5 = safe_acell("B5")
        b15 = safe_acell("B15")
        b17 = safe_acell("B17")
        summary = f"{b5} {b15} {b17}"
        data.append({
            "シート名": sheet_name,
            "gid": gid,
            "B5": b5,
            "B15": b15,
            "B17": b17,
            "summary": summary
        })
    return pd.DataFrame(data)

contents_df = load_all_contents()

# --- AIで2層分類（OpenAI新API） ---
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

# --- UIここから ---
st.title("おすすめ活動サジェスト")
user_input = st.text_input("どんな活動を探していますか？（例：自然系、小学生向け、運動など）")
search_btn = st.button("おすすめを表示")

if search_btn and user_input:
    recs = []
    # 必要なら件数を制限: contents_df.head(5).iterrows() など
    for i, row in contents_df.iterrows():
        # AI分類（最初の5件などに制限推奨）
        cat1, cat2 = categorize_content(row["シート名"], row["summary"])
        # 部分一致フィルタ
        cond = (user_input in cat1) or (user_input in cat2) or \
               (user_input in str(row["summary"])) or (user_input in str(row["シート名"]))
        if cond:
            recs.append({
                "コンテンツ名": row["シート名"],
                "B5": row["B5"],
                "B15": row["B15"],
                "B17": row["B17"],
                "gid": row["gid"],
                "カテゴリー": f"{cat1} > {cat2}",
            })

    top3 = recs[:3]
    others = recs[3:10]

    if top3:
        st.subheader("おすすめコンテンツ")
        for rec in top3:
            st.write(f'### {rec["コンテンツ名"]}')
            st.write(f'カテゴリー: {rec["カテゴリー"]}')
            st.write(f'B5: {rec["B5"]}')
            st.write(f'B15: {rec["B15"]}')
            st.write(f'B17: {rec["B17"]}')
            sheet_url = SHEET_BASE_URL + str(rec["gid"])
            st.markdown(f'<a href="{sheet_url}" target="_blank" style="font-size:18px; color:blue; text-decoration:underline;">詳細を見る</a>', unsafe_allow_html=True)
            st.write("---")
        if others:
            st.subheader("その他の近いコンテンツ")
            st.write("、".join([rec["コンテンツ名"] for rec in others]))
    else:
        st.info("条件に合うおすすめが見つかりませんでした。検索ワードを変えてみてください。")

else:
    st.write("上の検索欄に希望を入力して「おすすめを表示」ボタンを押してください。")

