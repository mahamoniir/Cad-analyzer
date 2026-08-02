import requests


class LuxScaleClient:

    def __init__(
        self,
        base_url="http://127.0.0.1:5000",
        timeout=60
    ):

        self.base_url = base_url.rstrip("/")

        self.timeout = timeout

    @staticmethod
    def raise_for_status_with_details(
        response,
        endpoint
    ):

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            details = response.text.strip()
            if details:
                raise RuntimeError(
                    f"LuxScale API error on {endpoint} "
                    f"({response.status_code}): {details}"
                ) from error
            raise RuntimeError(
                f"LuxScale API error on {endpoint} "
                f"({response.status_code})."
            ) from error

    # =====================================================
    # GET /places
    # =====================================================

    def get_places(self):

        response = requests.get(

            f"{self.base_url}/places",

            timeout=self.timeout
        )

        self.raise_for_status_with_details(
            response,
            "/places"
        )

        return response.json()

    # =====================================================
    # POST /calculate
    # =====================================================

    def calculate(

        self,

        sides,

        height,

        place,

        standard_ref_no=None,

        project_name="CAD Lighting Analysis",

        fast=False
    ):

        if not str(place).strip():
            raise ValueError(
                "Room type is required."
            )

        normalized_sides = []
        for raw_side in sides or []:
            try:
                side = float(raw_side)
            except (
                TypeError,
                ValueError
            ):
                continue
            if side > 0.001:
                normalized_sides.append(
                    round(side, 4)
                )

        if len(normalized_sides) < 3:
            raise ValueError(
                "Room must have at least 3 valid side lengths."
            )

        payload = {

            "sides": normalized_sides,

            "height": height,

            "place": place,

            "project_info": {

                "project_name":
                    project_name
            },

            "fast": fast
        }

        if standard_ref_no:

            payload[

                "project_info"

            ][

                "standard_ref_no"

            ] = standard_ref_no

        response = requests.post(

            f"{self.base_url}/calculate",

            json=payload,

            timeout=self.timeout
        )

        self.raise_for_status_with_details(
            response,
            "/calculate"
        )

        return response.json()

    # =====================================================
    # POST /standards/resolve
    # =====================================================

    def resolve_standard(

        self,

        ref_no
    ):

        response = requests.post(

            f"{self.base_url}/standards/resolve",

            json={

                "ref_no": ref_no
            },

            timeout=self.timeout
        )

        self.raise_for_status_with_details(
            response,
            "/standards/resolve"
        )

        return response.json()