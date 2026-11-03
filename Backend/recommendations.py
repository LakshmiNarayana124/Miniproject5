
"""
INTELLIWATCH - RECOMMENDATION ENGINE
Version: 1.0

Purpose:
1. Generate recommendations for vibration, temperature and current.
2. Calculate independent confidence for each sensor recommendation.
3. Calculate separate overall system recommendation confidence.
4. Generate goal-based recommendations across all confidence ranges.
5. Vary wording without changing the underlying meaning.

Important:
- Recommendations are not confirmed diagnoses.
- This module does not modify engine classifications.
- Confidence values are preliminary heuristic estimates.
- Safety-critical findings must follow established equipment procedures.
"""

import random
from datetime import datetime


# ============================================================
# 1. SENSOR CONFIGURATION
# ============================================================

SENSORS = {
    "vibration": "Vibration",
    "temperature": "Temperature",
    "current": "Electrical Current",
}


# ============================================================
# 2. CONFIDENCE LEVELS
# ============================================================

CONFIDENCE_LEVELS = [
    (0, 29, "VERY_LOW"),
    (30, 49, "LOW"),
    (50, 69, "MODERATE"),
    (70, 79, "GOOD"),
    (80, 89, "HIGH"),
    (90, 100, "VERY_HIGH"),
]


def get_confidence_level(confidence):

    confidence = max(0, min(100, round(confidence)))

    for minimum, maximum, level in CONFIDENCE_LEVELS:
        if minimum <= confidence <= maximum:
            return level

    return "VERY_LOW"


# ============================================================
# 3. GOAL-BASED WORDING VARIATIONS
# ============================================================

WORDING = {

    "observe": [
        "Continue observing the current behaviour.",
        "Keep monitoring the readings for further changes.",
        "Maintain regular observation of the current pattern.",
        "Continue collecting evidence before making adjustments.",
    ],

    "optimize": [
        "Review operating conditions for possible improvements.",
        "Look for opportunities to improve operating stability.",
        "Check whether the present setup can be optimized.",
        "Evaluate whether the current operating arrangement can be improved.",
    ],

    "investigate": [
        "Investigate possible reasons behind the observed deviation.",
        "Examine operating conditions that may contribute to the change.",
        "Review factors that could explain the unusual behaviour.",
        "Study the observed pattern before selecting corrective measures.",
    ],

    "reduce": [
        "Take suitable steps to reduce the observed deviation.",
        "Explore corrective measures that may bring readings closer to the expected range.",
        "Apply appropriate adjustments to help reduce abnormal behaviour.",
        "Consider suitable measures to minimize the observed variation.",
    ],

    "relief": [
        "Take an appropriate immediate relief measure according to the equipment procedure.",
        "Apply a suitable short-term measure to reduce the immediate concern.",
        "Follow the prescribed procedure to minimize the current abnormal condition.",
        "Prioritize an appropriate immediate response based on established safety requirements.",
    ],

    "correct": [
        "Identify and correct the verified underlying issue.",
        "Address the confirmed source of the abnormal behaviour.",
        "Carry out suitable corrective maintenance after inspection.",
        "Resolve the verified contributing factor and reassess the readings.",
    ],
}


def varied_wording(goal):
    """Select different wording while preserving the recommendation goal."""

    return random.choice(WORDING[goal])


# ============================================================
# 4. SENSOR-SPECIFIC GUIDANCE
# ============================================================

SENSOR_GUIDANCE = {

    "vibration": {

        "observation": {
            "NORMAL": "Vibration behaviour is within the recognized normal pattern.",
            "WARNING": "Unusual vibration behaviour has been detected.",
            "CRITICAL": "A significant vibration deviation has been detected.",
            "UNKNOWN": "The current vibration behaviour is not sufficiently understood.",
            "UNDER_OBSERVATION": "Vibration behaviour requires further observation.",
        },

        "possible_causes": [
            "Changes in operating conditions",
            "Loose mounting or external vibration influence",
            "Changes in mechanical behaviour",
        ],

        "optimization": [
            "Review equipment mounting and surrounding conditions.",
            "Maintain a consistent vibration baseline.",
            "Observe vibration trends under different operating conditions.",
        ],

        "reduction": [
            "Inspect mounting points and mechanical connections.",
            "Compare readings across multiple observation cycles.",
            "Review recent changes in equipment operation.",
        ],

        "relief": [
            "Where permitted, reduce operating load or vibration exposure.",
            "Follow established safety procedures if a critical vibration limit is reached.",
        ],

        "correction": [
            "Inspect mounting, alignment and mechanical connections.",
            "Correct the verified source of the vibration change.",
            "Recheck vibration behaviour after corrective maintenance.",
        ],
    },

    "temperature": {

        "observation": {
            "NORMAL": "Temperature behaviour is within the recognized normal pattern.",
            "WARNING": "An unusual temperature change has been detected.",
            "CRITICAL": "A significant temperature deviation has been detected.",
            "UNKNOWN": "The current temperature behaviour is not sufficiently understood.",
            "UNDER_OBSERVATION": "Temperature behaviour requires further observation.",
        },

        "possible_causes": [
            "Changes in operating load",
            "Environmental temperature variation",
            "Insufficient cooling or ventilation",
        ],

        "optimization": [
            "Review ventilation and surrounding environmental conditions.",
            "Maintain a consistent temperature baseline.",
            "Observe temperature changes under different operating conditions.",
        ],

        "reduction": [
            "Inspect ventilation and cooling arrangements.",
            "Review recent changes in operating conditions.",
            "Monitor whether temperature continues increasing.",
        ],

        "relief": [
            "Where permitted, reduce heat generation or operating load.",
            "Follow established safety procedures if a critical temperature limit is reached.",
        ],

        "correction": [
            "Inspect the cooling and ventilation arrangements.",
            "Correct the verified source of excess heating.",
            "Verify temperature behaviour after corrective maintenance.",
        ],
    },

    "current": {

        "observation": {
            "NORMAL": "Electrical current behaviour is within the recognized normal pattern.",
            "WARNING": "An unusual electrical current change has been detected.",
            "CRITICAL": "A significant electrical current deviation has been detected.",
            "UNKNOWN": "The current electrical behaviour is not sufficiently understood.",
            "UNDER_OBSERVATION": "Electrical current behaviour requires further observation.",
        },

        "possible_causes": [
            "Changes in electrical load",
            "Variation in supply conditions",
            "Changes in connected equipment behaviour",
        ],

        "optimization": [
            "Review changes in connected electrical loads.",
            "Maintain a consistent electrical operating baseline.",
            "Observe current trends under different operating conditions.",
        ],

        "reduction": [
            "Review connected loads and recent operating changes.",
            "Arrange inspection of electrical connections by qualified personnel.",
            "Monitor current behaviour over subsequent observation cycles.",
        ],

        "relief": [
            "If an established electrical safety limit is exceeded, follow the prescribed isolation procedure.",
            "Avoid handling exposed electrical connections or equipment.",
        ],

        "correction": [
            "Arrange inspection of the electrical supply and connected loads by qualified personnel.",
            "Correct any verified electrical connection or load-related issue.",
            "Recheck current behaviour after corrective work.",
        ],
    },
}


# ============================================================
# 5. SENSOR STATUS AND EXPLANATION
# ============================================================

def get_sensor_status(sensor_data):

    if isinstance(sensor_data, dict):
        return str(sensor_data.get("status", "UNKNOWN")).upper()

    if isinstance(sensor_data, str):
        return sensor_data.upper()

    return "UNKNOWN"


def get_sensor_explanation(sensor_data):

    if isinstance(sensor_data, dict):

        return (
            sensor_data.get("explanation")
            or sensor_data.get("reasoning")
            or "No additional explanation available."
        )

    return "No additional explanation available."


# ============================================================
# 6. SENSOR CONFIDENCE ESTIMATION
# ============================================================

def calculate_sensor_confidence(sensor_data):
    """
    Preliminary heuristic evidence-strength estimate.

    This is not a statistically calibrated probability.
    """

    if not isinstance(sensor_data, dict):
        return 0

    status = get_sensor_status(sensor_data)

    base_scores = {
        "NORMAL": 65,
        "UNKNOWN": 20,
        "UNDER_OBSERVATION": 35,
        "WARNING": 70,
        "CRITICAL": 80,
    }

    confidence = base_scores.get(status, 0)

    explanation = get_sensor_explanation(sensor_data)

    if explanation != "No additional explanation available.":
        confidence += 5

    classification = sensor_data.get("classification")

    if classification in ("NORMAL", "ABNORMAL"):
        confidence += 5

    quality = str(sensor_data.get("quality", "")).upper()

    if quality in ("BAD", "ERROR", "INVALID", "POOR"):
        confidence -= 30

    return max(0, min(100, confidence))


# ============================================================
# 7. GOAL SELECTION
# ============================================================

def select_recommendation_goal(confidence):

    if confidence <= 29:
        return "OBSERVATION_AND_OPTIMIZATION"

    elif confidence <= 49:
        return "PREVENTIVE_OPTIMIZATION"

    elif confidence <= 69:
        return "POSSIBILITY_INVESTIGATION_AND_REDUCTION"

    elif confidence <= 79:
        return "FOCUSED_REDUCTION"

    elif confidence <= 89:
        return "IMMEDIATE_RELIEF_AND_CORRECTION"

    return "HIGH_PRIORITY_RELIEF_AND_CORRECTION"


# ============================================================
# 8. SENSOR RECOMMENDATION GENERATION
# ============================================================

def generate_sensor_recommendation(sensor_key, sensor_data):

    if sensor_key not in SENSOR_GUIDANCE:
        return None

    guidance = SENSOR_GUIDANCE[sensor_key]

    status = get_sensor_status(sensor_data)
    confidence = calculate_sensor_confidence(sensor_data)

    level = get_confidence_level(confidence)
    goal = select_recommendation_goal(confidence)

    result = {

        "sensor": SENSORS[sensor_key],

        "status": status,

        "confidence": confidence,

        "confidence_level": level,

        "goal": goal,

        "observation": guidance["observation"].get(
            status,
            "Sensor behaviour requires further observation."
        ),

        "engine_explanation": get_sensor_explanation(sensor_data),

        "possible_causes": [],

        "recommended_actions": [],

        "immediate_relief_actions": [],

        "corrective_actions": [],

        "priority": "NORMAL",
    }

    # --------------------------------------------------------
    # 0-29: VERY LOW
    # Observation and general optimization
    # --------------------------------------------------------

    if confidence <= 29:

        result["recommended_actions"] = [
            varied_wording("observe"),
            varied_wording("optimize"),
        ]

        result["recommended_actions"].extend(
            guidance["optimization"]
        )

        result["priority"] = "LOW"

    # --------------------------------------------------------
    # 30-49: LOW
    # Preventive optimization
    # --------------------------------------------------------

    elif confidence <= 49:

        result["recommended_actions"] = [
            varied_wording("observe"),
            varied_wording("optimize"),
            "Continue collecting reliable sensor readings.",
        ]

        result["recommended_actions"].extend(
            guidance["optimization"]
        )

        result["priority"] = "LOW"

    # --------------------------------------------------------
    # 50-69: MODERATE
    # Investigate possibilities and reduce deviations
    # --------------------------------------------------------

    elif confidence <= 69:

        result["possible_causes"] = guidance["possible_causes"]

        result["recommended_actions"] = [
            varied_wording("investigate"),
            varied_wording("reduce"),
        ]

        result["recommended_actions"].extend(
            guidance["reduction"]
        )

        result["priority"] = "MODERATE"

    # --------------------------------------------------------
    # 70-79: GOOD
    # Focused reduction
    # --------------------------------------------------------

    elif confidence <= 79:

        result["possible_causes"] = guidance["possible_causes"]

        result["recommended_actions"] = [
            varied_wording("reduce"),
        ]

        result["recommended_actions"].extend(
            guidance["reduction"]
        )

        result["priority"] = "HIGH"

    # --------------------------------------------------------
    # 80-89: HIGH
    # Immediate relief and corrective actions
    # --------------------------------------------------------

    elif confidence <= 89:

        result["possible_causes"] = guidance["possible_causes"]

        result["immediate_relief_actions"] = guidance["relief"]

        result["corrective_actions"] = [
            varied_wording("correct")
        ]

        result["corrective_actions"].extend(
            guidance["correction"]
        )

        result["priority"] = "HIGH"

    # --------------------------------------------------------
    # 90-100: VERY HIGH
    # Higher-priority relief and correction
    # --------------------------------------------------------

    else:

        result["possible_causes"] = guidance["possible_causes"]

        result["immediate_relief_actions"] = [
            varied_wording("relief")
        ]

        result["immediate_relief_actions"].extend(
            guidance["relief"]
        )

        result["corrective_actions"] = [
            varied_wording("correct")
        ]

        result["corrective_actions"].extend(
            guidance["correction"]
        )

        result["priority"] = "VERY_HIGH"

    return result


# ============================================================
# 9. OVERALL SYSTEM CONFIDENCE
# ============================================================

def calculate_overall_confidence(sensor_recommendations):
    """
    Independently estimates confidence in the overall
    system recommendation.

    It does not blindly average sensor confidence scores.

    Factors:
    - Strongest sensor evidence.
    - Agreement between abnormal sensor findings.
    - Conflicting normal findings.
    - Unknown or unavailable sensor evidence.
    - Sensor coverage.
    """

    valid = [
        item
        for item in sensor_recommendations.values()
        if item is not None
    ]

    if not valid:
        return 0

    scores = [
        item["confidence"]
        for item in valid
    ]

    strongest_score = max(scores)

    abnormal_count = sum(
        1 for item in valid
        if item["status"] in ("WARNING", "CRITICAL")
    )

    normal_count = sum(
        1 for item in valid
        if item["status"] == "NORMAL"
    )

    unknown_count = sum(
        1 for item in valid
        if item["status"] in ("UNKNOWN", "UNDER_OBSERVATION")
    )

    confidence = strongest_score

    # Corroborating abnormal findings
    if abnormal_count >= 2:
        confidence += min(10, (abnormal_count - 1) * 5)

    # Conflicting normal findings
    if abnormal_count > 0 and normal_count > 0:
        confidence -= min(15, normal_count * 5)

    # Unknown sensor findings
    if unknown_count > 0:
        confidence -= min(15, unknown_count * 5)

    # Incomplete sensor coverage
    if len(valid) < 3:
        confidence -= 10

    return max(0, min(100, round(confidence)))


# ============================================================
# 10. OVERALL SYSTEM RECOMMENDATION
# ============================================================

def generate_overall_recommendation(sensor_recommendations):

    valid = [
        item
        for item in sensor_recommendations.values()
        if item is not None
    ]

    statuses = [
        item["status"]
        for item in valid
    ]

    confidence = calculate_overall_confidence(
        sensor_recommendations
    )

    level = get_confidence_level(confidence)

    goal = select_recommendation_goal(confidence)

    critical_count = statuses.count("CRITICAL")
    warning_count = statuses.count("WARNING")
    normal_count = statuses.count("NORMAL")

    if critical_count > 0:
        overall_status = "CRITICAL"

    elif warning_count > 0:
        overall_status = "WARNING"

    elif normal_count == 3:
        overall_status = "NORMAL"

    else:
        overall_status = "UNDER_OBSERVATION"

    result = {

        "sensor": "Overall System",

        "status": overall_status,

        "confidence": confidence,

        "confidence_level": level,

        "goal": goal,

        "observation": "",

        "possible_causes": [],

        "recommended_actions": [],

        "immediate_relief_actions": [],

        "corrective_actions": [],

        "priority": "NORMAL",
    }

    # Overall observation
    if overall_status == "NORMAL":

        result["observation"] = (
            "All three sensor findings currently indicate normal behaviour."
        )

    elif overall_status == "CRITICAL":

        result["observation"] = (
            "One or more sensors have reported critical behaviour."
        )

    elif overall_status == "WARNING":

        result["observation"] = (
            "One or more sensors have reported unusual behaviour."
        )

    else:

        result["observation"] = (
            "Overall system behaviour requires further observation."
        )

    # --------------------------------------------------------
    # 0-49: Observation and optimization
    # --------------------------------------------------------

    if confidence <= 49:

        result["recommended_actions"] = [
            varied_wording("observe"),
            varied_wording("optimize"),
            "Continue collecting reliable readings from all available sensors.",
        ]

        result["priority"] = "LOW"

    # --------------------------------------------------------
    # 50-69: Investigation and reduction
    # --------------------------------------------------------

    elif confidence <= 69:

        result["recommended_actions"] = [
            varied_wording("investigate"),
            varied_wording("reduce"),
            "Compare the behaviour of all three sensor parameters.",
        ]

        result["possible_causes"] = [
            "Changes in operating conditions",
            "Environmental or external influences",
            "Changes in equipment behaviour",
        ]

        result["priority"] = "MODERATE"

    # --------------------------------------------------------
    # 70-79: Focused reduction
    # --------------------------------------------------------

    elif confidence <= 79:

        result["recommended_actions"] = [
            varied_wording("reduce"),
            "Review the sensor findings together before making adjustments.",
            "Monitor the effect of any approved operating changes.",
        ]

        result["possible_causes"] = [
            "One or more operating conditions may contribute to the deviation.",
            "Multiple sensor changes may be related or independent.",
        ]

        result["priority"] = "HIGH"

    # --------------------------------------------------------
    # 80-89: Relief and correction
    # --------------------------------------------------------

    elif confidence <= 89:

        result["immediate_relief_actions"] = [
            varied_wording("relief"),
            "Review affected sensor findings and follow applicable safety procedures.",
        ]

        result["corrective_actions"] = [
            varied_wording("correct"),
            "Inspect contributing sensor parameters and verify the source of deviation.",
        ]

        result["priority"] = "HIGH"

    # --------------------------------------------------------
    # 90-100: High-priority relief and correction
    # --------------------------------------------------------

    else:

        result["immediate_relief_actions"] = [
            varied_wording("relief"),
            "Prioritize the affected equipment according to established safety procedures.",
        ]

        result["corrective_actions"] = [
            varied_wording("correct"),
            "Investigate contributing sensor findings and verify the underlying issue.",
            "Reassess all sensor readings after corrective work.",
        ]

        result["priority"] = "VERY_HIGH"

    return result


# ============================================================
# 11. MAIN PUBLIC FUNCTION
# ============================================================

def generate_recommendations(
    sensor_statuses,
    overall_system_status=None
):
    """
    Main function called by the IntelliWatch engine or API.

    Expected input:

    {
        "Vibration": {
            "status": "WARNING",
            "classification": "ABNORMAL",
            "explanation": "Warning limit exceeded."
        },

        "Temperature": {
            "status": "NORMAL",
            "classification": "NORMAL",
            "explanation": "Within recognized range."
        },

        "Current": {
            "status": "CRITICAL",
            "classification": "ABNORMAL",
            "explanation": "Critical deviation detected."
        }
    }

    Returns separate sensor and overall recommendations.
    """

    if not isinstance(sensor_statuses, dict):
        raise TypeError("sensor_statuses must be a dictionary.")

    recommendations = {}

    for sensor_key, display_name in SENSORS.items():

        sensor_data = (
            sensor_statuses.get(sensor_key)
            or sensor_statuses.get(display_name)
        )

        if sensor_data is None:

            recommendations[sensor_key] = None

            continue

        recommendations[sensor_key] = (
            generate_sensor_recommendation(
                sensor_key,
                sensor_data
            )
        )

    overall_recommendation = generate_overall_recommendation(
        recommendations
    )

    return {

        "generated_at": datetime.now().isoformat(),

        "sensor_recommendations": recommendations,

        "overall_recommendation": overall_recommendation,

        "disclaimer": (
            "Recommendations are evidence-based suggestions, "
            "not confirmed equipment diagnoses. Confidence values "
            "are preliminary heuristic estimates and require "
            "validation using real equipment data."
        ),
    }


# ============================================================
# 12. STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    sample_sensor_statuses = {

        "Vibration": {
            "status": "WARNING",
            "classification": "ABNORMAL",
            "explanation": "Configured warning operating limit exceeded.",
        },

        "Temperature": {
            "status": "NORMAL",
            "classification": "NORMAL",
            "explanation": "Temperature is within the recognized range.",
        },

        "Current": {
            "status": "CRITICAL",
            "classification": "ABNORMAL",
            "explanation": "Significant current deviation detected.",
        },
    }

    output = generate_recommendations(
        sample_sensor_statuses
    )

    print("\n========== INTELLIWATCH RECOMMENDATIONS ==========\n")

    for sensor_key, recommendation in output[
        "sensor_recommendations"
    ].items():

        if recommendation is None:
            continue

        print(f"\n{recommendation['sensor']}")
        print("-" * 55)

        print("Status:", recommendation["status"])

        print(
            "Confidence:",
            recommendation["confidence"],
            "%"
        )

        print("Confidence Level:", recommendation["confidence_level"])

        print("Goal:", recommendation["goal"])

        print("Observation:", recommendation["observation"])

        print("Possible Causes:", recommendation["possible_causes"])

        print("Recommended Actions:", recommendation["recommended_actions"])

        print("Immediate Relief:", recommendation["immediate_relief_actions"])

        print("Corrective Actions:", recommendation["corrective_actions"])

        print("Priority:", recommendation["priority"])

    overall = output["overall_recommendation"]

    print("\n========== OVERALL SYSTEM ==========\n")

    print("Status:", overall["status"])

    print("Confidence:", overall["confidence"], "%")

    print("Confidence Level:", overall["confidence_level"])

    print("Goal:", overall["goal"])

    print("Observation:", overall["observation"])

    print("Priority:", overall["priority"])

    print("Recommended Actions:", overall["recommended_actions"])

    print("Immediate Relief:", overall["immediate_relief_actions"])

    print("Corrective Actions:", overall["corrective_actions"])

    print("\n", output["disclaimer"])
