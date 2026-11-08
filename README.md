# passbert

自動診断・一括テスト・改良モデルの再学習手順: [自動化ガイド](docs/AUTOMATION.md)。Firefox拡張は「ラベルなしで自動診断・保存」に対応しています。

日英のWebフォームを分類するTiny BERT実験。入力値・認証情報・Cookieを収集せず、自動入力やフォーム送信は行いません。

[実験計画・調査・データ方針](docs/EXPERIMENT.md) / [初回実行結果](docs/RESULTS.md) / [Firefox評価拡張](docs/FIREFOX.md)

## 実行

Python 3.10以上、Node.js 20以上。CPU用PyTorchは環境に合う公式wheelを先に導入してください。

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[kaggle]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m passbert.train --generate --epochs 8
npm ci
npm test
HF_HOME="$PWD/artifacts/hf" .venv/bin/python -m scripts.zap_compare
```

`artifacts/data/{train,val,test}.jsonl` に正解付き合成データ、`artifacts/smoke/` にTokenizer・BERT重み・ONNX fp32/int8・report.jsonを出力します。JSONL各行はschema_version/site_id/template_family/language/source/license/signature/form/form_label/field_labels。form.fieldsの順番とfield_labelsは1対1対応です。

初期版はフォーム6分類・入力欄7分類。約1.35Mパラメータ。小型WordPieceはtrainのみで学習。合成サイトを80/10/10に分割し、正規化入力の重複を除去します。モデル入力は限定語彙へ変換した文脈と属性です。現時点の合成結果から実サイト精度を推定しないでください。

## Kaggle T4

Kaggle CLIの公式手順で端末側に認証を設定します。秘密情報をリポジトリへ保存しないでください。認証・GPU利用権限は別途必要です。

```bash
.venv/bin/python scripts/kaggle.py prepare --owner YOUR_KAGGLE_USERNAME
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/kaggle.py push --owner YOUR_KAGGLE_USERNAME
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/kaggle.py status --owner YOUR_KAGGLE_USERNAME
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/kaggle.py output --owner YOUR_KAGGLE_USERNAME
```

private kernelに必要なソースのみを埋め込み、`NvidiaTeslaT4` を要求。実GPU名を検査してT4以外なら中止します。完了後 `artifacts/kaggle-v2-output/` にモデル、データ、レポート、hardware.jsonを回収。既存kernelとの衝突を避けるには `--slug` を変更してください。OAuth認証でT4実行と成果物回収まで検証済みです。

## Firefox / ONNX Runtime Web

`web/extract.mjs` の `extract(document)` で安全化フォームを取得し、`web/infer.mjs` の `load(ort, modelBaseURL)` が返す `predict(form)` で推論します。ORT namespaceはローカルにbundleした `onnxruntime-web` を渡し、WASMファイルも同じ配信元に置きます。`ort.env.wasm.numThreads = 1` でCPU単一threadを指定できます。モデルURLは自分の配信元を使用します。取得対象はモデルとTokenizerで、フォーム情報を送信するコードはありません。

Firefoxの評価用拡張を `extension/firefox/` に実装。`scripts/build_firefox.py` でモデル・ランタイムを同梱します。使い方は [Firefox拡張ガイド](docs/FIREFOX.md) を参照してください。NodeでもDOM整合性、Tokenizer整合性、ORT Web WASMを検証しています。Shadow DOM、iframe境界、CSSによる非表示、複雑なform-less groupingは未対応。長いフォームは256 token以下の窓へ分割し、全入力欄を推論します。

元のBSD-3-Clauseライセンスを維持。Zapは公開重みを固定revisionで参照し、リモートコードは実行しません。比較は安全化した属性だけを渡す制約付き評価です。
