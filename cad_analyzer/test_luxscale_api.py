from luxscale_client import LuxScaleClient


client = LuxScaleClient(

    "http://127.0.0.1:5000"
)


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

health = client.health_check()

print(
    "API HEALTH:"
)

print(
    health
)


# --------------------------------------------------
# AVAILABLE PLACES
# --------------------------------------------------

places = client.get_places()

print(
    "AVAILABLE PLACES:"
)

print(
    places
)


# --------------------------------------------------
# LIGHTING CALCULATION
# --------------------------------------------------

result = client.calculate(

    sides=[
        10,
        8,
        10,
        8
    ],

    height=3.2,

    place="Office",

    project_info={

        "project_name":
            "CAD API Test",

        "standard_ref_no":
            "5.2.1"
    },

    fast=False
)


print(
    "CALCULATION RESULT:"
)

print(
    result
)