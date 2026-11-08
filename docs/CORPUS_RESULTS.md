# 収集・ラベル候補パイロット結果（2026-11-09）

Common Crawl `CC-MAIN-2026-43` の実HTMLから抽出した10,000フォームを保存しました。生HTML・元URL・入力値・Cookieを保存したデータセットではありません。限定語彙の特徴、拡張意味語彙のannotation_view、出典locatorを保存しています。利用・再配布の権利を一括で許諾されたデータとして扱いません。

| 項目 | 件数 |
|---|---:|
| フォーム | 10,000 |
| 入力欄 | 46,722 |
| registrable site（private suffix考慮） | 8,288 |
| train | 7,936 |
| val | 1,079 |
| test | 985 |
| 日本語 | 688 |
| 英語扱い | 9,312 |
| auth-candidate | 2,320 |
| general | 7,463 |
| search-negative | 217 |

言語根拠はHTML langが7,184件、英語の意味語推定が2,759件、日本語の意味語推定が57件。推定は検証済みの言語ではありません。auth-candidateも正解ラベルではありません。ログインフォーム1万件、または日英均等の標本と解釈しないでください。

150個のWARCから上限付きprefixを処理。完了shardの取得量は9.375GiBで、生WARCは保存していません。中断時の未完了リクエストはこの量に含みません。global canonical特徴重複除去と1サイト12件上限を適用。意味的な近似テンプレート重複は別途監査が必要です。

## ラベル付けの試験

訓練splitだけから言語・bucketで層化した500件に、固定revisionのローカルZapと属性ルールで候補を付与。val/testには教師ラベルを付けていません。

| 振り分け | フォーム数 |
|---|---:|
| 高信頼・ルール一致・autocomplete除去でも安定 | 58 |
| 教師とルールの不一致 | 221 |
| 現行6/7分類に収まらないnative出力 | 182 |
| 一致するが低信頼 | 39 |

500フォーム・1,687入力欄のうち、入力欄単位の高信頼一致候補は402欄。日本語215 / 英語285、auth-candidate 189 / general 189 / search-negative 122の層化サンプルであり、全コーパスの比率をそのまま表していません。

一致候補も未検証で、全件 `training_eligible: false`。正解確認済みラベルは0件です。各振り分けから20件ずつ計80件を独立レビュー用に抽出。`blind-review-requests.jsonl` は教師の予測を含まない入力で、使える分類とabstainの形式を指定しています。教師の元の11/26分類出力は保持し、対象外を黙ってotherへ潰していません。

最初の限定語彙300件では全体一致候補17件でした。特徴・標本数・層構成が変わっているため、最終58/500との差を直接的な精度改善とは扱いません。

## 次にすること

1. 80件を独立した強い教師/レビューで盲検判定し、誤りの傾向・不一致・採用条件を確認。
2. annotationのnative 11/26分類と、学生モデルの認証用分類への変換を固定。特にpassword-changeを扱う。
3. 採用条件を満たした弱いラベルと、部分ラベルを別管理して分類学習へ。推定confidenceやモデル同士の一致をgoldと呼ばない。
4. 全訓練フォームは別途MLM候補に使う。Tokenizerにもval/testを使わない。
5. 日本語と認証フォームの不足を狙って補充。独立したFirefox評価セットは別に構築。

## 成果物と検証

- データ: `artifacts/corpus-10k/{unlabeled,train,val,test}.jsonl`
- 状態・出典: `corpus.sqlite`, `manifest.json`
- 監査: `audit.json`（ファイルSHA-256も含む）
- ラベル候補: `label-pilot/proposals.jsonl`, `label-pilot/report.json`
- 独立レビュー: `label-pilot/blind-review-requests.jsonl`

全1万件にannotation_viewがあり、保存特徴のallowlist・入力欄数の対応・signature・canonical重複・サイト分割・評価予約フラグを検査し、エラー0件。サイトのtrain/val/test重複は0。native抽出器は既存fixtureと実アーカイブ50ページでreferenceと一致しました。これらはあらゆるDOMの正しさや、ラベルの正確さの保証ではありません。

Pythonテスト17件、既存ブラウザテスト7件、拡張テスト3件とFirefox実操作（通常・自動保存・長いフォーム）が通過。データはGitに含めず、コードと集計結果のみを保存します。
