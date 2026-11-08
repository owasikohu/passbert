# 新しい教師による盲検レビュー

主教師は **Qwen3.8-27B / Unsloth UD-Q6_K**、推論はKaggle T4 ×2上のllama.cppです。軽量なPhi-4-miniを最初に選びましたが、性能を優先する方針に変更し、その待機中ジョブは撤回しました。Windows側の環境は変更していません。

モデルの主張・仕様は[公式Qwenモデルカード](https://huggingface.co/Qwen/Qwen3.8-27B)、量子化ファイルは[Unslothの配布元](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)、サーバー仕様は[llama.cpp](https://github.com/ggml-org/llama.cpp/tree/b12208/tools/server)を参照。モデルカードの一般ベンチマークを、このフォーム分類の性能として扱いません。

## 固定した構成

- モデル: `Qwen/Qwen3.8-27B`
- 配布物: `unsloth/Qwen3.8-27B-GGUF` revision `4ca720788d1e01f1bff70c033e0d0028fd02e502`
- ファイル: `Qwen3.8-27B-UD-Q6_K.gguf`（21,983,677,344 bytes）
- SHA-256: `c9c206812fbe4ac7b76a729e25928b63f2ae89d37f69da7a71c20aec763cd436`
- llama.cpp: `b12208`、CUDA 12.8の公式バイナリとランタイム。両方のSHA-256も検証。
- T4 ×2にlayer splitで全層を配置。ctx 16384 / parallel 4、reasoning budget 512、出力上限896 token。

設定は `configs/review-qwen38-q6.json`。量子化の実体をhashで固定し、公式モデルのrevisionは参照情報として別記します。量子化版と公式最新版の重みが同一であるとは推定しません。

Q6でのGPUメモリ収容と、この課題での有効性は実行で確認します。OOM時に小さいモデルやCPUへ黙って切り替えません。

## レビュー方法

学習splitの500件パイロットから抽出した80件（英語46・日本語34）に、手作りの確認例8件を混ぜます。確認例には、明確なログイン・登録・OTP・検索・再設定と、文脈が足りず判定不能にすべき例を含めます。

GPUジョブへ渡すのは、allowlistで検証したフォーム特徴・record_id・言語・確認例区分だけ。Zapの予測、ルールの予測、候補の振り分け、確認例の期待ラベルは同梱しません。80件全てが訓練split由来であることをローカルで照合してから梱包します。値・Cookie・生HTML・元URLは含みません。外部の有料LLM APIは使わず、非公開Kaggleで公開重みを実行します。

出力はJSON schemaで分類名と入力欄数を制約し、受信後も再検証。余分なキー・自由文・入力欄の脱落・分類外の名前を受け入れません。判断材料が足りない場合は `unreviewable` を許可します。生成された内部思考や自由文は結果データとして保存しません。

結果は **別モデルの意見** です。Zapの元の教師もQwen系なので、同じ系列による相関した誤りがあり得ます。別モデルとの一致をgoldに昇格したり、不一致だけでZapが誤りと断定したりしません。全件 `verified: false` / `training_eligible: false` のままです。

## 実行・回収

```bash
.venv/bin/python -m scripts.prepare_blind_review --owner YOUR_KAGGLE_USERNAME
.venv/bin/kaggle kernels push -p artifacts/blind-review/kernel --accelerator NvidiaTeslaT4
.venv/bin/kaggle kernels status YOUR_KAGGLE_USERNAME/passbert-blind-review-qwen38-v1
.venv/bin/kaggle kernels output YOUR_KAGGLE_USERNAME/passbert-blind-review-qwen38-v1 -p artifacts/blind-review/output
.venv/bin/python -m scripts.summarize_review
```

投入後の自動回収には `.venv/bin/python -m scripts.finish_blind_review` を使います。1ジョブだけを最大6時間監視し、新しいGPUジョブは起動しません。現在状態は `artifacts/blind-review/watch-status.json` に保存し、エラー・時間切れを完了扱いにしません。

元の80件のJSONLと訓練コーパスが必要です。出力は `artifacts/blind-review/output/review-output/`。比較結果は `assessment.json`。確認例の正否、形式違反、保留、モデル間の一致・不一致を分け、元の振り分け別・言語別にも集計します。

GPU待機中や実行失敗を完了扱いにしません。確認例を通過しても実サイト精度や疑似ラベル全体の正確さは証明できず、採用条件の検討材料として使います。
