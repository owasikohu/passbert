# 初回実行結果

2026-10-29、ローカルCPU、合成test 224フォーム。train 1871 / val 219。モデル選択はvalのみ。

| モデル | parameters | form accuracy | field accuracy | CPU p50 ms |
|---|---:|---:|---:|---:|
| Tiny BERT PyTorch | 1352333 | 1.0000 | 1.0000 | 2.724 |
| Zap PyTorch（制約付き入力） | 20699173 | 0.9554 | 0.9728 | 22.964 |
| Heuristic | — | 1.0000 | 0.8234 | 0.004 |

| 出力 | bytes | CPU p50 ms | field accuracy |
|---|---:|---:|---:|
| model.onnx | 5506032 | 1.014 | 1.0000 |
| model.int8.onnx | 1540469 | 0.601 | 1.0000 |

Tokenizer実語彙234、埋め込み容量4096。4層/128次元、1,352,333パラメータ。8 epochs、seed42。

時間はtokenizationを含む。PyTorchとPython ORTは2 threads。バックエンドが違う時間は実装込みの参考値。Firefoxの速度ではない。

Tiny BERTは同じ合成生成規則で学習済み。Zapは未学習で、公開抽出器の全情報も渡していない。この結果からモデル間の実サイト性能差を主張できない。

Zap revision: `0ab38d45793577230569ad77e0e52fcdfb67b9dc`。重みのDLは公開MIT表記のものを利用。

Pythonの安全抽出・分割テスト5件を通過。DOM/Python抽出fixtureと全224フォームのTokenizer整合性、ORT Web WASM int8推論を検証。Firefox本体は未検証。

Kaggle [private kernel v1](https://www.kaggle.com/code/owasikohu/passbert-tinybert-v1) は完了、成果物を回収済み。実GPU `Tesla T4`、PyTorch `2.11.0+cu128`、12 epochs。フォーム正解率 1.0000、フィールド正解率 1.0000。量子化ONNXも同じ正解率。train/val/test JSONLのバイト列がローカル生成と完全一致することを確認。成果物は `artifacts/kaggle-output/model/`。OAuth認証を利用。

生成物: `artifacts/data/`, `artifacts/smoke/report.json`, `artifacts/zap-report.json`。環境固定記録: `docs/requirements-smoke.txt`。
