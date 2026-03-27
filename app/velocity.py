import pandas as pd

from app.cluster_schema import normalize_cluster_df


def compute_velocity(current_df, previous_df):
    columns = ["theme_id", "theme_name", "article_count", "previous_article_count", "velocity"]
    if current_df.empty:
        return pd.DataFrame(columns=columns)

    current_counts = current_df[["theme_id", "theme_name", "article_count"]].copy()
    current_counts = current_counts.rename(columns={"article_count": "current_article_count"})

    if previous_df.empty:
        velocity_df = current_counts.copy()
        velocity_df["previous_article_count"] = 0
        velocity_df["velocity"] = velocity_df["current_article_count"]
    else:
        previous_counts = previous_df[["theme_id", "article_count"]].copy()
        previous_counts = previous_counts.rename(columns={"article_count": "previous_article_count"})
        velocity_df = current_counts.merge(previous_counts, on="theme_id", how="left")
        velocity_df["previous_article_count"] = velocity_df["previous_article_count"].fillna(0).astype(int)
        velocity_df["velocity"] = (
            velocity_df["current_article_count"] - velocity_df["previous_article_count"]
        )

        previous_only = previous_df[~previous_df["theme_id"].isin(current_df["theme_id"])]

        if not previous_only.empty:
            decay_rows = previous_only.copy()
            decay_rows["current_article_count"] = 0
            decay_rows["velocity"] = -decay_rows["article_count"]

            decay_rows = decay_rows.drop(columns=["previous_article_count"], errors="ignore")
            decay_rows = decay_rows.rename(columns={
                "article_count": "previous_article_count"
            })

            velocity_df = pd.concat([velocity_df, decay_rows], ignore_index=True)

    velocity_df = velocity_df.rename(columns={"current_article_count": "article_count"})
    velocity_df = velocity_df.sort_values(
        ["velocity", "article_count"],
        ascending=[False, False],
    ).reset_index(drop=True)
    return velocity_df[columns]


def apply_velocity_metrics(cluster_df, velocity_df):
    if cluster_df.empty:
        return cluster_df

    merged = cluster_df.merge(
        velocity_df[["theme_id", "velocity", "previous_article_count"]],
        on="theme_id",
        how="left",
        suffixes=("", "_velocity"),
    )
    merged = normalize_cluster_df(merged)
    if "velocity_velocity" in merged.columns and "velocity" in merged.columns:
        merged["velocity"] = merged["velocity_velocity"].fillna(merged["velocity"]).fillna(0).astype(int)
    elif "velocity_velocity" in merged.columns:
        merged["velocity"] = merged["velocity_velocity"].fillna(0).astype(int)
    elif "velocity" in merged.columns:
        merged["velocity"] = merged["velocity"].fillna(0).astype(int)
    else:
        merged["velocity"] = 0
    merged["previous_article_count"] = merged["previous_article_count"].fillna(0).astype(int)
    merged["conviction_score"] = (
        (merged["cluster_strength"] * 0.5) +
        (merged["signal_quality"] * 0.3) +
        (merged["velocity"].clip(lower=0) * 0.2)
    ).round(2)
    if "velocity_velocity" in merged.columns:
        merged = merged.drop(columns=["velocity_velocity"])
    return merged.sort_values(
        ["conviction_score", "velocity", "cluster_strength"],
        ascending=[False, False, False],
    ).reset_index(drop=True)