# Counterevidence execution gate

`diagnose-conditions` and `generate-gap-candidates` require an approved flight
plan and a local retrieval history containing **every** approved counter query.
A counter search with zero candidates still counts as executed; a planned query
that was never run does not.

This prevents a Research Gap candidate from treating an unexecuted search plan
as counterevidence. It does not establish novelty or scientific validity: each
candidate remains evidence-bound and requires expert review.
