from src.logistics_dashboard import ShipmentEvent, classify_event


def test_temperature_exception_wins_over_delivery_status():
    event = ShipmentEvent("SHP-7", "cold-2", "in_transit", 11.2, "pod.pdf")
    assert classify_event(event) == "exception"


def test_proof_of_delivery_marks_normal_event_delivered():
    event = ShipmentEvent("SHP-8", "cold-3", "in_transit", 4.5, "pod.pdf")
    assert classify_event(event) == "delivered"
