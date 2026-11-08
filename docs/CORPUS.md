# 実フォーム1万件の収集とラベル付け

[今回の収集・パイロット結果](CORPUS_RESULTS.md)。

## 収集するもの

Common Crawl `CC-MAIN-2026-43` のWARC responseからフォームを抽出します。元サイトにアクセスするクローラではありません。各WARCの先頭から上限付きのbyte rangeを取得し、HTMLはメモリ内でHTML5正規化・処理して破棄します。生HTML、元URL、入力値、textarea本文、Cookie、スクリーンショットは保存しません。

保存対象は限定語彙の文脈・type/hint/autocomplete、サイトとホストのハッシュ、言語の根拠、出典のWARCパスと圧縮オフセットです。出典locatorは再抽出のために必要ですが、匿名化を保証するものではありません。データ・SQLite・ラベル候補はGit対象外です。Common Crawlの利用条件と収録サイトの権利は別なので、出典コンテンツに本リポジトリのBSDライセンスを付けません。再配布許可は未確認として記録します。

- 参考: [Common Crawlのアクセス方法](https://commoncrawl.org/get-started)、[利用条件](https://commoncrawl.org/terms-of-use)
- サイトはPSLのregistrable domain単位。private suffixも考慮し、PSLはtldextract同梱版を固定して使用。
- サイトハッシュでtrain/val/testを80/10/10の確率で割り当て。実際の件数比率はサイトごとの件数に左右される。
- 正規化したトークン集合のフォーム特徴で全体重複除去。同一サイトは最大12フォーム。
- 完全重複・canonical重複は除くが、意味的な類似テンプレートの重複除去は保証しない。
- `lang` 属性で日英と判定できない場合は意味語から推定。推定した英語は未確認であり、根拠を別記する。
- `auth-candidate` はパスワード型などに基づく収集用の目印で、ログインの正解ラベルではない。

初期分はHTML5のLexborで正規化してからlxmlで共通抽出ポリシーを適用。後半は同じ仕様のLexbor native抽出器を使います。既存fixtureと実アーカイブ50ページで、特徴とannotation_viewが一致することを確認しました。`--parser reference` で従来処理も選べます。あらゆる壊れたHTMLでのブラウザDOM一致は保証しません。

## 特徴の2つの表示

`form` は現在のモデルと互換の限定語彙、`annotation_view` はラベル付け用に拡張した閉じた意味語彙です。後者には氏名・住所・支払い・会員・変更などの一般語と標準autocomplete tokenを含みます。任意のラベル文字列や属性文字列をそのまま残しません。既知の語彙だけでは表現できない曖昧さは残ります。

初期レコードのannotation_viewはWARC locatorから再抽出します。元の特徴のsignatureと一致することを確認してから追加し、不一致は採用しません。入力欄の順序・個数は共通です。将来のTokenizer/大きなモデルは訓練splitのannotation_viewから学習する計画で、現在の推論モデルへ無条件に渡す特徴ではありません。

## 実行

収集・再抽出・監査・500件の候補ラベル付けを一括実行するには、`.venv/bin/python -m scripts.prepare_corpus`。以下は段階ごとの実行です。

```bash
.venv/bin/pip install -e '.[corpus]'
.venv/bin/python -m scripts.collect_commoncrawl --target 10000 --workers 8
# 中断した場合も同じコマンドでSQLiteから再開。--max-shards は今回実行する上限。
# 安全なチェックポイント停止: 出力先にSTOPという空ファイルを作る。再開前に削除する。
.venv/bin/python -m scripts.enrich_corpus
.venv/bin/python -m scripts.audit_corpus
```

出力は `artifacts/corpus-10k/`。`unlabeled.jsonl` とサイト分割済み `train.jsonl` / `val.jsonl` / `test.jsonl`、manifest、監査レポートを生成します。デフォルトは64MiB × 最大256shardで、上限未達は終了コード2を返します。1万件に達したら停止。収集はseed固定のWARC-prefixサンプルで、Web全体や日英ログインの代表標本ではありません。

## ラベル付けは段階を分ける

最初は全件を教師の回答で確定させず、訓練splitの500件を試験します。

```bash
.venv/bin/python -m scripts.label_corpus --limit 500
```

ローカルの固定revision Zapを使用します。デフォルトのteacher保存先は、既存のZap比較で取得した `artifacts/hf/hub/models--ProCreations--Zap/snapshots/0ab38d45793577230569ad77e0e52fcdfb67b9dc`。教師の重みがない環境では別途取得が必要です。外部LLM APIへデータを送信する処理やAPI課金はありません。

- Zap・属性ルール・autocompleteを消したZapの予測を比較。
- 全体の一致、入力欄単位の一致、信頼度、autocomplete依存を記録。
- 一致した高信頼データも `agreement_candidate`。正解確認済みにはせず、`training_eligible: false` を付ける。
- 不一致・低信頼・autocomplete依存はそれぞれレビュー待ち。
- Zapの11/26分類から現行6/7分類へ変換できない出力は `taxonomy_review`。nativeの予測自体は保持し、無理にotherへ変換しない。
- val/testに教師ラベルを付けない。これらは独立評価用として予約する。

`proposals.jsonl` は正解データセットではありません。`review-sample.jsonl` は状態別のサンプル。`blind-review-requests.jsonl` は教師の予測を隠した、独立した判定用の入力です。ユーザーが全件を手でラベル付けする構成ではありません。

次段階では独立した教師/レビューでこのサンプルを確認し、誤り率・対象分類の定義・候補採用条件を決めます。モデル同士の一致は独立した正解確認の代用ではなく、softmaxの高信頼度も正解率の保証ではありません。

最初の限定語彙300件では全体の高信頼一致が17件に留まりました。限定語彙の情報落ち、分類対象外、教師/ルール不一致を調べる必要があるため、全1万件への確定ラベル付与は行いません。拡張意味語彙での500件パイロット結果を参照して方針を決めます。

## 留意点

静的HTMLなのでJSで後から出現するフォームやShadow DOMは網羅しません。大量のログイン専用データが揃ったとみなさず、auth候補率・日本語比率・サイト数をmanifestで確認します。実サイトをFirefoxで読む評価は別系統です。また、Zapが同じサイトやテンプレートを学習済みである可能性は除去できていません。
