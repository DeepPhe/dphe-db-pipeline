def get_gender_readable(gender_id):
    """
    Convert an OMOP gender concept ID into a human-readable gender.

    Parameters:
        gender_id (int): The OMOP concept ID representing gender.

    Returns:
        str: A human-readable gender, or 'Unknown' if the ID is not recognized.
    """
    gender_mapping = {
        8507: "M",  # OMOP concept id for male
        8532: "F",  # OMOP concept id for female
        # Optionally add other mappings if available:
        8551: "U"  # Example: OMOP concept id for unknown or unspecified gender
    }

    return gender_mapping.get(gender_id, "U")


def get_race_readable(race_id):
    """
    Convert an OMOP race concept ID into a human-readable race using updated codes.

    Parameters:
        race_id (int): The OMOP concept ID representing race.

    Returns:
        str: A human-readable race, or 'Unknown' if the ID is not recognized.
    """
    race_mapping = {
        8657: "American Indian or Alaska Native",
        38003574: "Asian Indian",
        38003598: "Black",
        38003611: "Micronesian",
        38003579: "Chinese",
        38003610: "Polynesian",
        38003581: "Filipino",
        8557: "Native Hawaiian or Other Pacific Islander",
        38003582: "Hmong",
        38003584: "Japanese",
        38003578: "Cambodian",
        38003585: "Korean",
        38003586: "Laotian",
        38003612: "Melanesian",
        8515: "Asian",
        38003613: "Other Pacific Islander",
        38003589: "Pakistani",
        38003591: "Thai",
        38003592: "Vietnamese",
        8527: "White"
    }

    return race_mapping.get(race_id, "Unknown")


# Example usage:
if __name__ == "__main__":
    sample_race_ids = [
        8657, 38003574, 38003598, 38003611, 38003579, 38003610, 38003581,
        8557, 38003582, 38003584, 38003578, 38003585, 38003586, 38003612,
        0, 8515, 38003613, 38003589, 38003591, 38003592, 8527, 9999
    ]

    for rid in sample_race_ids:
        print(f"Race ID {rid}: {get_race_readable(rid)}")


def get_ethnicity_readable(ethnicity_id):
    """
    Convert an OMOP ethnicity concept ID into a human-readable ethnicity.

    Parameters:
        ethnicity_id (int): The OMOP concept ID representing ethnicity.

    Returns:
        str: A human-readable ethnicity, or 'Unknown' if the ID is not recognized.
    """
    ethnicity_mapping = {
        38003563: "Hispanic or Latino",  # Example OMOP concept id for Hispanic or Latino ethnicity
        38003564: "Not Hispanic or Latino",  # Example OMOP concept id for Not Hispanic or Latino ethnicity
        # Optionally add additional mappings as needed
    }

    return ethnicity_mapping.get(ethnicity_id, "Unknown")

