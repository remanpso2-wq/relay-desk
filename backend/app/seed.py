"""Explicit fictional data seed; refuses to overwrite an existing database."""

import os
from .db import *
from .main import ph


def seed():
    pw = os.getenv("DEMO_PASSWORD", "")
    if not 15 <= len(pw) <= 128:
        raise SystemExit("DEMO_PASSWORD must contain 15–128 characters.")
    with Session() as db:
        if db.query(Tenant).first():
            raise SystemExit("Database is not empty; seed cancelled.")
        t = Tenant(name="青葉ストア / 架空サポート窓口")
        db.add(t)
        db.flush()
        users = []
        for name, email, role in [
            ("青葉 美咲", "admin@example.test", "admin"),
            ("佐藤 遥", "agent@example.test", "agent"),
            ("高橋 蓮", "reviewer@example.test", "reviewer"),
        ]:
            u = User(
                tenant_id=t.id, name=name, email=email, role=role, password=ph.hash(pw)
            )
            db.add(u)
            users.append(u)
        db.flush()
        articles = [
            (
                "配送先住所の変更",
                "配送",
                "配送先住所の変更は、出荷準備前の注文に限り受け付けます。注文番号と新しい郵便番号・住所を確認してください。出荷後は変更を確約せず、配送会社への確認が必要である旨をご案内ください。",
            ),
            (
                "請求書・領収書の発行",
                "請求",
                "請求書はマイページの「注文履歴」からPDFでダウンロードできます。宛名の修正は未発行の場合に限り可能です。発行済みの請求書については担当部署へ確認してください。",
            ),
            (
                "パスワードを忘れた場合",
                "アカウント",
                "ログイン画面の「パスワードを忘れた方」から、登録済みメールアドレスを入力してください。有効期限30分の再設定リンクを送信します。メールが届かない場合は迷惑メールフォルダと入力したメールアドレスをご確認ください。担当者がパスワードを尋ねることはありません。",
            ),
            (
                "返品・交換の受付条件",
                "その他",
                "未使用の商品に限り、商品到着後7日以内に返品の相談を受け付けます。開封済み・使用済み商品は個別確認が必要です。不良品の場合は注文番号と状態が分かる情報を確認し、担当部署へ引き継いでください。返金や交換を確認前に確約しないでください。",
            ),
        ]
        for title, category, body in articles:
            a = Article(
                tenant_id=t.id, title=title, category=category, body=body, version=1
            )
            db.add(a)
            db.flush()
            db.add(
                ArticleRevision(
                    tenant_id=t.id, article_id=a.id, version=1, title=title, body=body
                )
            )
        entries = [
            (
                "注文後に配送先住所を変更したい",
                "架空のお客様 A",
                "昨日注文した商品の配送先住所を変更したいです。まだ出荷されていません。手続きの方法を教えてください。",
                "配送",
                "high",
            ),
            (
                "請求書の宛名を変更できますか",
                "架空のお客様 B",
                "注文履歴から請求書を発行したいのですが、宛名を会社名に変更できますか。まだ発行していません。",
                "請求",
                "normal",
            ),
            (
                "パスワード再設定メールが届かない",
                "架空のお客様 C",
                "パスワードを忘れて再設定を試しましたがメールが届きません。確認する場所を教えてください。",
                "アカウント",
                "high",
            ),
            (
                "開封した商品の返品について",
                "架空のお客様 D",
                "商品を開封しましたがサイズが合いませんでした。返品できますか。",
                "その他",
                "normal",
            ),
            (
                "海外から購入したい",
                "架空のお客様 E",
                "海外在住です。海外発送と関税の取り扱いについて教えてください。",
                "配送",
                "normal",
            ),
        ]
        for i, (title, customer, body, category, priority) in enumerate(entries):
            db.add(
                Ticket(
                    tenant_id=t.id,
                    title=title,
                    customer=customer,
                    body=body,
                    category=category,
                    priority=priority,
                    assignee_id=users[i % 3].id,
                    status="in_progress" if i == 0 else "open",
                )
            )
        db.add(
            Audit(
                tenant_id=t.id,
                actor="setup",
                action="demo.created",
                target=t.id,
                detail={"fictional": True},
            )
        )
        db.commit()
    print("Fictional demo created. Login: admin@example.test / supplied DEMO_PASSWORD")


if __name__ == "__main__":
    seed()
