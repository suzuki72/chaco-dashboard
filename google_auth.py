"""
Google API 認証ヘルパー

ローカル: token.json からトークンを読み込む（初回はブラウザ認証）
クラウド: Streamlit Secrets からトークンを読み込む

使い方:
    from google_auth import get_credentials
    creds = get_credentials()
"""

import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# このディレクトリを基準にファイルを配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

# 必要なスコープ（各APIのread-only権限）
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",          # GA4
    "https://www.googleapis.com/auth/adsense.readonly",            # AdSense
    "https://www.googleapis.com/auth/admob.readonly",              # AdMob
    "https://www.googleapis.com/auth/yt-analytics.readonly",       # YouTube Analytics
    "https://www.googleapis.com/auth/youtube.readonly",            # YouTube channel info
]


def get_credentials():
    """
    OAuth2認証情報を取得する。

    優先順位:
    1. Streamlit Secrets（クラウドデプロイ時）
    2. token.json（ローカル実行時）
    3. ブラウザ認証フロー（初回のみ）
    """
    creds = None

    # 1. Streamlit Secrets から読み込む（クラウド環境）
    try:
        import streamlit as st
        if "google_token" in st.secrets:
            token_data = dict(st.secrets["google_token"])
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    except Exception:
        pass

    # 2. token.json から読み込む（ローカル環境）
    if not creds and os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # 3. トークンが無い or 期限切れ → 再認証 or リフレッシュ
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # トークンをリフレッシュ
            creds.refresh(Request())
        else:
            # 初回認証フロー（ローカルのみ、クラウドでは不可）
            from google_auth_oauthlib.flow import InstalledAppFlow
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "credentials.json が見つかりません。\n"
                    "ローカル: Google Cloud Console からダウンロードしてください。\n"
                    "クラウド: Streamlit Secrets に google_token を設定してください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # ローカルの場合はトークンを保存
        if os.path.exists(BASE_DIR):
            try:
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
            except Exception:
                pass

    return creds
