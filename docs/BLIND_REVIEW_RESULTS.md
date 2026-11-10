# Qwen3.8-27B盲検レビュー結果（2026-11-10回収）

Kaggle private kernel `owasikohu/passbert-blind-review-qwen38-v1` は完了。Qwen3.8-27B UD-Q6_KをT4 ×2で実行し、88件すべてでschema・分類名・入力欄数を満たす回答を得ました。投入したJSONLと回収metadataのSHA-256を照合済みです。

全体1940.7秒（約32分）、うち重み・ランタイムの取得とモデル準備658.3秒（約11分）。これはラベル付け用の大型教師の所要時間であり、Firefoxの学生モデル推論速度ではありません。

## 確認例

8/8件で期待ラベルと全項目一致。ログイン・登録・OTP・検索・再設定に加え、空のtext欄、文脈のないemail欄、password欄での保留を確認しました。手作りの小さな確認例なので、実サイト正解率100%を意味しません。

## 実コーパス80件

| 結果 | フォーム数 |
|---|---:|
| Zapとフォーム目的・全入力欄が一致 | 43 |
| 全項目を判定したがZapと不一致 | 10 |
| 目的または入力欄にunreviewableを含む | 27 |
| 不正形式・欠落 | 0 |

フォーム目的を判定できた73件では65件でZapと一致。232入力欄のうち78欄を保留し、判定した154欄では132欄で一致しました。これはモデル間一致であり正解率ではありません。保留例でも、一部の判定済み入力欄は比較対象に含みます。

元の高信頼一致候補20件では19件が全項目一致、1件が不一致。他の元区分ごとの一致は、低信頼8/20、taxonomy 6/20、ルール不一致10/20でした。各区分20件の層化サンプルなので母集団比率へ単純に外挿できません。

元の入力欄単位の弱いラベル候補で、追加モデルも同じ判定をしたのは66欄。正解確定や学習への自動昇格はしていません。

## 不一致から分かったこと

- 日本語の「姓／名」をZapがusername、Qwenがfamily-name/given-nameと判定する例があった。
- 「登録」とパスワード欄の組合せでlogin/current-passwordとsignup/new-passwordが割れた。
- 「confirm code」がOTPかcaptchaか、emailがusernameも受け付けるか、といった区別が残る。
- Qwenにも、contextが `change 確認`、入力欄のtype=text・hint空のケースからpassword-change/new-passwordを推測した例があった。新しい大型モデルの回答もそのまま正解にはできない。

したがって、次は情報が欠けた特徴の補強と、保留・採用条件の整備を優先します。限定語彙で落とした文脈を必要な例だけ安全に再抽出し、分類定義（特にpassword-changeとother）を固定してから部分ラベルの学習利用を検討します。

Zapの元の教師もQwen系なので、相関した誤りがあり得ます。人手の独立したgold評価はまだなく、この結果から「Zapより高精度」とは主張しません。

## 回収・監視

自動監視の更新がqueued状態で止まっていたため、この回は状態を再照会して手動で回収・集計しました。原因は断定していません。監視を修正し、status取得を毎回新しいCLIプロセスで行い45秒のtimeout、回収に300秒のtimeoutを設定。更新時刻をUTCで記録します。修正版で再度回収・入力hash検証・集計まで実行して `assessed` を確認しました。

ローカルWSLが停止・スリープしている間の監視や回収は保証できません。その場合もKaggle側の実行結果は同じ回収コマンドで取得できます。

ローカル成果物:

- `artifacts/blind-review/assessment.json`
- `artifacts/blind-review/output/review-output/{reviews.jsonl,metadata.json}`
- `artifacts/blind-review/watch-status.json`

gold_labels=0、training_promotions=0を維持しています。
