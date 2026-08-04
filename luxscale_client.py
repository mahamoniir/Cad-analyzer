from urllib.parse import quote

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
    # POST /cad_calc  (N-sided polygon rooms)
    # =====================================================

    @staticmethod
    def normalize_vertices(vertices):
        """Accept [[x,y], ...] or [{"x":..,"y":..}, ...] → [[x,y], ...] in meters."""
        normalized = []
        for raw in vertices or []:
            try:
                if isinstance(raw, dict):
                    x = float(raw["x"])
                    y = float(raw["y"])
                else:
                    x = float(raw[0])
                    y = float(raw[1])
            except (TypeError, ValueError, KeyError, IndexError):
                continue
            normalized.append([round(x, 4), round(y, 4)])

        if len(normalized) < 3:
            raise ValueError(
                "Room polygon must have at least 3 valid vertices (meters)."
            )
        return normalized

    def cad_calc(
        self,
        vertices,
        height,
        place="",
        standard_ref_no=None,
        project_name="CAD Lighting Analysis",
        project_info=None,
        fast=False,
    ):
        """
        Polygon-based lighting calc for arbitrary N-sided rooms.
        Same result shape as /calculate, plus calculation_meta.polygon.
        """
        place = str(place or "").strip()
        if not place and not standard_ref_no:
            raise ValueError(
                "Room type (place) or standard_ref_no is required."
            )

        try:
            height_m = float(height)
        except (TypeError, ValueError) as error:
            raise ValueError("Ceiling height must be a number (meters).") from error

        if height_m <= 0:
            raise ValueError("Ceiling height must be greater than zero.")

        verts = self.normalize_vertices(vertices)

        info = {"project_name": project_name}
        if project_info:
            info.update(project_info)

        payload = {
            "polygon": {"vertices": verts},
            "height": height_m,
            "project_info": info,
            "fast": bool(fast),
        }
        if place:
            payload["place"] = place
        if standard_ref_no:
            payload["standard_ref_no"] = standard_ref_no

        response = requests.post(
            f"{self.base_url}/cad_calc",
            json=payload,
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(response, "/cad_calc")
        return response.json()

    # =====================================================
    # POST /calculate  (legacy 4-side / sides list)
    # =====================================================

    def calculate(
        self,
        sides,
        height,
        place,
        standard_ref_no=None,
        project_name="CAD Lighting Analysis",
        fast=False,
    ):
        """Legacy rectangular / sides-based calculator. Prefer cad_calc()."""
        if not str(place).strip():
            raise ValueError("Room type is required.")

        normalized_sides = []
        for raw_side in sides or []:
            try:
                side = float(raw_side)
            except (TypeError, ValueError):
                continue
            if side > 0.001:
                normalized_sides.append(round(side, 4))

        if len(normalized_sides) < 3:
            raise ValueError(
                "Room must have at least 3 valid side lengths."
            )

        payload = {
            "sides": normalized_sides,
            "height": height,
            "place": place,
            "project_info": {"project_name": project_name},
            "fast": fast,
        }
        if standard_ref_no:
            payload["project_info"]["standard_ref_no"] = standard_ref_no

        response = requests.post(
            f"{self.base_url}/calculate",
            json=payload,
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(response, "/calculate")
        return response.json()

    # =====================================================
    # Standards picker — /api/standards/*
    # Category → task/activity → standard_ref_no for /cad_calc
    # =====================================================

    def get_standards_categories(self):
        response = requests.get(
            f"{self.base_url}/api/standards/categories",
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(
            response, "/api/standards/categories"
        )
        return response.json()

    def get_standards_tasks(self, category):
        category = str(category or "").strip()
        if not category:
            raise ValueError("category is required.")
        encoded = quote(category, safe="")
        response = requests.get(
            f"{self.base_url}/api/standards/categories/{encoded}/tasks",
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(
            response, f"/api/standards/categories/{category}/tasks"
        )
        return response.json()

    def detect_standards(self, text, limit=5):
        text = str(text or "").strip()
        if not text:
            raise ValueError("text is required for standards detect.")
        response = requests.post(
            f"{self.base_url}/api/standards/detect",
            json={"text": text, "limit": int(limit)},
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(
            response, "/api/standards/detect"
        )
        return response.json()

    def resolve_standard_by_task(
        self,
        category,
        task_or_activity,
        ref_no_hint=None,
    ):
        payload = {
            "category": str(category or "").strip(),
            "task_or_activity": str(task_or_activity or "").strip(),
        }
        if ref_no_hint:
            payload["ref_no_hint"] = str(ref_no_hint).strip()
        response = requests.post(
            f"{self.base_url}/api/standards/resolve-by-task",
            json=payload,
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(
            response, "/api/standards/resolve-by-task"
        )
        return response.json()

    def get_standard_by_ref(self, ref_no):
        ref_no = str(ref_no or "").strip()
        if not ref_no:
            raise ValueError("ref_no is required.")
        encoded = quote(ref_no, safe="")
        response = requests.get(
            f"{self.base_url}/api/standards/ref/{encoded}",
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(
            response, f"/api/standards/ref/{ref_no}"
        )
        return response.json()

    # =====================================================
    # POST /standards/resolve  (legacy)
    # =====================================================

    def resolve_standard(self, ref_no):
        response = requests.post(
            f"{self.base_url}/standards/resolve",
            json={"ref_no": ref_no},
            timeout=self.timeout,
        )
        self.raise_for_status_with_details(
            response, "/standards/resolve"
        )
        return response.json()