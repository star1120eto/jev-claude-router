# jev-claude-router

指示文をJev(TypeSafe AI)で判定し、Claude APIのモデルとeffortを自動選択して呼び出すルーター。
ユーザーから見た使い方は変えず、裏でモデルとeffortだけを切り替える。非公式プロジェクト。

## 最初に読むもの

- `docs/DESIGN.md` : 設計(アーキテクチャ、Jev質問定義、tier決定ロジック、設定ファイル)
- `docs/TASKS.md` : 作業タスク(フェーズ順、完了条件つき)

作業は `docs/TASKS.md` のフェーズ順に進める。Phase 1(Jev判定の検証)を終える前に、ゲートウェイ(Phase 3以降)へ進まない。

## 絶対に守ること

- APIキー(`TYPESAFE_API_KEY`, `ANTHROPIC_API_KEY`)をコード、設定ファイル、ログ、テスト、コミット履歴に含めない。環境変数からのみ読む。
- このリポジトリは公開設定。`.env` は `.gitignore` に入れ、コミット前に `git diff --staged` でキー混入を確認する。
- ログにはプロンプト全文を既定で残さない(ハッシュ、文字数、Jevの回答のみ)。全文保存は明示的な設定フラグがあるときだけ。

## 実装時に必ず公式ドキュメントで確認すること(未検証の前提)

設計書の「未決事項・要検証」に一覧がある。推測で実装せず、以下の一次情報で確認して結果を設計書に反映する。

- Jev: https://docs.typesafe.ai/llms.txt (ドキュメント索引。各ページは `.md` で取得できる)
- Claude effort: https://platform.claude.com/docs/en/build-with-claude/effort
- モデルID・対応状況: Anthropic公式のモデル一覧

## 技術スタック(仮定。変更する場合は設計書を更新)

Python 3.11+、uv、`typesafe-sdk`、`anthropic`、pydantic、FastAPI(Phase 3以降)、pytest、ruff。

## コマンド(Phase 0で整備する)

```
uv sync
uv run pytest
uv run ruff check .
uv run python -m router.eval      # Jev判定の評価(Phase 1)
uv run python -m router.cli "..."  # CLI(Phase 2)
```

## 方針

- 判定ロジック(`decide`)は純粋関数にして、Jevもネットワークも使わずにテストできるようにする。
- 閾値、質問文、tier定義は `config/` に置き、コードに埋め込まない。
- 判定が外れたときの被害は「軽く見積もりすぎ」のほうが大きい。評価では under-routing(重い依頼を軽いtierに振る誤り)を最優先で見る。
- 質問文と選択肢は、直接的で文字通りに読める英語で書く(Jevは字義通りに読む傾向があるため)。日本語stateでの精度は Phase 1 で検証する。
