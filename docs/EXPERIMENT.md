# 初期実験計画

## 調査

既存コードはREADMEとBSD-3-Clause LICENSEのみ。2026-10-29に参照した [Zap](https://huggingface.co/ProCreations/Zap) はMIT表記、20.7Mパラメータ、8層/384次元、16k WordPiece、フォーム11分類・フィールド26分類。CLSとFLD位置で分類する。公開精度は実データ由来なので本プロジェクトの合成精度と直接比較しない。Zap由来コードやデータはコピーせず、重みは別途取得し固定revisionで評価する。

## 仮説と構成

4層/128次元/4 heads/FFN512、4096語彙、256 positions、約1.35Mパラメータ。ランダム初期化のBERTを教師あり学習。初期版はMLM事前学習なし。Tokenizerは訓練splitだけで学習するため小規模スモークでは実語彙は4096未満。

入力はフォームcontextとフィールドのtype/hint/autocomplete。出力はフォーム6分類、フィールド7分類。対象外Zapラベルはotherに投影する。全フィールドに周囲の文脈が届く。256トークン超は例外にし、黙ってフィールドを切り落とさない。長文窓処理は今後実装。

## 安全なデータ契約

HTMLはネットワークアクセスもスクリプト実行も行わないHTML5 parserで処理。生HTML、URL、action、入力値、textarea本文、選択肢、Cookie、イベント属性は保存しない。name/id/ラベル/placeholderも限定した分類語彙に変換する。任意のテキストから秘密が絶対に復元不能であることは保証できないため、実データ収集はこの初期実験の対象外。ブラウザ抽出も同じ契約。DOM要素参照は保存しない。自動入力・送信は実装しない。

## データと分割

手作り日英合成フォーム。login/signup/recovery/otp/search/other、email/username/current/new password/OTP/search/other。site_id、template_family、language、source、license、signatureをJSONLに記録。合成サイト80/10/10、seed42。サイト番号を特徴に含めず、正規化したモデル入力の完全重複を全splitで除く。各site固有familyだが生成規則は共有するため、未知テンプレートへの汎化を証明する評価ではない。

実サイトへ拡張する際は提供許諾・利用条件を記録し、registrable domain（PSL固定）単位で分割。cross-hostテンプレート類似クラスタを同一splitへまとめ、近似重複も監査する。独立した人手ラベル付き日英実サイトtestを凍結し、学習・語彙作成・閾値調整・合成生成には使わない。Zapの既知収集時期との重なりを記録し、Zap訓練データ非混入は未検証と明記する。

## 評価

valのフォーム/フィールドmacro-F1平均でcheckpoint選択後にtestを一度評価。accuracy、macro-F1、クラス別F1/support、日英別、password識別、identifier識別を最終比較で報告する。初期レポートはaccuracy/macro-F1/クラス別を実装。未出現クラスもF1=0として平均。ヒューリスティックは同じ安全化入力を使用。Zapは元の抽出方式を再現するには追加属性が必要で、初期adapterは安全化情報のみを渡す制約付き比較。

PyTorch、ONNX fp32/int8を同じtestで評価しサイズ・CPU p50/p95を測る。現状時間はtokenizationを含む1フォームずつの経過時間、ONNXは5回warmup。Firefoxの最終計測は同じ端末・ORT Webバージョン・WASM threads・warmup・sequence長を固定し、抽出/tokenize/model/全体を別計測。Python ORTの速度をFirefoxの速度として扱わない。

## 次の実験

1. 合成スモークでラベル整列、分割、学習、exportを検証。
2. 非公開Kaggle T4で同一実験を実行しhardwareと成果物を回収。
3. 固定revisionのZapを同じtestで制約付き比較。
4. independent実サイトtest、語彙制限のablation、autocomplete除去、識別子のみ/多段階ログイン、日英別評価。
5. Firefox WASM実測と量子化ラベル一致検証。合格基準は実サイト評価の前に固定する。

## リポジトリ

passbert/data.py: 抽出・合成・JSONL。train.py: WordPiece/BERT/評価/ONNX。
web/: DOM抽出・ORT Web接続。scripts/: KaggleとZap比較。
tests/: 安全性・分割の回帰テスト。artifacts/: 生成物（git対象外）。

合成データ・独自モデルは本リポジトリのBSD-3-Clause。依存ライブラリ/ONNX Runtimeと外部モデルは各ライセンスが別途適用される。MIT表記だけでZapの元クロールデータの再配布許諾を推定しない。
