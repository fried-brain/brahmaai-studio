from math import ceil


def preview_staircase(*, floor_to_floor_mm: float, preferred_riser_mm: float,
                      tread_depth_mm: float, clear_width_mm: float,
                      landing_depth_mm: float, configuration: str) -> dict:
    riser_count = max(1, round(floor_to_floor_mm / preferred_riser_mm))
    actual_riser = floor_to_floor_mm / riser_count
    flight_count = 1 if configuration == "straight" else 2
    if flight_count == 1:
        risers_per_flight = [riser_count]
    else:
        first_flight = ceil(riser_count / 2)
        risers_per_flight = [first_flight, riser_count - first_flight]
    going_count = riser_count - flight_count
    max_flight_risers = max(risers_per_flight)
    flight_run = max(0, max_flight_risers - 1) * tread_depth_mm
    comfort_sum = 2 * actual_riser + tread_depth_mm
    notes = ["Conceptual geometry only; verify applicable local rules and site conditions with a qualified professional."]
    if comfort_sum < 550 or comfort_sum > 700:
        notes.append("The 2R+T proportion is outside the 550–700 mm reference band; review riser and tread dimensions.")
    if min(risers_per_flight) < 2 and flight_count == 2:
        notes.append("One flight has fewer than two risers; review whether this split suits the selected floor height.")
    return {
        "configuration": configuration,
        "floor_to_floor_mm": round(floor_to_floor_mm, 3),
        "riser_count": riser_count,
        "actual_riser_mm": round(actual_riser, 3),
        "total_rise_mm": round(actual_riser * riser_count, 3),
        "going_count": going_count,
        "tread_depth_mm": round(tread_depth_mm, 3),
        "flight_count": flight_count,
        "risers_per_flight": risers_per_flight,
        "flight_run_mm": round(flight_run, 3),
        "clear_width_mm": round(clear_width_mm, 3),
        "landing_depth_mm": round(landing_depth_mm, 3),
        "comfort_sum_2r_plus_t_mm": round(comfort_sum, 3),
        "comfort_indicator": "within_reference_band" if 550 <= comfort_sum <= 700 else "outside_reference_band",
        "notes": notes,
        "is_code_certified": False,
    }
