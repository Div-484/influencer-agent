from followup_agent import generate_followup_message


BASE_CONTEXT = {
    "found": True,

    "followup": {
        "followup_id": "test-followup",
        "attempt_number": 2,
        "status": "scheduled",
    },

    "brand": {
        "brand_id": "brand-1",
        "name": "Test Brand",
    },

    "contact": {
        "contact_id": "contact-1",
        "name": "Test Contact",
        "email": "test@example.invalid",
    },

    "previous_outreach": {
        "outreach_id": "outreach-1",
        "message_text": "Original collaboration message.",
        "status": "sent",
    },

    "previous_followups": [],

    "conversation": {
        "conversation_id": "conversation-1",
        "classification": None,
    },

    "messages": [],
}


def make_context(classification):
    context = dict(BASE_CONTEXT)

    context["conversation"] = {
        "conversation_id": "conversation-1",
        "classification": classification,
    }

    return context


# =============================================================
# INTERESTED
# =============================================================

message = generate_followup_message(
    make_context("interested")
)

print("INTERESTED:")
print(message)

assert "Thanks for your interest" in message
assert "next step" in message

print("CASE 1 - INTERESTED RESPONSE: PASS")


# =============================================================
# QUESTION
# =============================================================

message = generate_followup_message(
    make_context("question")
)

print()
print("QUESTION:")
print(message)

assert "Thanks for getting back to me" in message
assert "clarification" in message

print("CASE 2 - QUESTION RESPONSE: PASS")


# =============================================================
# NEGOTIATING
# =============================================================

message = generate_followup_message(
    make_context("negotiating")
)

print()
print("NEGOTIATING:")
print(message)

assert "terms" in message
assert "details" in message

print("CASE 3 - NEGOTIATING RESPONSE: PASS")


# =============================================================
# NOT INTERESTED
# =============================================================

try:
    generate_followup_message(
        make_context("not_interested")
    )

    raise AssertionError(
        "not_interested should not generate a follow-up"
    )

except ValueError as error:
    assert "not_interested" in str(error)

print("CASE 4 - NOT INTERESTED BLOCKED: PASS")


# =============================================================
# NO RESPONSE
# =============================================================

message = generate_followup_message(
    make_context("no_response")
)

print()
print("NO RESPONSE:")
print(message)

assert "Just following up" in message

print("CASE 5 - NO RESPONSE FOLLOW-UP: PASS")


# =============================================================
# UNKNOWN CLASSIFICATION + INBOUND
# =============================================================

context = make_context(None)

context["messages"] = [
    {
        "message_id": "msg-1",
        "direction": "inbound",
        "body": "Can you send more details?",
        "sent_at": None,
    }
]

message = generate_followup_message(
    context
)

print()
print("UNKNOWN + INBOUND:")
print(message)

assert "Thanks for getting back to me" in message

print("CASE 6 - UNKNOWN INBOUND FALLBACK: PASS")


print()
print(
    "PHASE 5.5.5 CLASSIFICATION-AWARE GENERATOR TEST PASSED"
)
