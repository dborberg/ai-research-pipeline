import pandas as pd


def normalize_cluster_df(df):
    if df is None or df.empty:
        return df

    df = df.copy()

    # Core signal fields
    df["signal_quality"] = df.get("signal_quality", df.get("avg_score", 0.0))

    # Velocity fields
    df["velocity"] = df.get("velocity", 0)
    df["previous_article_count"] = df.get("previous_article_count", 0)

    # Safe velocity %
    df["velocity_pct"] = (
        df["velocity"] / df["previous_article_count"].replace(0, 1)
    ).fillna(0.0)

    # Cluster strength fallback
    df["cluster_strength"] = df.get("cluster_strength", df.get("avg_score", 0.0))

    # Conviction score fallback (if missing)
    if "conviction_score" not in df.columns:
        df["conviction_score"] = (
            df["cluster_strength"] * 0.5 +
            df["signal_quality"] * 0.3 +
            df["velocity"].clip(lower=0) * 0.2
        )

    df = df.fillna({
        "signal_quality": 0.0,
        "cluster_strength": 0.0,
        "velocity": 0,
        "velocity_pct": 0.0,
        "conviction_score": 0.0,
    })

    return df
