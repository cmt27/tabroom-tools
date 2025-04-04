import pandas as pd
import re

def compute_metrics_per_judge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes overall metrics for each judge (across all rounds) in the provided judge records DataFrame.
    
    Metrics include:
      - Rounds Judged: Total rounds with valid vote ("Aff" or "Neg").
      - Aff Win Rate (%): Percentage of valid rounds with vote "Aff".
      - Squirrel Rate (%): For panel rounds only (Result non-empty and containing a dash),
        the percentage of rounds where the judge's vote differs from the overall outcome.
    
    Returns a DataFrame with one row per judge.
    """
    def valid_vote(vote):
        return isinstance(vote, str) and vote.strip().lower() in ("aff", "neg")

    valid_df = df[df['Vote'].apply(valid_vote)].copy()
    groups = valid_df.groupby(["JudgeID", "JudgeName"])
    results = []
    
    for (judge_id, judge_name), group in groups:
        total_rounds = len(group)
        aff_count = group['Vote'].str.strip().str.lower().eq("aff").sum()
        aff_win_rate = (aff_count / total_rounds * 100) if total_rounds > 0 else 0.0

        def is_panel(result):
            return isinstance(result, str) and result.strip() != "" and "-" in result

        panel = group[group['Result'].apply(is_panel)]
        panel_rounds = len(panel)
        squirrel = 0
        for _, row in panel.iterrows():
            overall = row['Result'].split()[0].strip().lower()
            vote = row['Vote'].strip().lower()
            if vote != overall:
                squirrel += 1
        squirrel_rate = (squirrel / panel_rounds * 100) if panel_rounds > 0 else 0.0

        results.append({
            "JudgeID": judge_id,
            "JudgeName": judge_name,
            "Rounds Judged": total_rounds,
            "Aff Win Rate (%)": round(aff_win_rate, 1),
            "Squirrel Rate (%)": round(squirrel_rate, 1)
        })

    return pd.DataFrame(results)

def compute_metrics_for_team_per_judge(df: pd.DataFrame, team: str) -> pd.DataFrame:
    """
    Computes team-specific metrics for each judge individually.
    
    A round is included if the team (the school name) appears at the start of the entry in either the 'Aff' or 'Neg' column.
    For example, if the team is "Main High School", an entry like "Main High School CT" is included.
    
    For each judge, this function computes:
      - Rounds Judged: Total rounds involving the team with a valid vote.
      - Aff Win Rate (%): Among rounds where the team appears in the 'Aff' column, 
          the percentage where the overall outcome is "aff".
      - Neg Win Rate (%): Among rounds where the team appears in the 'Neg' column, 
          the percentage where the overall outcome is "neg".
      - Squirrel Rate (%): For panel rounds only (Result non-empty with a dash) that involve the team,
          the percentage of rounds where the judge’s vote differs from the overall outcome.
    
    Returns a DataFrame with one row per judge.
    """
    team_lower = team.strip().lower()
    
    def valid_vote(vote):
        return isinstance(vote, str) and vote.strip().lower() in ("aff", "neg")
    
    df_valid = df[df['Vote'].apply(valid_vote)].copy()
    
    filtered = df_valid[
        df_valid['Aff'].str.strip().str.lower().str.startswith(team_lower) |
        df_valid['Neg'].str.strip().str.lower().str.startswith(team_lower)
    ]
    if filtered.empty:
        return pd.DataFrame()
    
    def overall_outcome(row):
        result = row.get("Result", "").strip()
        if result and "-" in result:
            return result.split()[0].strip().lower()
        return row.get("Vote", "").strip().lower()
    
    filtered["Outcome"] = filtered.apply(overall_outcome, axis=1)
    
    groups = filtered.groupby(["JudgeID", "JudgeName"])
    results = []
    
    for (judge_id, judge_name), group in groups:
        total_rounds = len(group)
        
        aff_group = group[group['Aff'].str.strip().str.lower().str.startswith(team_lower)]
        aff_total = len(aff_group)
        aff_wins = aff_group['Outcome'].eq("aff").sum() if aff_total > 0 else 0
        aff_win_rate = (aff_wins / aff_total * 100) if aff_total > 0 else 0.0

        neg_group = group[group['Neg'].str.strip().str.lower().str.startswith(team_lower)]
        neg_total = len(neg_group)
        neg_wins = neg_group['Outcome'].eq("neg").sum() if neg_total > 0 else 0
        neg_win_rate = (neg_wins / neg_total * 100) if neg_total > 0 else 0.0

        def is_panel(result):
            return isinstance(result, str) and result.strip() != "" and "-" in result
        
        panel = group[group["Result"].apply(is_panel)]
        panel_total = len(panel)
        squirrel = 0
        for _, row in panel.iterrows():
            overall = row["Outcome"]
            vote = row["Vote"].strip().lower()
            if vote != overall:
                squirrel += 1
        squirrel_rate = (squirrel / panel_total * 100) if panel_total > 0 else 0.0

        results.append({
            "JudgeID": judge_id,
            "JudgeName": judge_name,
            "Rounds Judged": total_rounds,
            "Aff Win Rate (%)": round(aff_win_rate, 1),
            "Neg Win Rate (%)": round(neg_win_rate, 1),
            "Squirrel Rate (%)": round(squirrel_rate, 1)
        })
    
    return pd.DataFrame(results)