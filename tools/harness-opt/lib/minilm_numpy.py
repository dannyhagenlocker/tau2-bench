"""Offline sentence-transformers/all-MiniLM-L6-v2 encoder in pure NumPy.

This dev machine has no network and no torch, but the HF cache already holds
the model weights (``model.safetensors``) and tokenizer, and ``tokenizers`` +
``numpy`` + ``scipy`` are installed. So we run the BERT forward pass directly
in NumPy to get real MiniLM sentence embeddings without torch / sentence-
transformers. Architecture (from config.json): BertModel, 6 layers, hidden
384, 12 heads, intermediate 1536, gelu, LayerNorm eps 1e-12, mean pooling.
"""

from __future__ import annotations

import json
import struct
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

_MODEL_REPO = "models--sentence-transformers--all-MiniLM-L6-v2"
_EPS = 1e-12
_N_LAYERS = 6
_N_HEADS = 12


def _model_dir() -> Path:
    base = Path.home() / ".cache" / "huggingface" / "hub" / _MODEL_REPO / "snapshots"
    snaps = sorted(base.glob("*/")) if base.exists() else []
    if not snaps:
        raise RuntimeError(
            f"all-MiniLM-L6-v2 not found in HF cache ({base}). The offline "
            "'st' embedder requires the model to be pre-cached."
        )
    return snaps[-1]


def _load_safetensors(path: Path) -> dict[str, np.ndarray]:
    dtypes = {
        "F64": np.float64,
        "F32": np.float32,
        "F16": np.float16,
        "I64": np.int64,
        "I32": np.int32,
    }
    with open(path, "rb") as fh:
        (header_len,) = struct.unpack("<Q", fh.read(8))
        header = json.loads(fh.read(header_len))
        buf = fh.read()
    out: dict[str, np.ndarray] = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        start, end = meta["data_offsets"]
        arr = np.frombuffer(buf[start:end], dtype=dtypes[meta["dtype"]])
        out[name] = arr.reshape(meta["shape"]).astype(np.float32)
    return out


class _MiniLM:
    def __init__(self) -> None:
        from tokenizers import Tokenizer

        model_dir = _model_dir()
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.w = _load_safetensors(model_dir / "model.safetensors")

    def _get(self, name: str) -> np.ndarray:
        if name in self.w:
            return self.w[name]
        prefixed = f"bert.{name}"
        if prefixed in self.w:
            return self.w[prefixed]
        raise KeyError(name)

    @staticmethod
    def _layernorm(x, weight, bias):
        mu = x.mean(-1, keepdims=True)
        var = x.var(-1, keepdims=True)
        return (x - mu) / np.sqrt(var + _EPS) * weight + bias

    @staticmethod
    def _linear(x, weight, bias):
        return x @ weight.T + bias

    @staticmethod
    def _gelu(x):
        from scipy.special import erf

        return 0.5 * x * (1.0 + erf(x / np.sqrt(2.0)))

    @staticmethod
    def _softmax(x):
        x = x - x.max(axis=-1, keepdims=True)
        e = np.exp(x)
        return e / e.sum(axis=-1, keepdims=True)

    def encode(self, docs: list[str], *, normalize: bool = True) -> np.ndarray:
        encs = self.tokenizer.encode_batch([d or "" for d in docs])
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.float32)
        n, seq = ids.shape

        x = (
            self._get("embeddings.word_embeddings.weight")[ids]
            + self._get("embeddings.position_embeddings.weight")[:seq][None, :, :]
            + self._get("embeddings.token_type_embeddings.weight")[0][None, None, :]
        )
        x = self._layernorm(
            x,
            self._get("embeddings.LayerNorm.weight"),
            self._get("embeddings.LayerNorm.bias"),
        )

        # additive attention-mask bias: (n, 1, 1, seq)
        bias = (1.0 - mask)[:, None, None, :] * -1e9
        hidden = x.shape[-1]
        dh = hidden // _N_HEADS

        for i in range(_N_LAYERS):
            p = f"encoder.layer.{i}."
            q = self._linear(
                x,
                self._get(p + "attention.self.query.weight"),
                self._get(p + "attention.self.query.bias"),
            )
            k = self._linear(
                x,
                self._get(p + "attention.self.key.weight"),
                self._get(p + "attention.self.key.bias"),
            )
            v = self._linear(
                x,
                self._get(p + "attention.self.value.weight"),
                self._get(p + "attention.self.value.bias"),
            )

            def split(t):
                return t.reshape(n, seq, _N_HEADS, dh).transpose(0, 2, 1, 3)

            qh, kh, vh = split(q), split(k), split(v)
            scores = qh @ kh.transpose(0, 1, 3, 2) / np.sqrt(dh) + bias
            ctx = self._softmax(scores) @ vh
            ctx = ctx.transpose(0, 2, 1, 3).reshape(n, seq, hidden)

            attn = self._linear(
                ctx,
                self._get(p + "attention.output.dense.weight"),
                self._get(p + "attention.output.dense.bias"),
            )
            x = self._layernorm(
                x + attn,
                self._get(p + "attention.output.LayerNorm.weight"),
                self._get(p + "attention.output.LayerNorm.bias"),
            )

            inter = self._gelu(
                self._linear(
                    x,
                    self._get(p + "intermediate.dense.weight"),
                    self._get(p + "intermediate.dense.bias"),
                )
            )
            out = self._linear(
                inter,
                self._get(p + "output.dense.weight"),
                self._get(p + "output.dense.bias"),
            )
            x = self._layernorm(
                x + out,
                self._get(p + "output.LayerNorm.weight"),
                self._get(p + "output.LayerNorm.bias"),
            )

        # mean pooling over real tokens
        summed = (x * mask[:, :, None]).sum(axis=1)
        counts = np.clip(mask.sum(axis=1, keepdims=True), 1e-9, None)
        emb = summed / counts
        if normalize:
            norms = np.linalg.norm(emb, axis=1, keepdims=True)
            emb = emb / np.clip(norms, 1e-12, None)
        return emb.astype(np.float32)


@lru_cache(maxsize=1)
def _model() -> _MiniLM:
    return _MiniLM()


def encode(docs: list[str], *, normalize: bool = True) -> np.ndarray:
    return _model().encode(list(docs), normalize=normalize)


def is_available(model_name: Optional[str] = None) -> bool:
    try:
        _model_dir()
        import tokenizers  # noqa: F401

        return True
    except Exception:
        return False
