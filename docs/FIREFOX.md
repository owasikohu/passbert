# Firefox 実サイト評価拡張

対象はFirefox Desktop 140以降。量子化モデル、Tokenizer、ONNX Runtime Webを同梱し、CPU/WASM 1 threadで実行します。Firefox以外は対象外です。学習用モデルはKaggleから回収したモデルを使っています。

## 読み込み

1. Firefoxで `about:debugging#/runtime/this-firefox` を開く。
2. 「一時的なアドオンを読み込む」で `artifacts/firefox-extension/manifest.json` を選ぶ。
3. 対象のログインページを開き、拡張メニューの「PassBERT フォーム評価」をクリック。必要に応じてツールバーにピン留めする。

`artifacts/passbert-firefox-eval.xpi` も作成します。未署名の開発用なので通常インストール用ではありません。一時読み込みした拡張はFirefox終了時に解除されます。永続配布・AMO公開・署名は行っていません。

「ラベルなしで自動診断・保存」なら正解付けなしで診断を保存できます。この記録は正解未確認として精度集計から除外します。一括テストとv2モデルの情報は[自動化ガイド](AUTOMATION.md)を参照してください。

## 評価手順

1. 拡張ボタンを押すと、その時点のトップフレームを抽出し評価タブを開く。ページを操作して次の段階へ進めたら、再度拡張ボタンを押す。
2. 「ページ上で確認」で各フィールドにF番号と入力欄番号を15秒間表示。位置は押した瞬間のものなので、スクロール後は再表示する。
3. 予測を見ずにフォーム目的・入力欄の正解を選ぶ。情報不足や現在の分類対象外は「判定不能 / 対象外」。これは `other` と区別する。
4. 言語を指定し、「推論して比較」。正解ラベルは予測表示前に固定する。後から訂正したい場合は新しい抽出としてやり直す。
5. 「評価を端末に保存」。同じ抽出の保存は上書き。端末あたり300ページまで。
6. 「JSONLを書き出す」。端末内保存の削除は別ボタン。セッション中の抽出情報はブラウザ終了時に破棄されるが、保存済み評価は明示的に削除するまで残る。

抽出・モデル準備・推論の時間を表示します。初回の推論はwarmupなしで、精密な速度ベンチマークではありません。フォーム情報の表示は限定語彙への変換後のものです。元ページの目視と番号で照合してください。

## データとプライバシー

ユーザーが拡張ボタンを押したタブだけに一時アクセスします。常時動作のcontent scriptや全サイト権限は使いません。取得・保存対象は限定語彙の文脈、type/hint/autocomplete、手動ラベル、予測、可視性、実行時間、モデルのSHA-256です。input.value、textarea本文、選択値、Cookie、URL、ページタイトル、生HTML、スクリーンショットは読み取り・保存しません。ページを送信・自動入力しません。

ホスト名だけを一時的に取得し、SHA-256へ変換してサイトグループのIDとして保存します。元ホスト名やURLはJSONLに含めませんが、ホストのハッシュは辞書照合できるため匿名化の保証ではありません。任意属性やラベルは限定語彙に落としますが、情報の完全な匿名化を保証する仕組みではありません。

外部への送信処理はなく、CSPは接続先を拡張自身に制限しています。依存コードとWASMもローカル同梱です。ブラウザ標準の拡張権限の説明は[MozillaのactiveTab資料](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/permissions#activetab_permission)、WASM用CSPは[MozillaのCSP資料](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/content_security_policy)を参照。

## 保存形式と集計

1行が1回のページ抽出です。`rows` に各フォームの特徴、`form_label`、`field_labels`、`prediction` を保存。`evaluation_only: true` を付けて学習データと区別します。モデルハッシュ・抽出時刻・言語・サイトIDを含みます。実サイト情報のライセンスは自動で付与しません。公開・再配布の権利確認は別途必要です。

```bash
.venv/bin/python -m scripts.evaluate_firefox /path/to/passbert-evaluation.jsonl
```

accuracy、macro-F1、クラス別F1、日英別、推論失敗数を `artifacts/real-site-report.json` に出力。判定不能・推論失敗は精度の分母から除き、件数を別記します。同一snapshotの二重取り込みはエラー。言語やモデルハッシュの混在も確認できます。

同じサイトの複数ページ・同じテンプレートは独立サンプルではありません。現在のグループIDはホスト単位で、registrable domainや関連サイトの統合には未対応。評価セットは学習・Tokenizer・合成生成の改善に使わず、独立した凍結セットとして扱ってください。

## 対応範囲

トップフレームのlight DOMのみ。iframe内・Shadow DOM内、複雑なSPAのフォーム分割は未対応。最大32グループ、各グループ最初の64コントロール。抽出漏れのrecallはこのツール単体では評価できないので、目視で別途記録してください。CSS非表示欄は番号表示できない場合も含め一覧に残し、可視性を記録します。長いフォームは256 token以下の窓に分けて推論します。1入力欄だけで窓の上限を超える場合は失敗を記録し、黙って切り詰めません。ログイン・登録・パスワード再設定・OTP・検索・otherのみの初期モデルです。

## 再ビルドと検証

```bash
npm ci
.venv/bin/python scripts/build_firefox.py
npm run test:extension
npm run lint:firefox
```

モデルを差し替える場合は `--model MODEL_DIRECTORY`。モデルディレクトリには `tokenizer.json` と `model.int8.onnx` が必要です。拡張のソースは `extension/firefox/`、読み込み用の生成物は `artifacts/firefox-extension/` です。生成物は直接編集せず再ビルドします。

任意のFirefox実機スモークにはSeleniumとgeckodriverが別途必要です。

```bash
.venv/bin/pip install selenium
SE_CACHE_PATH="$PWD/artifacts/selenium" .venv/bin/python scripts/firefox_smoke.py --firefox /path/to/firefox
```

一時プロファイルとlocalhostのテストフォームを使い、拡張ボタンから抽出・推論・保存まで確認します。テスト結果と画面は `artifacts/firefox-smoke.json`、`artifacts/firefox-review.png`。このテストは実サイトの精度評価ではありません。

## 今回の検証結果

Firefox 159.0（Linux/headless）の一時プロファイルで、拡張メニューからの抽出、正解入力、WASM推論、端末内保存、元ページの番号表示まで通過しました。テスト用の入力値とURL文字列が保存データに含まれず、入力値も変更されないことを確認。実サイトの精度検証とは別の動作試験です。

計測例: 抽出 4.0 ms / モデル準備 466.0 ms / 推論合計 7.0 ms（WASM 1 thread、初回warmupなし）。1フォームの初回値なので速度比較には使いません。

Pythonテスト6件、既存ブラウザテスト3件、拡張テスト3件を通過。web-ext lintはエラー0件。Firefox Android互換性の警告（Desktop専用）と、同梱ONNX Runtimeの動的importに対する警告が各1件あります。ORTの版とローカルパスを固定し、外部コード読込は許可していません。
