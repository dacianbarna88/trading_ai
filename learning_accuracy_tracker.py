import pandas as pd
from pathlib import Path

FILE = "learning_weight_history.csv"


def update_vote_result(vote_name, outcome):

    if not Path(FILE).exists():
        print("learning_weight_history.csv missing")
        return

    df = pd.read_csv(FILE)

    mask = (
        (df["Vote"] == vote_name) &
        (df["Outcome"] == "PENDING")
    )

    if not mask.any():
        print("No pending record found")
        return

    idx = df[mask].index[-1]

    correct = int(df.loc[idx, "Correct"])
    wrong = int(df.loc[idx, "Wrong"])

    if outcome == "WIN":
        correct += 1

    elif outcome == "LOSS":
        wrong += 1

    total = correct + wrong

    accuracy = 0

    if total > 0:
        accuracy = round(
            correct / total * 100,
            2
        )

    df.loc[idx, "Correct"] = correct
    df.loc[idx, "Wrong"] = wrong
    df.loc[idx, "Total_Scored"] = total
    df.loc[idx, "Accuracy_%"] = accuracy
    df.loc[idx, "Outcome"] = outcome

    df.to_csv(FILE, index=False)

    print(
        vote_name,
        outcome,
        accuracy
    )


if __name__ == "__main__":

    update_vote_result(
        "THRESHOLD",
        "WIN"
    )
