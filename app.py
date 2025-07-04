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
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        api_key=OPENAI_API_KEY,
    )
    res = response.choices[0].message.content.strip()
    if ">" in res:
        cat1, cat2 = [x.strip() for x in res.split(">", 1)]
    elif "＞" in res:
        cat1, cat2 = [x.strip() for x in res.split("＞", 1)]
    else:
        cat1, cat2 = res, ""
    return cat1, cat2

categories = []
worksheets = gc.open_by_key(SPREADSHEET_ID).worksheets()
for ws in worksheets:
    content_name = ws.title
    # B5, B15, B17の内容取得
    def safe_acell(ws, cell):
        try:
            return ws.acell(cell).value or ""
        except Exception:
            return ""
    b5 = safe_acell(ws, "B5")
    b15 = safe_acell(ws, "B15")
    b17 = safe_acell(ws, "B17")
    # まとめてサマリーテキスト
    summary = f"{b5} {b15} {b17}"
    cat1, cat2 = categorize_content(content_name, summary)
    categories.append({
        "コンテンツ名": content_name,
        "B5": b5,
        "B15": b15,
        "B17": b17,
        "第一階層": cat1,
        "第二階層": cat2
    })
categories_df = pd.DataFrame(categories)
st.subheader("二層分類ラベル一覧")
st.dataframe(categories_df)

# UIここから
st.title("おすすめ活動サジェスト")

user_input = st.text_input("どんな活動を探していますか？（例：自然系、小学生向け、運動など）")
search_btn = st.button("おすすめを表示")

if search_btn and user_input:
    # 各コンテンツごとにカテゴリー推定＋テーマ抽出
    recs = []
    for i, row in contents_df.iterrows():
        # 各ワークシートのB7セル（テーマ）取得
        ws = gc.open_by_key(SPREADSHEET_ID).worksheet(row["シート名"])
        theme = get_b7_value(ws)
        cat1, cat2 = categorize_content(row["シート名"], theme)
        # 検索キーワードの部分一致でフィルタ
        cond = (user_input in cat1) or (user_input in cat2) or (user_input in theme) or (user_input in str(row["シート名"])) or (user_input in str(row.get("説明", "")))
        if cond:
            recs.append({
                "コンテンツ名": row["シート名"],
                "説明": row.get("説明", ""),
                "gid": row["gid"],
                "カテゴリー": f"{cat1} > {cat2}",
                "テーマ": theme
            })

    # おすすめ上位3件
    top3 = recs[:3]
    others = recs[3:10]

    if top3:
        st.subheader("おすすめコンテンツ")
        for rec in top3:
            st.write(f'### {rec["コンテンツ名"]}')
            st.write(f'カテゴリー: {rec["カテゴリー"]}')
            st.write(f'テーマ: {rec["テーマ"]}')
            st.write(f'説明: {rec["説明"] if rec["説明"] else "（説明なし）"}')
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

