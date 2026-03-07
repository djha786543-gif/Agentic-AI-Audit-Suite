"""Statistical sampling utilities (Attribute and MUS) aligned to audit practice."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List


def confidence_level_sampling(
    population_size: int,
    confidence_level: float = 0.95,
    margin_error: float = 0.05,
    expected_deviation: float = 0.5,
    seed: int | None = 42,
) -> Dict[str, Any]:
    """
    Generate a statistically valid sample size and random sample IDs.

    Uses finite population correction with z-scores commonly used in audit sampling.
    """
    if population_size <= 0:
        raise ValueError("population_size must be > 0")

    z_lookup = {
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.576,
    }
    rounded_conf = min(z_lookup.keys(), key=lambda c: abs(c - confidence_level))
    z = z_lookup[rounded_conf]

    p = min(max(expected_deviation, 0.01), 0.99)
    e = min(max(margin_error, 0.005), 0.25)

    n0 = (z * z * p * (1 - p)) / (e * e)
    n = n0 / (1 + ((n0 - 1) / population_size))
    sample_size = max(1, min(population_size, int(math.ceil(n))))

    rnd = random.Random(seed)
    sample_ids = sorted(rnd.sample(range(1, population_size + 1), sample_size))

    return {
        "method": "confidence_level_sampling",
        "population_size": population_size,
        "sample_size": sample_size,
        "confidence_level": rounded_conf,
        "z_score": z,
        "margin_error": e,
        "expected_deviation": p,
        "sample_ids": sample_ids,
        "pcaob_note": "Finite-population corrected sample size aligned to statistical audit sampling practice.",
    }


def attribute_sampling(population: List[Dict[str, Any]], sample_size: int, seed: int | None = 42) -> Dict[str, Any]:
    """Simple random attribute sampling."""
    if sample_size <= 0:
        raise ValueError("sample_size must be > 0")
    if sample_size > len(population):
        sample_size = len(population)
    rnd = random.Random(seed)
    indices = sorted(rnd.sample(range(len(population)), sample_size))
    sample = [population[i] for i in indices]
    return {
        "method": "attribute_sampling",
        "population_size": len(population),
        "sample_size": sample_size,
        "sample_indices": indices,
        "sample": sample,
        "aicpa_note": "Attribute sampling suitable when testing pass/fail control deviations.",
    }


def mus_sampling(
    population: List[Dict[str, Any]], amount_field: str = "invoice_amount", confidence_factor: float = 3.0,
                 tolerable_misstatement: float = 10000.0, expected_misstatement: float = 1000.0,
                 seed: int | None = 42) -> Dict[str, Any]:
    """Monetary Unit Sampling (MUS) with interval-based selection."""
    if not population:
        return {
            "method": "mus",
            "population_size": 0,
            "sample_size": 0,
            "sample": [],
            "aicpa_note": "Monetary Unit Sampling targets higher-value items with probability proportional to size.",
        }

    amounts: List[float] = []
    for row in population:
        try:
            amounts.append(float(str(row.get(amount_field, "0")).replace(",", "").replace("$", "")))
        except ValueError:
            amounts.append(0.0)

    total_book_value = sum(max(a, 0.0) for a in amounts)
    if total_book_value <= 0:
        return attribute_sampling(population, min(25, len(population)), seed=seed)

    denominator = max(tolerable_misstatement - expected_misstatement, 1.0)
    sample_size = max(1, int(math.ceil((confidence_factor * total_book_value) / denominator)))
    sample_size = min(sample_size, len(population))

    interval = total_book_value / sample_size
    rnd = random.Random(seed)
    start = rnd.uniform(0.0, interval)

    picks: List[Dict[str, Any]] = []
    cumulative = 0.0
    target = start
    for idx, amount in enumerate(amounts):
        cumulative += max(amount, 0.0)
        while cumulative >= target and len(picks) < sample_size:
            picks.append(population[idx])
            target += interval

    return {
        "method": "mus",
        "population_size": len(population),
        "sample_size": len(picks),
        "interval": round(interval, 2),
        "sample": picks,
        "aicpa_note": "MUS selected using probability-proportional-to-size intervals.",
    }
