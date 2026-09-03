# Account Age & Transaction History Policy

Account age and transaction frequency together describe how established
a customer relationship is, and both reduce estimated risk as they
increase.

Accounts under 90 days old are considered new and carry elevated risk
regardless of other features, simply because there isn't enough history
to be confident in the signal. New accounts should be reviewed more
conservatively even when the model outputs a low risk score.

Accounts between 90 days and one year are considered established but
still benefit from cross-checking transaction frequency - a customer
with low transaction frequency during this period has a thinner track
record than the account age alone suggests.

Accounts older than one year with consistent transaction history are
treated as the strongest positive signal in this category and can
support approval even when other individual features are borderline.

High average transaction amounts relative to a customer's typical
pattern can indicate either a positive change in circumstances or
early signs of financial distress - a sudden spike should prompt a
closer look rather than an automatic classification either way.
