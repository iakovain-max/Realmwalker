"""How loud a sound is, the way ears hear it (ITU-R BS.1770 loudness, in LUFS), so every sound and every tune can
be brought to the same level: the shipped ones when they are built (tools/build_sounds.py), and music the player adds
when it is first played (audio/music.py).

The K-weighting filter (a high shelf at ~1.7 kHz and a high-pass at ~38 Hz) is applied in the frequency domain, block
by block, which needs only numpy.
"""

from __future__ import annotations

import math

import numpy as np

SILENT = -70.0  # LUFS: the absolute gate; anything quieter counts as silence


def _biquad_power(b, a, freqs: np.ndarray, rate: int) -> np.ndarray:
    z = np.exp(-2j * np.pi * freqs / rate)
    num = b[0] + b[1] * z + b[2] * z * z
    den = a[0] + a[1] * z + a[2] * z * z
    return np.abs(num / den) ** 2


def k_weights(freqs: np.ndarray, rate: int) -> np.ndarray:
    """|H(f)|^2 of the BS.1770 K-weighting filter at the given frequencies."""
    # Stage 1: the head's high shelf (+4 dB above ~1.7 kHz), designed for any sample rate (as libebur128 does).
    gain_db, q, fc = 3.99984385397, 0.7071752369554193, 1681.9744509555319
    k = math.tan(math.pi * fc / rate)
    vh = 10 ** (gain_db / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    b1 = ((vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0)
    a1 = (1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0)
    # Stage 2: the RLB high-pass (the ear hears little below ~40 Hz).
    q, fc = 0.5003270373253953, 38.13547087613982
    k = math.tan(math.pi * fc / rate)
    a0 = 1 + k / q + k * k
    b2 = (1.0, -2.0, 1.0)
    a2 = (1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0)
    return _biquad_power(b1, a1, freqs, rate) * _biquad_power(b2, a2, freqs, rate)


def _as_2d(samples: np.ndarray) -> np.ndarray:
    x = np.asarray(samples, dtype=np.float64)
    return x[:, None] if x.ndim == 1 else x


def _block_powers(x: np.ndarray, rate: int, block: int, step: int) -> np.ndarray:
    """Mean square of the K-weighted signal in each block, summed over the channels."""
    n = len(x)
    if n < block:
        x = np.pad(x, ((0, block - n), (0, 0)))
        n = block
    starts = np.arange(0, n - block + 1, step)
    weights = k_weights(np.fft.rfftfreq(block, 1 / rate), rate)
    # Parseval: the mean square of a block from its spectrum (the end bins once, the rest twice).
    scale = np.full(len(weights), 2.0)
    scale[0] = 1.0
    if block % 2 == 0:
        scale[-1] = 1.0
    out = np.zeros(len(starts))
    for i0 in range(0, len(starts), 64):  # 64 blocks at a time keeps the memory small
        idx = starts[i0:i0 + 64, None] + np.arange(block)[None, :]
        for ch in range(x.shape[1]):
            spec = np.fft.rfft(x[idx, ch], axis=1)
            out[i0:i0 + 64] += (np.abs(spec) ** 2 * weights * scale).sum(axis=1) / (block * block)
    return out


def _lufs(power: float) -> float:
    return -0.691 + 10 * math.log10(power) if power > 0 else SILENT - 1


def integrated(samples: np.ndarray, rate: int) -> float:
    """Integrated loudness in LUFS (400 ms blocks, 75% overlap, absolute and relative gates)."""
    x = _as_2d(samples)
    block = int(0.4 * rate)
    powers = _block_powers(x, rate, block, max(1, block // 4))
    loud = np.array([_lufs(p) for p in powers])
    kept = powers[loud > SILENT]
    if len(kept) == 0:
        return SILENT - 1
    relative = _lufs(float(kept.mean())) - 10
    kept = powers[(loud > SILENT) & (loud > relative)]
    return _lufs(float(kept.mean())) if len(kept) else SILENT - 1


def short_peak(samples: np.ndarray, rate: int, window: float = 0.1) -> float:
    """The loudest stretch of a short sound (LUFS over `window` seconds): what a click or a blow sounds like."""
    x = _as_2d(samples)
    n = len(x)
    if n == 0:
        return SILENT - 1
    size = 1 << max(8, int(math.ceil(math.log2(n * 2))))
    weights = k_weights(np.fft.rfftfreq(size, 1 / rate), rate)
    win = max(1, min(n, int(window * rate)))
    best = 0.0
    total = np.zeros(n)
    for ch in range(x.shape[1]):
        filtered = np.fft.irfft(np.fft.rfft(x[:, ch], size) * np.sqrt(weights), size)[:n]
        total += filtered ** 2
    c = np.concatenate([[0.0], np.cumsum(total)])
    best = float(((c[win:] - c[:-win]) / win).max())
    return _lufs(best)


def peak(samples: np.ndarray) -> float:
    x = np.asarray(samples)
    return float(np.abs(x).max()) if x.size else 0.0


def gain_to(level: float, target: float, peak_value: float, *, ceiling: float = 0.89, most: float = 4.0) -> float:
    """The gain that brings a sound measured at `level` to `target`, never letting its peak pass `ceiling` and never
    raising it more than `most` times (a nearly silent file is not blown up into noise)."""
    if level <= SILENT:
        return 1.0
    g = 10 ** ((target - level) / 20)
    if peak_value > 0:
        g = min(g, ceiling / peak_value)
    return max(0.05, min(most, g))
