# 設計書: jev-claude-router

## 1. 目的

指示文を送ると、内容に応じてClaudeのモデルとeffortを自動で選んで呼び出す。

- 簡単な指示: 安価・高速なモデル + 低effort
- 通常の指示: 中間のモデル + 中effort
- 複雑な指示、設計、検証: 最上位モデル + 高effort

ユーザーから見た使い方は変えない。回答はClaudeがそのまま返す。判定にはJev(TypeSafe AIのSystem Oneモデル)を使う。

## 2. 前提と制約

- Jevは文字列を生成できない。型付きの質問(Choice / Score / Noul)に、確率と信頼度つきで答える判定専用モデル。回答文の生成は常にClaudeが行う。
- Jevはearly access。APIキーは発行済み。
- Jevは字義通りに読む、数値・日付の比較が苦手、状態(state)に無関係な情報が多いと精度が落ちる、入力に混ぜた指示に弱い、という既知の弱点がある。設計はこれを前提にする。
- 日本語の指示文に対するJevの精度は、公開情報から確認できていない。Phase 1で検証する。
- 本リポジトリは公開設定。秘密情報を含めない。

## 3. 全体アーキテクチャ

```
クライアント(チャットUI / CLI / 既存ツール)
        │  指示文 + 会話履歴
        ▼
┌──────────────────────── router ─────────────────────────┐
│ 1. features   : コードで特徴量を計算(文字数、コードブロック有無など)   │
│ 2. classify   : Jevを1回呼ぶ(質問を並列で複数)                │
│ 3. decide     : 回答からtierを決定(純粋関数)                  │
│ 4. claude     : tierのモデル/effortでClaude APIを呼ぶ          │
│ 5. log        : 判定結果をJSONLに記録                        │
└──────────────────────────────────────────────────────────┘
        │  ストリーミングをそのまま返す
        ▼
クライアント
```

原則: Jevは「スマートなif文」として使い、統合・閾値・例外処理はすべてコード側に置く。Jevに複数の判断を1問に詰めない。

## 4. コンポーネント

| モジュール | 役割 |
|---|---|
| `router/config.py` | `config/*.yaml|json` を読み、pydanticで検証する |
| `router/features.py` | 指示文と履歴から、コードで計算できる特徴量を作る |
| `router/state.py` | Jevに渡す `state` を組み立てる(切り詰め含む) |
| `router/classify.py` | Jev呼び出し。タイムアウト、リトライ、失敗時フォールバック |
| `router/decide.py` | tier決定。Jevもネットワークも使わない純粋関数 |
| `router/claude_client.py` | tierに応じたモデル/effortでClaude APIを呼ぶ。ストリーミング対応 |
| `router/session.py` | 会話ごとの直近tierを保持(sticky制御用) |
| `router/logging.py` | 判定ログのJSONL出力 |
| `router/cli.py` | Phase 2: CLI入口 |
| `router/gateway.py` | Phase 3: HTTP入口(FastAPI) |
| `router/eval.py` | Phase 1: 評価スクリプト |

## 5. Jev API仕様(公式ドキュメントから確認済みの範囲)

- エンドポイント: `POST https://api.typesafe.ai/v1/systemone`、`Authorization: Bearer <API_KEY>`
- リクエスト: `state`(文字列またはJSONオブジェクト)、`model`(例: `jev-latest`、`jev-1.13`)、`questions`(名前 → 質問定義)
- 質問の型:
  - `choice`: `instructions` と `criteria`(選択肢名 → 説明)。返り値は `choice`, `probabilities`, `confidence`
  - `score`: `instructions` と `criteria`(順序つきレベルの配列)。返り値は `score`, `probabilities`, `confidence`
  - `noul`: `instructions` のみ。返り値は `noul`(0〜1のyes確率)
- 全質問は同一stateに対して並列・独立に評価される。質問を増やしても応答時間はほとんど変わらない。
- Python SDK: `pip install typesafe-sdk`(Python 3.10以上)。`TypeSafeClient()` は環境変数 `TYPESAFE_API_KEY` を読む。`client.system_one(state=..., questions={...})` の結果は `response.answers["name"].choice / .score / .noul / .confidence`。
- 評価の再現性のため、評価時は `jev-latest` ではなくバージョン固定(例: `jev-1.13`)を使う。

## 6. Jevに投げる質問(初版)

`config/questions.json`。英語で、直接的に書く。1問1判断。

```json
{
  "task": {
    "type": "choice",
    "instructions": "What is the main kind of work the user's current request asks for?",
    "criteria": {
      "simple_qa": "A short factual question or a quick lookup",
      "rewrite_translate": "Rewrite, translate, proofread, or reformat given text",
      "summarize_extract": "Summarize a text or extract specific items from it",
      "code_write": "Write new code or make a small, clearly specified code change",
      "debug": "Find and fix the cause of a bug, error, or failing test",
      "design": "Design an architecture, system, data model, or plan, or compare design options",
      "review_verify": "Review, audit, or verify existing work, code, or a plan for problems",
      "analysis": "Analyze information or reason through a problem that has several steps or factors",
      "chat_other": "Casual conversation or anything else"
    }
  },
  "depth": {
    "type": "score",
    "instructions": "How many separate reasoning steps or independent factors are needed to answer the current request well?",
    "criteria": [
      "One step or direct recall",
      "Several steps in a clear order",
      "Many interacting factors or trade-offs that must be weighed"
    ]
  },
  "scope": {
    "type": "score",
    "instructions": "How large is the thing the current request asks to be produced or changed?",
    "criteria": [
      "A single small item such as one sentence, one function, or one answer",
      "Several related items such as a few files or sections",
      "A whole system, a large document, or many interdependent parts"
    ]
  },
  "verify": {
    "type": "noul",
    "instructions": "The current request asks to check, review, audit, or verify something for correctness or problems."
  },
  "followup": {
    "type": "noul",
    "instructions": "The current request only makes sense together with the previous messages, for example it tells the assistant to continue or proceed with what was discussed."
  }
}
```

この質問セットは出発点。Phase 1の評価結果に基づいて、質問文と選択肢を調整する。

### state の組み立て

```json
{
  "current_request": "<今回の指示文。長い場合は先頭N文字 + 末尾M文字>",
  "previous_request": "<直前のユーザー指示。先頭のみ>",
  "previous_reply_head": "<直前のアシスタント回答の先頭のみ>",
  "meta": { "turn_index": 3, "has_code_block": true, "attachment_count": 0, "request_chars": 812 }
}
```

- 切り詰めの長さは `config/tiers.yaml` の `state` セクションで設定する。Jevのコンテキスト長には上限があるため、上限値は公式のモデルページで確認する。
- `meta` の数値はコードで計算する。Jevに数えさせない。`meta` が精度に効くかはPhase 1でA/B比較し、効かなければ削除する。
- `followup` を除き、`previous_*` はJevに解釈させる補助情報にとどめる。

## 7. tier決定ロジック

`router/decide.py`。純粋関数。入力は Jevの回答、会話の直近tier、設定。出力は `Decision(tier, reasons[])`。`reasons` は判定ログにそのまま残す。

```
1. 明示指定: 指示文の先頭が /light /normal /heavy ならそのtierを採用(設定で有効化)
2. 基本tier:
     verify.noul > thresholds.verify_noul  または  task が design / review_verify → heavy
     それ以外は s = depth.score + scope.score
        s < score_sum_normal → light
        s < score_sum_heavy  → normal
        それ以外              → heavy
3. 下限(floors): task が code_write / debug なら light を normal に引き上げる
4. 低信頼度: min(depth.confidence, task.confidence) < thresholds.low_confidence なら1段階上げる
5. 追従: followup.noul > thresholds.followup_noul なら、直近tier未満にならないようにする
6. sticky: 会話中の切替コストを抑える(下記)
```

### sticky(切替の抑制)

モデルの切替はプロンプトキャッシュを無効化する。effortもトップレベル指定を変えるとキャッシュの先頭一致が保たれない。そのため会話内では次のルールで安定させる。

- 上げるのは即時。
- 下げるのは、下位tierが `sticky.downgrade_after_turns` 回連続で判定されたときだけ。
- 会話が短い(`turn_index` が小さい)うちはキャッシュの効果も小さいので、設定で無効化できるようにする。

### Jev失敗時

タイムアウト、認証エラー、レート制限、レスポンス不正のいずれでも、リクエストを止めず `default_tier`(初期値 normal)で続行し、ログに `jev_error` を残す。Jevの障害でユーザーの利用を止めない。

## 8. Claude呼び出し

- Messages APIを使う。`model` と `output_config: {"effort": "<level>"}` をtierごとに設定する。システムプロンプト、ツール、メッセージ履歴は一切改変せず素通しにする。
- effortの指定値は `low / medium / high`(上位モデルはさらに `xhigh / max`)。初期のheavyは `high` とし、評価で必要と分かった場合のみ引き上げる。
- effortに対応しないモデルへは `output_config.effort` を送らない(400になり得る)。`supports_effort` を設定に持たせ、Phase 2で実際に確認して確定する。
- thinking設定はルーターでは触らない。クライアントが指定したものを素通しする。
- `max_tokens` はtierごとの既定値を持ち、クライアント指定があればそちらを優先する。
- ストリーミングはSDKのイベントをそのまま中継する。

## 9. 設定ファイル(`config/tiers.yaml` 初版)

```yaml
mode: shadow              # shadow: 判定をログに残すだけで、モデルは既定のまま / active: 判定どおりに切替
default_tier: normal      # Jev失敗時
jev:
  model: jev-1.13         # 評価時は固定。運用でlatestにするかは別途判断
  timeout_sec: 3
tiers:
  light:
    model: claude-haiku-4-5-20251001
    effort: low
    supports_effort: null   # 要確認。確認後に true / false
    max_tokens: 4096
  normal:
    model: claude-sonnet-5-5
    effort: medium
    supports_effort: true
    max_tokens: 8192
  heavy:
    model: claude-opus-5-5
    effort: high
    supports_effort: true
    max_tokens: 16000
thresholds:
  verify_noul: 0.5
  followup_noul: 0.5
  low_confidence: 0.5
  score_sum_normal: 1
  score_sum_heavy: 3
floors:
  code_write: normal
  debug: normal
sticky:
  enabled: true
  downgrade_after_turns: 3
state:
  request_head_chars: 1500
  request_tail_chars: 500
  previous_request_chars: 300
  previous_reply_chars: 300
override_prefix_enabled: true
log:
  path: logs/decisions.jsonl
  store_prompt_text: false
```

モデルIDは設定値として持ち、コードに直書きしない。IDと対応effortは実装時に公式情報で確認する。

## 10. 入口(フェーズ別)

### Phase 2: CLI
`uv run python -m router.cli "指示文"`。判定結果(tier, model, effort, reasons)を表示し、`mode: active` のときはClaudeの回答をストリーミング表示する。

### Phase 3: HTTPゲートウェイ(FastAPI)
- `POST /v1/chat`: `messages`, `system`, `tools` などをAnthropic Messages APIと同じ形で受け、`conversation_id` があればstickyの状態を紐付ける。
- 応答はSSEで中継。デバッグ用にレスポンスヘッダ `X-Router-Tier`, `X-Router-Model`, `X-Router-Effort` を付ける。
- 認証はゲートウェイ自身のBearerトークン(環境変数)。Anthropic/TypeSafeのキーはサーバー側だけが持つ。

### Phase 4(任意・実験的): Anthropic API互換プロキシ
- `POST /v1/messages` を受け、最後のユーザーメッセージで判定し、`model` と `output_config.effort` だけを上書きして転送。ストリーミングはそのまま中継。
- 既存クライアントのbase URLを差し替えるだけで使えるのが利点。ただし、クライアントが指定したモデルを上書きすることになるため、ツール利用などクライアント側の想定と食い違わないか検証が要る。

## 11. ログと評価

### 判定ログ(JSONL、1リクエスト1行)
`ts`, `conversation_id`, `prompt_sha256`, `request_chars`, Jevの各回答(値、confidence、確率)、`tier_base`, `tier_final`, `reasons[]`, `model`, `effort`, `jev_latency_ms`, `jev_error`, `usage`(Claudeのトークン数)。プロンプト全文は `store_prompt_text: true` のときだけ。

### 評価(`eval/cases.jsonl`)
1行1件: `{"id": "...", "prompt": "...", "history": [...], "expected_tier": "light|normal|heavy", "note": "..."}`。

`router.eval` の出力:
- 混同行列(期待tier × 判定tier)
- 全体一致率
- **under-routing率**(期待がnormal/heavyなのに、それより低いtierに振った割合)。最優先の指標
- over-routing率(コスト増の目安)
- 低信頼度で引き上げた件数

初期の合格目安(要調整): under-routing率は heavy期待で 5%以下、全体一致率は 80%以上。

### shadow運用
実運用の入力に対して判定だけを記録し、数日分を見て閾値と質問文を調整してから `mode: active` に切り替える。

## 12. セキュリティ

- キーは環境変数のみ。`.env.example` にはダミー値だけを置く。
- 入力に混ぜた指示でtierを誘導できる(Jevは敵対的入力に弱いと公式にも記載)。複数人で使う場合は、ユーザーごとに上限tier(`max_tier`)を設ける。
- ログにプロンプト全文を残さないことを既定にする。

## 13. ディレクトリ構成

```
jev-claude-router/
├ CLAUDE.md
├ README.md
├ pyproject.toml
├ .env.example
├ .gitignore
├ config/
│  ├ questions.json
│  └ tiers.yaml
├ docs/
│  ├ DESIGN.md
│  └ TASKS.md
├ eval/
│  └ cases.jsonl
├ logs/                # gitignore
├ src/router/
│  ├ config.py  features.py  state.py  classify.py  decide.py
│  ├ claude_client.py  session.py  logging.py
│  ├ cli.py  gateway.py  eval.py
└ tests/
```

## 14. 未決事項・要検証

| # | 項目 | 確認方法 | 反映先 |
|---|---|---|---|
| 1 | 日本語stateでのJevの精度 | Phase 1の評価 | questions.json、state設計 |
| 2 | Jevのコンテキスト長上限 | Jevドキュメントのモデルページ | tiers.yaml の state 長さ |
| 3 | Haiku 4.5がeffortに対応するか | Anthropicのeffortドキュメントの対応モデル表 | tiers.yaml の supports_effort |
| 4 | 各モデルID、effortの選択可能値 | Anthropic公式のモデル一覧とeffortドキュメント | tiers.yaml |
| 5 | Jevのレート制限、料金、SLA | Jevドキュメント、コンソール | タイムアウトとリトライ設定 |
| 6 | 会話途中のeffort変更でキャッシュを保つ「メッセージ単位のeffort(ベータ)」の対象モデルと条件 | Anthropicのeffortドキュメント | sticky設計の見直し(最適化として) |
| 7 | 実装言語(Python前提でよいか) | 作業開始時にユーザーへ確認 | 全体 |
| 8 | Phase 4(互換プロキシ)を作るか | Phase 3完了後に判断 | ロードマップ |
