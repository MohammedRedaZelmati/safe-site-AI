import sys
from pathlib import Path
import unittest

from fastapi.testclient import TestClient
from PIL import Image
import tempfile


sys.path.insert(0, str(Path(__file__).parents[1]))

from app.graph import GroundedAgent
from app.main import create_app
from app.query_catalog import plan_question, validate_plan


class FakeDatabase:
    def __init__(self):
        self.calls = []

    async def execute(self, sql, parameters):
        self.calls.append((sql, parameters))
        if "COUNT(*)" in sql and "WHERE camera_id" not in sql:
            return [{"total": 5}]
        return []

    async def open(self):
        return None

    async def close(self):
        return None

    async def health(self):
        return {"current_user": "safesite_agent", "transaction_read_only": "on"}


class FakeOllama:
    async def answer(self, question, sql, rows):
        return f"Grounded from {len(rows)} SQL rows."

    async def available_models(self):
        return ["llama3.2:latest", "qwen2.5vl:3b"]

    async def describe_image(self, image_path):
        return f"Visible PPE evidence from {image_path.name}."


class GroundedAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_total_question_runs_approved_select(self):
        database = FakeDatabase()
        agent = GroundedAgent(database.execute, FakeOllama().answer)
        result = await agent.ask("How many violations are there?")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["plan"].intent, "total_violations")
        self.assertTrue(result["plan"].sql.startswith("SELECT"))
        self.assertEqual(result["answer_provider"], "ollama")
        self.assertEqual(len(database.calls), 1)

    async def test_write_request_is_rejected_before_database(self):
        database = FakeDatabase()
        agent = GroundedAgent(database.execute)
        result = await agent.ask("Delete every violation")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(database.calls, [])

    async def test_unknown_question_is_rejected(self):
        database = FakeDatabase()
        agent = GroundedAgent(database.execute)
        result = await agent.ask("What color is the sky?")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(database.calls, [])

    async def test_model_failure_uses_deterministic_answer(self):
        class BrokenOllama:
            async def answer(self, question, sql, rows):
                raise RuntimeError("offline")

        database = FakeDatabase()
        agent = GroundedAgent(database.execute, BrokenOllama().answer)
        result = await agent.ask("What is the total number of violations?")
        self.assertEqual(result["answer_provider"], "deterministic")
        self.assertIn("5", result["answer"])

    def test_every_planned_query_passes_catalog_validation(self):
        for question in (
            "How many violations are there?",
            "Show violations by type",
            "Show violations by camera",
            "Show the latest 5 violations",
            "How many violations for camera-01?",
            "What is the most common violation?",
        ):
            plan = plan_question(question)
            self.assertIsNotNone(plan)
            validate_plan(plan)

    def test_http_api_exposes_grounded_sql_and_rejects_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            application = create_app(FakeDatabase(), FakeOllama(), Path(temporary))
            with TestClient(application) as client:
                accepted = client.post("/ask", json={"question": "How many violations are there?"})
                rejected = client.post("/ask", json={"question": "Delete every violation"})
            self.assertEqual(accepted.status_code, 200)
            self.assertTrue(accepted.json()["sql"].startswith("SELECT"))
            self.assertEqual(accepted.json()["answer_provider"], "ollama")
            self.assertEqual(rejected.status_code, 422)

    def test_vision_endpoint_restricts_paths_to_data_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_path = root / "evidence.png"
            Image.new("RGB", (8, 8), "white").save(image_path)
            application = create_app(FakeDatabase(), FakeOllama(), root)
            with TestClient(application) as client:
                accepted = client.post("/vision/describe", json={"image_path": "evidence.png"})
                rejected = client.post("/vision/describe", json={"image_path": str(Path(__file__).resolve())})
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.json()["status"], "described")
            self.assertEqual(rejected.status_code, 403)


if __name__ == "__main__":
    unittest.main()
