# 自動テストと改善（2026-11-08）

## 一括実行

```bash
.venv/bin/pip install -e '.[automation,kaggle]'
npm ci
.venv/bin/python scripts/auto_test.py --firefox /path/to/firefox
# 公開ログインページの読み取り専用スモークも実行する場合
.venv/bin/python scripts/auto_test.py --firefox /path/to/firefox --live
```

デフォルトモデルは `artifacts/kaggle-v2-output/model/`。`--model` で変更できます。モデルがない環境では、下記Kaggle手順で学習・回収してください。Firefoxは利用者の一時プロファイルで起動し、普段のログイン状態を利用しません。geckodriverはSeleniumが管理し、キャッシュは `artifacts/selenium/`。手動正解付けは必要ありません。

Python回帰テスト、共通語彙の整合性、拡張ビルド、Python/ORT Webの窓・ラベル一致、DOM抽出、web-ext lint、Firefox実操作、長いフォーム、モデルの回帰ケースを順に実行します。結果・ログは `artifacts/automation/`。失敗した段階で終了コードを返します。モデル回帰は12ケース中raw 10件以上・属性補正後12件を最低基準にしています。この基準は開発用で、実世界の精度基準ではありません。

GitHub Actionsにはモデルも認証も不要なPython/Nodeの回帰テストを追加しました。push/PRで実行。モデル・WASM実行やパッケージが必要なテストは生成物がないCI環境では明示的にskipし、上記のローカル一括テストで実行します。実サイト訪問・Kaggle学習をCIから自動で繰り返す設定はありません。

## 今回の変更

- フォーム外の見出し、`form=`による外部入力欄、`aria-labelledby`を抽出。
- form要素とform-less入力欄の混在、複数のSPAカードをグループ化。
- hidden/aria-hidden/inline CSS非表示の祖先も確認。分類対象外の要素を除いてから64欄まで抽出。
- textarea/select/contenteditableやコメントの文字列を分類用文脈に混ぜない。
- 長いフォームはフィールドを切断せず256 token以下の窓へ分割。各窓で文脈を再利用し、フォームlogitsを平均。64入力欄をFirefoxで検証。
- 多様な日英ラベル・属性・レイアウト・OTP分割・識別子だけのログインを含むsynthetic-v2で再学習。
- 拡張に「ラベルなしで自動診断・保存」を追加。正解未確認として保存し、精度の分母に含めない。
- 有効なautocompleteなどの属性ルールを併用。補正理由とモデル単体の予測を両方保存し、集計CLIでもraw_modelを別に報告。
- 評価専用レコードを学習/Tokenizer用のデータ読み込みで拒否。

ルールはautocompleteの誤設定にも影響されます。補正後の精度をモデル単体の精度として報告しません。

## 結果

| 開発用12ケース | 入力欄数・グループ分けが正しいケース | 全項目が正しいケース |
|---|---:|---:|
| 旧抽出＋v1モデル | 8/12 | 0/12 |
| 改善抽出＋v1モデル | 12/12 | 3/12 |
| 改善抽出＋v2モデル単体 | 12/12 | 10/12 |
| 改善抽出＋v2＋属性ルール | 12/12 | 12/12 |

これらは改善中に参照した開発ケースであり、独立した精度評価ではありません。合成生成コードは回帰ケースや実サイトのデータを読みません。

公開実サイトはGitHub、GitLab、英語Wikipedia、日本語Wikipedia、はてなの5ページを試行。固定したCSS selectorで事前定義した入力欄との照合は3ページで成立しました。GitLabは取得失敗、はてなは未許可の転送で除外し件数を残しています。3ページ6入力欄の同じ安全化特徴を再生するとv1は3/6、v2 rawは4/6、v2＋属性ルールは6/6。フォーム目的は各版3/3でした。Wikipediaの2入口は中央認証の `auth.wikimedia.org` へ転送されるため、そのホストを明示的に許可し、転送後の同一ホストにグループ化します。言語はページのlang属性を確認して記録します。

これはselectorに基づく少数のsilverラベルで、人手の正解確認も母集団代表性もありません。独立した実サイトtestの精度や、抽出漏れのrecallとして扱えません。抽出漏れ・サイト変更・ブロックは件数とstatusを確認してください。JSONL/生HTML/Cookie/入力値/実サイトのスクリーンショットは収集せず、安全化特徴と件数のみをローカル成果物へ保存します。

v2はTesla T4、12 epochs、1,352,333パラメータ。synthetic-v2はtrain 4696 / val 469 / test 459、seed 20261108。Tokenizerはtrainだけで学習し、valでcheckpoint選択。合成testのフォーム・フィールド正解率は各100%でした。実サイトと上記開発ケースは学習に入れていません。各splitの生成規則は共有しているため、合成testも実サイト精度の代用にはしません。

PythonとORT Webで143ケースのトークン列・窓分割・予測ラベルが一致。Firefox 159で通常評価、自動診断保存、64入力欄の複数窓推論、番号表示、値の非変更を確認。これらは動作試験で、速度は比較用のベンチマークではありません。

## T4で再実行

```bash
.venv/bin/python scripts/kaggle.py prepare --owner YOUR_KAGGLE_USERNAME
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/kaggle.py push --owner YOUR_KAGGLE_USERNAME
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/kaggle.py status --owner YOUR_KAGGLE_USERNAME
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/kaggle.py output --owner YOUR_KAGGLE_USERNAME
```

今回の実行はprivate kernel `owasikohu/passbert-tinybert-v2` version 1。回収先 `artifacts/kaggle-v2-output/`。旧モデルは `artifacts/kaggle-output/` に保持。拡張の再ビルドは `scripts/build_firefox.py`。モデル等の生成物はGit対象外です。
