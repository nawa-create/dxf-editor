# DXF Natural Language Editor

自然言語でDXFファイルを編集できるWebアプリケーション。

## 🚀 Renderへのデプロイ手順

### 前提条件
- GitHubアカウント
- Renderアカウント（無料）
- Anthropic API Key（Claude API用）

### Step 1: GitHubリポジトリを作成

```bash
cd C:\Users\fujin\.gemini\antigravity\scratch\dxf-editor
git init
git add .
git commit -m "Initial commit: DXF Editor for Render deployment"
```

GitHubで新規リポジトリを作成し、プッシュ:
```bash
git remote add origin https://github.com/YOUR_USERNAME/dxf-editor.git
git branch -M main
git push -u origin main
```

### Step 2: Renderでデプロイ

#### 方法A: Blueprintを使用（推奨）
1. [Render Dashboard](https://dashboard.render.com/) にログイン
2. **New** → **Blueprint** をクリック
3. GitHubリポジトリを接続
4. `render.yaml` が自動検出される
5. 環境変数を設定:
   - `ANTHROPIC_API_KEY`: Claude APIキー

#### 方法B: 手動で2つのサービスを作成

**バックエンド (Web Service):**
1. **New** → **Web Service**
2. GitHubリポジトリを接続
3. 設定:
   - Name: `dxf-editor-api`
   - Root Directory: `backend`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. 環境変数:
   - `ANTHROPIC_API_KEY`: Claude APIキー
   - `FRONTEND_URL`: フロントエンドのURL（後で設定）

**フロントエンド (Static Site):**
1. **New** → **Static Site**
2. GitHubリポジトリを接続
3. 設定:
   - Name: `dxf-editor-frontend`
   - Root Directory: `frontend`
   - Build Command: `npm install && npm run build`
   - Publish Directory: `dist`
4. 環境変数:
   - `VITE_API_URL`: バックエンドのURL（例: `https://dxf-editor-api.onrender.com`）

### Step 3: CORSの設定

フロントエンドのURLをバックエンドの環境変数に追加:
```
FRONTEND_URL=https://dxf-editor-frontend.onrender.com
```

### Step 4: 動作確認

フロントエンドのURLにアクセスして動作を確認:
```
https://dxf-editor-frontend.onrender.com
```

---

## 🔧 ローカル開発

### バックエンド
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### フロントエンド
```bash
cd frontend
npm install
npm run dev
```

---

## 📁 プロジェクト構成

```
dxf-editor/
├── backend/              # FastAPI バックエンド
│   ├── main.py           # エントリポイント
│   ├── routers/          # APIルーター
│   ├── services/         # ビジネスロジック
│   └── requirements.txt
├── frontend/             # React フロントエンド
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── render.yaml           # Render Blueprint
└── README.md
```

---

## 🔑 必要な環境変数

| 変数名 | 説明 | 設定場所 |
|--------|------|----------|
| `ANTHROPIC_API_KEY` | Claude API キー | バックエンド |
| `FRONTEND_URL` | フロントエンドURL | バックエンド |
| `VITE_API_URL` | バックエンドURL | フロントエンド（ビルド時） |
