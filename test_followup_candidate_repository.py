from followup_candidate_repository import get_followup_candidates


print("===== FOLLOW-UP CANDIDATES =====")

result = get_followup_candidates(limit=10)

for row in result:
    print(row)

print()
print("PHASE 5.4.1 CANDIDATE REPOSITORY TEST PASSED")
