# RELAY Desk

[![relay-quality](https://github.com/remanpso2-wq/relay-desk/actions/workflows/ci.yml/badge.svg)](https://github.com/remanpso2-wq/relay-desk/actions/workflows/ci.yml)

**問い合わせと根拠をつなぐ、AI返信レビューのワークスペース。**

React / TypeScript + FastAPI / SQLAlchemy のポートフォリオ用Webアプリです。
問い合わせを登録し、社内資料を検索して返信案を作り、担当者が根拠を確認して承認する一連の流れをDBへ保存します。

v0.2.0 / 2026-10-16。架空の「青葉ストア」を題材にしています。
商用導入済み・本番品質保証・AI回答の正確性保証を意味しません。

## 実装したこと

- Cookieセッション認証、Argon2パスワードハッシュ、Origin検証、CSRF、ログイン試行制限
- 管理者・担当者・レビュアーの3ロール。企業IDでAPIを分離し、関連レコードの企業一致を複合外部キーでも制約
- 問い合わせの登録・検索・担当割当・優先度・対応状況・履歴
- FAQ/資料の登録・更新・非公開化と、過去版の本文保存・履歴表示
- チーム内メモの追記（AI送信対象外）
- 2分以上停止した生成の手動復旧。遅れて返ったAI応答で復旧状態を上書きしない
- 日本語を含む段落・チャンク単位の文字2-gram検索で最大3資料を取得し、根拠付きの返信案を生成
- 送信前の本文・参照資料プレビュー。プレビュー後に資料が変更されたら再確認を要求
- 生成原文とレビュー後の文を分離。承認・差戻しと確認メモを保存
- 問い合わせ・参照資料の更新後は古い下書きの承認を拒否
- 現在の記録に基づく承認がある場合だけ問い合わせを完了可能
- リクエストIDによる重複生成抑止、企業ごと過去24時間30回の上限、外部AI障害の分離
- レスポンシブ画面、問い合わせ一覧・対応詳細・返信支援、ナレッジ、操作履歴
- Alembic初期マイグレーション、OpenAPI、APIテスト、E2E仕様、CI、Compose構成

メール送信は実装していません。「承認」は保存する操作で、顧客への送信ではありません。
PDFアップロード、ベクトル検索、SSO、招待、ユーザー管理UI、通知、SLA、バックアップ自動化も今後の対象です。

## AIの2つのモード

| 設定 | 動作 |
|---|---|
| `AI_PROVIDER=demo`（初期値） | 検索した資料を引用する定型文。LLM不使用・外部送信なし。UIでもサンプルと表示 |
| `AI_PROVIDER=openai` | サーバーからOpenAI Responses APIを呼ぶ。`OPENAI_API_KEY` が必要 |
| `AI_PROVIDER=off` | 下書き生成を無効化 |

実AIはJSON Schemaで出力形式を制約し、参照IDが送信資料の範囲内か検証します。
**引用IDが正しいことと、文章の内容が根拠に支持されることは別です。** 人による確認が必須です。
資料が見つからない場合は、実AIを呼ばず「根拠不足」として保存します。

問い合わせの氏名欄は外部AIへ送りませんが、本文・資料本文に含まれる情報は送信対象です。
プレビューで確認し、架空データだけを使用してください。実キーでの接続検証はまだ行っていません。
キーをブラウザコードやGitHubへ入れないでください。

## 起動（Python 3.12 / Node.js 24）

プロジェクトのルートから実行します。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.lock
cd frontend
npm ci
npm run build
cd ../backend
python -m alembic upgrade head
# 自分で選んだ15～128文字のデモ用パスワードを環境変数へ設定
read -s -p 'Demo password: ' DEMO_PASSWORD
export DEMO_PASSWORD
python -m app.seed
unset DEMO_PASSWORD
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`http://localhost:8000` を開きます。Originを厳密に検査するため、ブラウザでは `127.0.0.1` ではなく `localhost` を使用してください。
DBは `backend/relay.db` に作られます。再起動してもデータは保持されます。
`.env.example` は設定の例です。ローカルPython起動では **.envを自動読み込みしません**。必要な環境変数をシェルに設定してください。

Windows PowerShellでは仮想環境を `.\.venv\Scripts\Activate.ps1` で有効化し、`source` の行を置き換えます。
パスワード設定部分は次の操作へ置き換えます（Windowsでの実行は未検証）。

```powershell
$secureDemo = Read-Host "Demo password (15 characters minimum)" -AsSecureString
$env:DEMO_PASSWORD = [System.Net.NetworkCredential]::new('', $secureDemo).Password
python -m app.seed
Remove-Item Env:DEMO_PASSWORD
```

初期データの投入は空のDBに対してだけ許可されます。既存DBを上書きする動作はありません。

| ログイン | ロール | 操作 |
|---|---|---|
| `admin@example.test` | 管理者 | 全画面・資料編集・承認 |
| `agent@example.test` | 担当者 | 問い合わせ・下書き生成。資料編集・承認・全体監査は不可 |
| `reviewer@example.test` | レビュアー | 問い合わせ・資料編集・承認・監査 |

全アカウントが初期化時に設定したデモ用パスワードを使用します。実運用用アカウントとして使わないでください。

## 5分で試す

1. 管理者でログインし「注文後に配送先住所を変更したい」を選択。
2. 「送信内容・参照資料を確認」で、問い合わせ本文と資料の抜粋を見る。
3. 確認欄をチェックして「下書きを生成」。サンプル生成と表示される。
4. 返信文を編集し、根拠資料を開き、確認メモ・確認チェックを入れて承認。
5. 再読み込みして保存を確認。状況を「完了」に変更。
6. 別の下書きを作り、ナレッジを編集。古い下書きで承認が拒否されることを確認。
7. 担当者アカウントでログインし、編集・承認できる範囲の違いを確認。

## PostgreSQL / Docker Compose

Composeはローカル開発用です。ホスト公開は `127.0.0.1:8000` に限定し、DBポートは公開しません。
DBユーザーは簡易開発構成の所有者です。本番用の非特権ランタイムロールやRLSはこの版にありません。

1. `.env.example` を `.env` にコピー。
2. `DB_PASSWORD` に長いランダムな英数字、`DEMO_PASSWORD` に15文字以上の値を設定。
3. `docker compose up --build -d`
4. `docker compose exec app python -m app.seed`
5. `http://localhost:8000` を開く。

PostgreSQL 17実DBでの初期マイグレーションとAPIテストはGitHub Actionsで成功しています。Compose自体は未検証です。

## テスト

```bash
cd backend
python -m pytest -q
cd ../frontend
npm run build
# 以下は対応するブラウザ環境で実行（GitHub ActionsのChromiumで2シナリオ成功）
npx playwright install chromium
npm run test:e2e
```

GitHub ActionsでSQLite、PostgreSQL 17実DB、フロントエンドビルド、Chromium E2E 2シナリオが成功しました（[実行結果](https://github.com/remanpso2-wq/relay-desk/actions/runs/38886416030)）。実AI接続・視覚QA・Docker/Windows・公開デモの検証は未実施です。
CIの実行状況は [GitHub Actions](https://github.com/remanpso2-wq/relay-desk/actions) で確認できます。PostgreSQLテストは使い捨ての `TEST_DATABASE_URL` のテーブルをTRUNCATEするため、実データのDBを指定しないでください。
検証結果は [docs/validation.md](docs/validation.md)、設計は [docs/architecture.md](docs/architecture.md) を参照。

## フォルダ

- `backend/app`: 認証・DB・API・検索・AIアダプター・架空データ
- `backend/migrations`: 固定した初期スキーマとAlembic
- `backend/tests`: API、認可、外部AI境界、マイグレーション
- `frontend/src`: React / TypeScript画面
- `frontend/e2e`: Playwright操作シナリオ（Chromiumで2件成功）
- `docs`: 設計、検証結果、次の開発項目、OpenAPI

ソース公開用ライセンスは未選定です。第三者依存のライセンスは各パッケージに従います。

## v0.2で追加した検証と復旧

- 長文資料の後半に根拠がある場合、段落と最大800文字・200文字重複のチャンクから該当抜粋を取得。
- 固定7問の検索回帰テスト（正答資料6問・無関係文字列1問）。本格的なAI品質評価の代わりにはしません。
- 二人が同時に承認した場合は一人だけ成功。企業をまたぐ担当者リンクをDB制約でも拒否。
- 画面の通信再試行では同じ生成キーを保持して二重生成を抑止。画面を閉じた後は履歴を先に確認してください。
- ログアウト時に画面・入力・履歴キャッシュを消去。
- SQLiteの一貫したスナップショットを作り、一時DBへ復元して全テーブルの件数・内容ハッシュ・整合性を照合。

SQLite復元検証はプロジェクトのルートで実行できます。入力DBは読み取り専用で開き、復元先は一時ディレクトリです。恒久バックアップは残しません。

```bash
python ops/check_sqlite_restore.py backend/relay.db
```

PostgreSQL実DB・Dockerはこの実行環境で導入/実行できず、ブラウザE2E/視覚QAも利用可能なブラウザ検証手段がないため未実施です。実OpenAI接続はキーが必要です。これらが完了するまでは「検証済み完成版」とは表記しません。
