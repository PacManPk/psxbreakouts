import pandas as pd

def open_gt_prev_close(df: pd.DataFrame, days: int = 1) -> pd.DataFrame:
    df = df.sort_values('Date').reset_index(drop=True)
    df['ShiftClose'] = df['Close'].shift(days)
    return df[df['Open'] > df['ShiftClose']]

def volume_increasing(df: pd.DataFrame, window: int = 5) -> bool:
    return df['Volume'].tail(window).is_monotonic_increasing

# Additional filters: PE/EPS (if fundamental data added)
