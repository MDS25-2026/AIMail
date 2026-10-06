from app.ml.baseline import build_baseline, evaluate
from app.ml.dataset import stratified_split


def _toy_dataset() -> tuple[list[str], list[str]]:
    high = [
        "please approve this by tomorrow urgent deadline",
        "need your decision now asap urgent",
        "action required respond before friday deadline",
        "urgent please schedule the meeting this week",
        "approval needed immediately to proceed",
        "reply required by end of day urgent",
        "we must decide today action needed",
        "escalation please respond urgently now",
    ]
    low = [
        "monthly company newsletter update",
        "weekly digest for your information",
        "fyi the cafeteria menu changed",
        "notification your subscription renewed",
        "here is the quarterly newsletter roundup",
        "automated receipt no action needed",
        "general announcement for your awareness",
        "informational update nothing required",
    ]
    return high + low, ["HIGH"] * len(high) + ["LOW"] * len(low)


def test_stratified_split_preserves_both_classes():
    texts, labels = _toy_dataset()
    _, _, y_train, y_test = stratified_split(texts, labels, test_size=0.5, seed=0)
    assert set(y_train) == {"HIGH", "LOW"}
    assert set(y_test) == {"HIGH", "LOW"}


def test_baseline_trains_and_scores_a_separable_task():
    texts, labels = _toy_dataset()
    x_train, x_test, y_train, y_test = stratified_split(texts, labels, test_size=0.5, seed=0)
    model = build_baseline()
    model.fit(x_train, y_train)
    metrics = evaluate(model, x_test, y_test)
    assert 0.0 <= metrics["macro_f1"] <= 1.0
    assert set(metrics["labels"]) == {"HIGH", "LOW"}
    assert len(metrics["confusion_matrix"]) == 2
