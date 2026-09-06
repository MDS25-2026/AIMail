"""Per-user policy applied on top of the classifier.

The point of the layer is that the model stays untouched — its macro-F1 against the holdout must
remain comparable no matter what a user configures. These pin the precedence order and the
guarantee that an unconfigured user sees exactly today's behaviour.
"""

from app.db.models import Message
from app.personalisation import DEFAULT_POLICY, Policy, apply_policy


def _message(**kwargs) -> Message:
    defaults = {"from_addr": "Someone <someone@corp.com>", "subject": "", "body_masked": "", "importance": 1}
    return Message(**{**defaults, "id": None, **kwargs})


def test_an_unconfigured_user_sees_the_models_prediction_unchanged():
    for importance, expected in ((0, "low"), (1, "medium"), (2, "high")):
        assert apply_policy(_message(importance=importance), DEFAULT_POLICY) == expected


def test_an_unscored_message_still_falls_back_to_medium():
    # Bias must not manufacture a priority the classifier never produced.
    policy = Policy(priority_bias=1)
    assert apply_policy(_message(importance=None), policy) == "medium"


def test_bias_shifts_the_prediction_one_step():
    assert apply_policy(_message(importance=1), Policy(priority_bias=1)) == "high"
    assert apply_policy(_message(importance=1), Policy(priority_bias=-1)) == "low"


def test_bias_cannot_push_past_the_ends_of_the_scale():
    assert apply_policy(_message(importance=2), Policy(priority_bias=1)) == "high"
    assert apply_policy(_message(importance=0), Policy(priority_bias=-1)) == "low"


def test_a_sender_rule_beats_the_model_and_the_bias():
    policy = Policy(priority_bias=-1, sender_rules={"someone@corp.com": 2})
    assert apply_policy(_message(importance=0), policy) == "high"


def test_a_sender_rule_matches_inside_a_full_from_header():
    # Real headers are "Name <addr>", so equality on the whole field would never fire.
    policy = Policy(sender_rules={"boss@corp.com": 2})
    assert apply_policy(_message(from_addr="The Boss <boss@corp.com>", importance=0), policy) == "high"


def test_a_keyword_rule_matches_subject_or_body():
    policy = Policy(keyword_rules={"project alpha": 2})
    assert apply_policy(_message(subject="Re: Project Alpha timeline", importance=0), policy) == "high"
    assert apply_policy(_message(body_masked="notes on project alpha", importance=0), policy) == "high"


def test_a_keyword_rule_can_demote_as_well_as_promote():
    policy = Policy(keyword_rules={"newsletter": 0})
    assert apply_policy(_message(subject="Weekly newsletter", importance=2), policy) == "low"


def test_a_sender_rule_wins_over_a_keyword_rule():
    # Most specific first: who sent it beats what it mentions.
    policy = Policy(sender_rules={"someone@corp.com": 0}, keyword_rules={"urgent": 2})
    assert apply_policy(_message(subject="urgent", importance=1), policy) == "low"
