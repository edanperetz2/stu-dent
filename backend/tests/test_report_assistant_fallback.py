from app.services.report_assistant import (
    _format_resource_utilization_plainly,
    _format_time_impact_plainly,
    _plain_english_fallback,
)


def test_resource_utilization_plainly_handles_empty_list():
    assert _format_resource_utilization_plainly([]) == (
        "No room or equipment usage was recorded in this period."
    )


def test_resource_utilization_plainly_handles_single_item():
    items = [
        {
            "resource_name": "Room A",
            "resource_type": "room",
            "booked_hours": 4.0,
            "appointment_count": 3,
            "deviation_from_average": 0.0,
        }
    ]
    sentence = _format_resource_utilization_plainly(items)
    assert sentence == (
        "Room A was the only resource used this period, booked for 4.0 hours "
        "across 3 appointments."
    )


def test_resource_utilization_plainly_names_most_and_least_used():
    items = [
        {
            "resource_name": "Room A",
            "resource_type": "room",
            "booked_hours": 10.0,
            "appointment_count": 8,
            "deviation_from_average": 5.0,
        },
        {
            "resource_name": "Room B",
            "resource_type": "room",
            "booked_hours": 1.0,
            "appointment_count": 1,
            "deviation_from_average": -5.0,
        },
    ]
    sentence = _format_resource_utilization_plainly(items)
    assert "Room A was the most-used resource" in sentence
    assert "+5.0 vs. average" in sentence
    assert "Room B saw the least use" in sentence


def test_resource_utilization_plainly_handles_a_tie():
    items = [
        {
            "resource_name": "Room A",
            "resource_type": "room",
            "booked_hours": 0.0,
            "appointment_count": 0,
            "deviation_from_average": 0.0,
        },
        {
            "resource_name": "Room B",
            "resource_type": "room",
            "booked_hours": 0.0,
            "appointment_count": 0,
            "deviation_from_average": 0.0,
        },
    ]
    sentence = _format_resource_utilization_plainly(items)
    assert sentence == "Room and equipment usage was evenly spread across the board this period."


def test_time_impact_plainly_handles_empty_list():
    assert _format_time_impact_plainly([]) == (
        "No no-shows or cancellations were recorded in this period."
    )


def test_time_impact_plainly_names_top_actor_with_no_others():
    items = [
        {
            "actor_name": "Jane Doe",
            "actor_type": "patient",
            "no_show_count": 2,
            "cancelled_count": 1,
            "minutes_lost": 90.0,
        }
    ]
    sentence = _format_time_impact_plainly(items)
    assert sentence == (
        "Jane Doe (patient) accounted for the most lost time: 2 no-shows and "
        "1 cancellations, totaling 90.0 minutes."
    )


def test_time_impact_plainly_mentions_other_affected_people():
    items = [
        {
            "actor_name": "Jane Doe",
            "actor_type": "patient",
            "no_show_count": 2,
            "cancelled_count": 1,
            "minutes_lost": 90.0,
        },
        {
            "actor_name": "John Smith",
            "actor_type": "patient",
            "no_show_count": 0,
            "cancelled_count": 1,
            "minutes_lost": 30.0,
        },
    ]
    sentence = _format_time_impact_plainly(items)
    assert sentence.startswith("Jane Doe (patient) accounted for the most lost time")
    assert "1 other person was also affected" in sentence


def test_plain_english_fallback_combines_both_sections_into_flowing_prose():
    data = {
        "resource_utilization": [
            {
                "resource_name": "Room A",
                "resource_type": "room",
                "booked_hours": 4.0,
                "appointment_count": 3,
                "deviation_from_average": 0.0,
            }
        ],
        "time_impact": [],
    }
    content = _plain_english_fallback(data)
    assert content.startswith("AI narration unavailable -- plain summary of the data: ")
    assert "Room A was the only resource used this period" in content
    assert "No no-shows or cancellations were recorded in this period." in content
    # A flowing summary, not a bullet list.
    assert "\n" not in content
