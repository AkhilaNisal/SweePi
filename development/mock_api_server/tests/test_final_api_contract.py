import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.core.state import robot_state, exploration_state, reset_cleaning_state


class FinalApiContractTest(unittest.TestCase):
    def setUp(self):
        reset_cleaning_state()
        robot_state["state"] = "idle"
        robot_state["mode"] = "automatic"
        robot_state["nav"]["execution_status"] = "IDLE"
        robot_state["map"] = {"map_id": "my_room_map", "name": "My Room"}
        robot_state["exploration"] = {"active": False, "map_name": None, "mode": None}
        exploration_state["active"] = False
        exploration_state["map_name"] = None
        exploration_state["mode"] = None
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/api/system/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status"], "ok")
        self.assertIn("timestamp", body)

    def test_map_shapes(self):
        maps = self.client.get("/api/maps").json()
        self.assertTrue(maps["success"])
        self.assertIn("items", maps)
        first = maps["items"][0]
        self.assertIn("origin", first)
        self.assertIn("sections", first)
        if first["sections"]:
            self.assertIn("bounds", first["sections"][0])

        detail = self.client.get(f"/api/maps/{first['map_id']}").json()
        self.assertIn("occupancy", detail)
        self.assertIn("sections", detail)
        self.assertIn("yaw", detail["origin"])

        metadata = self.client.get(f"/api/maps/{first['map_id']}/metadata").json()
        self.assertIn("origin", metadata)
        self.assertIn("sections", metadata)

    def test_exploration_start_switch_manual_drive_and_stop(self):
        start = self.client.post(
            "/api/exploration/start",
            json={"map_name": "test_room", "mode": "automatic"},
        )
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["map_name"], "test_room")

        switch = self.client.post("/api/exploration/switch", json={"new_mode": "manual"})
        self.assertEqual(switch.status_code, 200)
        self.assertEqual(switch.json()["mode"], "manual")

        drive = self.client.post(
            "/api/exploration/manual-drive",
            json={"command": "left", "speed": 0.2},
        )
        self.assertEqual(drive.status_code, 200)
        self.assertEqual(drive.json()["command"], "left")

        stop = self.client.post("/api/exploration/stop")
        self.assertEqual(stop.status_code, 200)
        self.assertTrue(stop.json()["map_saved"])

    def test_manual_drive_requires_manual_exploration(self):
        response = self.client.post(
            "/api/exploration/manual-drive",
            json={"command": "left", "speed": 0.2},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATE")

    def test_cleaning_validation_errors(self):
        early_pose = self.client.post(
            "/api/cleaning/start",
            json={
                "map_id": "my_room_map",
                "cleaning_mode": "full-map",
                "sections": [],
                "initial_pose": {"x": 0, "y": 0, "yaw": 0, "frame": "map"},
            },
        )
        self.assertEqual(early_pose.status_code, 400)
        self.assertEqual(early_pose.json()["error"]["details"]["field"], "initial_pose")
        self.assertEqual(
            early_pose.json()["error"]["details"]["use_endpoint"],
            "/api/localization/initial-pose",
        )

        missing_sections = self.client.post(
            "/api/cleaning/start",
            json={
                "map_id": "my_room_map",
                "cleaning_mode": "sections",
                "sections": [],
            },
        )
        self.assertEqual(missing_sections.status_code, 400)
        self.assertEqual(missing_sections.json()["error"]["details"]["field"], "sections")

        invalid_mode = self.client.post(
            "/api/cleaning/start",
            json={
                "map_id": "my_room_map",
                "cleaning_mode": "room",
                "sections": [],
            },
        )
        self.assertEqual(invalid_mode.status_code, 400)
        self.assertEqual(invalid_mode.json()["error"]["details"]["field"], "cleaning_mode")

    def test_cleaning_full_map_and_controls(self):
        start = self.client.post(
            "/api/cleaning/start",
            json={
                "map_id": "my_room_map",
                "cleaning_mode": "full-map",
                "sections": [],
            },
        )
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["cleaning_mode"], "full-map")
        self.assertEqual(start.json()["state"], "waiting_for_initial_pose")
        self.assertIsNone(start.json()["initial_pose"])

        pose = self.client.post(
            "/api/localization/initial-pose",
            json={"map_id": "my_room_map", "x": 0, "y": 0, "yaw": 0, "frame": "map"},
        )
        self.assertEqual(pose.status_code, 200)
        self.assertTrue(pose.json()["initial_pose_received"])

        validate = self.client.post("/api/cleaning/validate")
        self.assertEqual(validate.status_code, 200)
        self.assertEqual(validate.json()["state"], "validated")

        motion = self.client.post("/api/cleaning/start-motion")
        self.assertEqual(motion.status_code, 200)
        self.assertEqual(motion.json()["state"], "cleaning")

        status = self.client.get("/api/cleaning/status")
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["active"])

        self.assertEqual(self.client.post("/api/cleaning/pause").status_code, 200)
        self.assertEqual(self.client.post("/api/cleaning/resume").status_code, 200)
        self.assertEqual(self.client.post("/api/cleaning/stop").status_code, 200)
        self.assertEqual(self.client.post("/api/cleaning/reset").status_code, 200)
        self.assertEqual(self.client.post("/api/cleaning/return-home").status_code, 200)

    def test_cleaning_multi_section_success_and_busy_error(self):
        request = {
            "map_id": "my_room_map",
            "cleaning_mode": "sections",
            "sections": [
                {
                    "section_id": "section_1",
                    "name": "Section 1",
                    "bounds": {"x": 1, "y": 1, "width": 1, "height": 1},
                },
                {
                    "section_id": "section_2",
                    "name": "Section 2",
                    "bounds": {"x": 2, "y": 2, "width": 1, "height": 1},
                },
            ],
        }
        start = self.client.post("/api/cleaning/start", json=request)
        self.assertEqual(start.status_code, 200)
        self.assertEqual(len(start.json()["sections"]), 2)

        busy = self.client.post("/api/cleaning/start", json=request)
        self.assertEqual(busy.status_code, 409)
        self.assertEqual(busy.json()["error"]["code"], "ROBOT_BUSY")


if __name__ == "__main__":
    unittest.main()
