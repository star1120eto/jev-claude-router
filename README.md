# jev-claude-router

指示文を [Jev](https://docs.typesafe.ai/)(TypeSafe AI)で判定し、内容に応じて Claude のモデルと effort を自動で選んで呼び出すルーターです。

- 簡単な指示: 安価・高速なモデル + 低 effort
- 通常の指示: 中間のモデル + 中 effort
- 複雑な指示、設計、検証: 最上位モデル + 高 effort

ユーザーから見た使い方は変わりません。回答は Claude がそのまま返し、裏でモデルと effort だけを切り替えます。

> **非公式プロジェクトです。** TypeSafe AI および Anthropic とは無関係で、両社の承認や支援を受けていません。

## 仕組み

Jev は文字列を生成できず、型付きの質問に確率と信頼度つきで答える判定専用モデルです。このルーターでは Jev を「スマートな if 文」として使い、閾値や例外処理はすべてコード側に置きます。

1. 指示文と会話履歴から特徴量を計算する
2. Jev に複数の質問を並列で投げる
3. 回答から tier(light / normal / heavy)を決める
4. tier に対応するモデルと effort で Claude API を呼ぶ
5. 判定結果をログに記録する

詳しい設計は [docs/DESIGN.md](docs/DESIGN.md)、作業計画は [docs/TASKS.md](docs/TASKS.md) を参照してください。

## 現状

開発の初期段階です。Phase 0(準備)を進めており、ルーター本体はまだ動きません。

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 0 | 準備(リポジトリ設定、プロジェクト初期化、README、CI) | 作業中 |
| Phase 1 | Jev 判定の検証 | 未着手 |
| Phase 2 | コアと CLI(shadow 運用) | 未着手 |
| Phase 3 | HTTP ゲートウェイ | 未着手 |

## 必要なもの

- [uv](https://docs.astral.sh/uv/)(Python 3.11 以上は uv が用意します)
- Jev(TypeSafe AI)の API キー。Jev は early access のため、TypeSafe AI から発行を受ける必要があります
- Anthropic の API キー

## セットアップ

```bash
git clone https://github.com/star1120eto/jev-claude-router.git
cd jev-claude-router
uv sync
```

### API キーの設定

API キーは環境変数からのみ読みます。コードや設定ファイルには書きません。

| 環境変数 | 用途 |
|---|---|
| `TYPESAFE_API_KEY` | Jev の判定 |
| `ANTHROPIC_API_KEY` | Claude の呼び出し |

シェルで直接設定する場合:

```bash
export TYPESAFE_API_KEY="..."
export ANTHROPIC_API_KEY="..."
```

`.env` ファイルを使う場合は、`.env.example` をコピーして値を入れ、`uv run` に渡します。`.env` は `.gitignore` で除外されています。

```bash
cp .env.example .env
# .env を編集してキーを入力
uv run --env-file .env pytest -m live
```

## 実行方法

現時点で使えるのは開発用のコマンドだけです。

```bash
uv run pytest              # テスト(API キー不要のもの)
uv run pytest -m live      # 実キーが必要なテスト。API を実際に呼ぶ
uv run ruff check .        # 静的解析
```

次のコマンドは、該当フェーズの実装後に使えるようになります。

```bash
uv run python -m router.eval       # Jev 判定の評価(Phase 1)
uv run python -m router.cli "..."  # CLI(Phase 2)
```

## 設定

判定に使う質問、閾値、tier の定義は `config/` に置く方針です(Phase 1 で追加します)。モデル ID もコードに直書きせず、設定で持ちます。

## プライバシーと安全性

- 判定ログには、既定でプロンプト全文を残しません。記録するのはハッシュ、文字数、Jev の回答などです。全文の保存は、明示的な設定フラグを有効にしたときだけです。
- 入力に混ぜた指示で tier を誘導できる可能性があります。Jev は敵対的な入力に弱いと公式にも記載されています。複数人で使う場合は、ユーザーごとの上限 tier を設ける予定です。

## ライセンス

未設定です。
