# 作業タスク: jev-claude-router

設計は `docs/DESIGN.md` を参照。フェーズ順に進め、各タスクの「完了条件」を満たしてからチェックを付ける。
Phase 1(Jev判定の検証)を終えるまで、Phase 3以降には進まない。

## Phase 0: 準備

- [x] **T0.1 リポジトリの安全設定**
  `.gitignore`(`.env`, `logs/`, `.venv/`, `__pycache__/` など)と `.env.example`(`TYPESAFE_API_KEY=`, `ANTHROPIC_API_KEY=` のダミー)を追加する。
  完了条件: `.env` を作ってもgitに追跡されない。`git diff --staged` にキーが現れない。
- [x] **T0.2 プロジェクト初期化**
  uvでPython 3.11+のプロジェクトを作り、`typesafe-sdk`, `anthropic`, `pydantic`, `pyyaml`, `python-dotenv`, `pytest`, `ruff` を依存に追加する。`src/router/` の空パッケージを作る。
  完了条件: `uv sync`, `uv run pytest`(テスト0件でも成功), `uv run ruff check .` が通る。
- [x] **T0.3 README初版**
  概要、非公式であること、セットアップ手順(環境変数)、実行方法の見出しを書く。
  完了条件: 第三者がREADMEだけでセットアップ手順を追える。
- [x] **T0.4 CI**
  GitHub Actionsで `ruff` と `pytest` を実行する。APIキーが必要なテストは実行しない(マーカーで分離)。
  完了条件: pushでCIが緑になる。

## Phase 1: Jev判定の検証(最優先)

- [ ] **T1.1 設定読み込み**
  `router/config.py` で `config/questions.json` と `config/tiers.yaml` をpydanticで検証して読む。設計書の初版内容をそのまま `config/` に置く。
  完了条件: 不正な設定(未知のtier名、範囲外の閾値)でわかりやすいエラーが出る。単体テストあり。
- [ ] **T1.2 state組み立て**
  `router/features.py` と `router/state.py` を実装する。文字数などはコードで計算し、長い入力は先頭N文字+末尾M文字に切り詰める。
  完了条件: 長さ境界(ちょうど、超過、空文字)のテストが通る。
- [ ] **T1.3 Jev呼び出し**
  `router/classify.py` で `typesafe-sdk` を使い、質問を1リクエストで送る。タイムアウトとリトライ(SDKの `RetryPolicy`)を設定し、失敗時は例外を独自型にラップする。
  完了条件: 実キーで1件の判定が返る(`@pytest.mark.live` で分離)。モックを使った失敗系テストが通る。
- [ ] **T1.4 評価データの作成**
  `eval/cases.jsonl` に30件以上を作る。内訳の目安: light 10、normal 10、heavy 10。追従文(「それで進めて」など)を5件以上含める。**実際に自分が投げる日本語の指示文を使う**(Claude Codeが下書きし、期待tierはユーザーが確定する)。
  完了条件: 全件に `expected_tier` がある。ユーザーがレビュー済み。
- [ ] **T1.5 評価スクリプト**
  `router/eval.py` を実装する。混同行列、全体一致率、under-routing率、over-routing率、低信頼度の件数を出力する。
  完了条件: `uv run python -m router.eval` が上記を表示する。結果をJSONでも保存できる。
- [ ] **T1.6 質問セットの調整**
  評価結果をもとに、質問文、選択肢、閾値を調整する。少なくとも次を比較して結果を `docs/EVAL_NOTES.md` に記録する。
  - 質問文を英語にした場合と日本語にした場合
  - `meta` あり/なし
  - `previous_*` あり/なし
  完了条件: 合格目安(設計書§11: heavy期待のunder-routing率5%以下、全体一致率80%以上)を満たす設定が決まる。満たせない場合は、原因と代替案(ルールベースの併用など)を `EVAL_NOTES.md` に書いてユーザーに相談する。

## Phase 2: コア + CLI(shadow運用)

- [ ] **T2.1 tier決定ロジック**
  `router/decide.py` を純粋関数で実装する(明示指定、基本tier、floors、低信頼度の引き上げ、追従、reasons出力)。sticky以外を先に作る。
  完了条件: 設計書§7の各規則に対応するテストがある(境界値を含む)。
- [ ] **T2.2 sticky**
  `router/session.py` と `decide` への組み込み。上げるのは即時、下げるのは連続N回判定後。
  完了条件: 上昇・維持・遅延降下のテストが通る。
- [ ] **T2.3 Claude呼び出し**
  `router/claude_client.py` を実装する。tierのモデルと `output_config.effort` を設定し、messages/system/toolsは素通し。ストリーミング対応。`supports_effort` が偽のモデルにはeffortを送らない。
  完了条件: 3つのtierそれぞれで実キーによる呼び出しが成功する(`@pytest.mark.live`)。
- [ ] **T2.4 effort対応とモデルIDの確認**
  DESIGN §14 の#3, #4 を公式ドキュメントで確認し、`tiers.yaml` の `supports_effort` とモデルIDを確定する。結果を設計書に反映する。
  完了条件: 未確認(`null`)の項目がなくなる。
- [ ] **T2.5 判定ログ**
  `router/logging.py` でJSONLを出力する(設計書§11のフィールド)。プロンプト全文は既定で保存しない。
  完了条件: ログにキーやプロンプト全文が出ないことをテストで確認する。
- [ ] **T2.6 CLI**
  `router/cli.py`。shadow時は判定結果のみ表示し、active時は判定どおりにClaudeを呼んでストリーミング表示する。Jev失敗時は `default_tier` で続行する。
  完了条件: 両モードで動作する。Jev障害(不正キーなど)でも回答が返る。
- [ ] **T2.7 shadow運用**
  実際の指示文を数日分shadowで記録し、判定分布と、期待とのずれを確認する。
  完了条件: 閾値・質問の調整案が `EVAL_NOTES.md` にまとまり、ユーザーが `mode: active` への切替を承認する。

## Phase 3: HTTPゲートウェイ

- [ ] **T3.1 FastAPIアプリ**
  `router/gateway.py`。`POST /v1/chat`(Anthropic Messages APIと同形の入力)、SSEで中継、`X-Router-*` ヘッダ、Bearer認証、`/healthz`。
  完了条件: curlでストリーミング応答が得られ、ヘッダにtier/model/effortが入る。
- [ ] **T3.2 会話状態**
  `conversation_id` ごとにstickyの状態を保持する(まずは有効期限つきのインメモリ)。
  完了条件: 同一 `conversation_id` でstickyが働く。TTL切れで状態が消える。
- [ ] **T3.3 ユーザーごとの上限tier**
  設定で `max_tier` を指定できるようにし、判定結果を上限で頭打ちにする。
  完了条件: 上限を超える判定がログに `capped` として残る。
- [ ] **T3.4 Dockerfileと起動手順**
  完了条件: `docker run` で起動でき、READMEに手順がある。

## Phase 4(任意・実験的): Anthropic API互換プロキシ

Phase 3完了後に、作るかどうかをユーザーと決める(DESIGN §14 #8)。

- [ ] **T4.1 `POST /v1/messages` 互換エンドポイント**
  最後のユーザーメッセージで判定し、`model` と `output_config.effort` のみ上書きして転送。ストリーミングはそのまま中継。
  完了条件: Anthropic SDKのbase URLを差し替えただけで動く。
- [ ] **T4.2 互換性の検証**
  ツール利用を含むリクエスト、長い会話、エラー応答が素通しされることを確認し、制約を README に書く。
  完了条件: 既知の非互換点が文書化されている。

## Phase 5: 運用改善

- [ ] **T5.1 ログ集計スクリプト**: tier分布、平均レイテンシ、Jev失敗率、推定コスト削減を出す。
- [ ] **T5.2 継続評価**: 実運用で判定が外れた例を `eval/cases.jsonl` に追加し、CIで回帰を検知する(実キーが要るため手動実行)。
- [ ] **T5.3 メッセージ単位effort(ベータ)の調査**: 会話途中のeffort変更でキャッシュを保てる仕組みが使えるか確認し、sticky規則を緩められるか検討する(DESIGN §14 #6)。
- [ ] **T5.4 Jevのバージョン更新手順**: `jev-latest` へ切り替える前に評価を回す手順を決める。

## 作業ルール

- 1タスク1コミットを目安にし、コミットメッセージにタスクID(例: `T1.3`)を含める。
- 実キーを使うテストは `@pytest.mark.live` を付け、CIでは実行しない。
- 設計と実装が食い違ったら、コードより先に設計書を更新する。
- 判断に迷う点(実装言語、Phase 4の要否、合格基準の妥協など)は、進める前にユーザーへ選択肢つきで確認する。
