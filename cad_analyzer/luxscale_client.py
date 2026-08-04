import requests


class LuxScaleClient:

    def __init__(

        self,

        base_url="http://127.0.0.1:5000",

        timeout=60
    ):

        self.base_url = (

            base_url.rstrip("/")
        )

        self.timeout = timeout

    def get_places(self):

        response = requests.get(

            f"{self.base_url}/places",

            timeout=self.timeout
        )

        response.raise_for_status()

        return response.json()

    def cad_calc(
        self,
        vertices,
        height,
        place="",
        standard_ref_no=None,
        project_name="CAD Lighting Analysis",
        fast=False,
    ):
        """Delegate to the root LuxScaleClient — prefer importing that module."""
        from luxscale_client import LuxScaleClient as RootClient

        return RootClient(self.base_url, timeout=self.timeout).cad_calc(
            vertices=vertices,
            height=height,
            place=place,
            standard_ref_no=standard_ref_no,
            project_name=project_name,
            fast=fast,
        )

    def calculate(

        self,

        sides,

        height,

        place,

        standard_ref_no=None,

        project_name="CAD Lighting Analysis",

        fast=False
    ):

        payload = {

            "sides": sides,

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

        response.raise_for_status()

        return response.json()