# Transformer Chinese-to-English Translation

A from-scratch TensorFlow implementation of an encoder-decoder Transformer for Chinese-to-English neural machine translation.

## What is implemented

- Chinese normalization and Jieba tokenization, plus English text preprocessing
- Train/validation splitting and TensorFlow input pipelines
- Sinusoidal positional encoding
- Padding and look-ahead attention masks
- Scaled dot-product and multi-head attention
- Encoder and decoder stacks with residual connections and normalization
- Transformer learning-rate schedule, masked loss, checkpointing, inference, and attention visualization

The saved notebook output records an 80-epoch run with final training loss `0.1570`, token-level training accuracy `0.9345`, validation loss `0.5398`, and validation accuracy `0.8853`. These are the metrics emitted by the notebook's training loop; they are not BLEU scores.

## Repository contents

- `transformer_zh_en.ipynb`: complete model, training, evaluation, and visualization workflow
- `requirements.txt`: Python dependencies

Model checkpoints and the parallel corpus are intentionally excluded to keep the repository lightweight and respect dataset redistribution constraints. Place a tab-separated Chinese-English corpus at `data/cmn.txt` and update the dataset path in the notebook before training.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter lab transformer_zh_en.ipynb
```

The notebook was developed as a university natural-language-processing project.

