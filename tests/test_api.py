from __future__ import annotations

import asyncio
import re
import unittest

import httpx

import server
from tests.test_router import earthquake_context


class ApiBoundaryTests(unittest.TestCase):
    def test_voice_metadata_is_bounded_before_transcription(self):
        with self.assertRaisesRegex(server.HTTPException, "task_id") as raised:
            server._validate_voice_chat_metadata(
                task_id="x" * 101,
                session_id=None,
                previous_question=None,
                previous_response=None,
            )
        self.assertEqual(raised.exception.status_code, 422)

    def test_voice_metadata_is_trimmed_consistently_with_json_chat(self):
        result = server._validate_voice_chat_metadata(
            task_id="  eq_home_6_dch  ",
            session_id="  session-1  ",
            previous_question="  What now?  ",
            previous_response="  Stay under cover.  ",
        )
        self.assertEqual(
            result,
            (
                "eq_home_6_dch",
                "session-1",
                "What now?",
                "Stay under cover.",
            ),
        )

    def test_json_endpoint_uses_structured_context(self):
        payload = server.AssistantRequest(
            question="Should I run outside?",
            locale="taglish-PH",
            context=earthquake_context(learner_heading_to_exit=True),
        )
        result = server.respond(payload)
        self.assertEqual(result["protocol_id"], "EQ-DUR-003")
        self.assertEqual(result["locale"], "taglish-PH")
        self.assertFalse(result["llm_used"])

    def test_asgi_endpoint_end_to_end(self):
        async def exercise():
            transport = httpx.ASGITransport(app=server.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.post(
                    "/api/v1/respond",
                    json={
                        "question": "What should I do?",
                        "locale": "fil-PH",
                        "context": earthquake_context(),
                    },
                )

        response = asyncio.run(exercise())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["protocol_id"], "EQ-DUR-001")
        self.assertEqual(body["locale"], "fil-PH")
        self.assertIn("dashboard_event", body)

    def test_import_does_not_load_speech_model(self):
        self.assertIsNone(server._stt_engine)

    def test_health_discloses_development_and_demo_status(self):
        result = server.health()
        self.assertEqual(
            result["corpus"]["decision"], "INTERNAL_DEVELOPMENT_VALIDATED"
        )
        self.assertFalse(result["corpus"]["runtime_approved"])
        self.assertFalse(result["school_config"]["valid_for_real_emergency"])
        self.assertTrue(result["missions"]["contracts_valid"])
        self.assertIn(
            "school-earthquake-minimal", result["missions"]["mission_ids"]
        )

    def test_mission_contract_is_available_to_unity(self):
        listed = server.list_missions()
        self.assertEqual(len(listed["missions"]), 1)
        mission = server.get_mission("school-earthquake-minimal")
        self.assertEqual(mission["mission_revision"], "1.0.0")
        self.assertIn("EQ-S-A04R", mission["states"])
        self.assertEqual(mission["main_path"][-1], "EQ-S-END")
        verification = mission["verification"]
        self.assertTrue(verification["oracle_generated"])
        self.assertEqual(len(verification["callable_state_order"]), 16)
        protect = verification["states"]["EQ-S-D01"]
        self.assertEqual(
            protect["expected_response_text"]["en-PH"],
            server.assistant.repository.get("EQ-DUR-001")["language_pack"]
            ["en-PH"]["tts_text"],
        )
        self.assertIn("EVACUATE_NOW", protect["expected_blocked_action_codes"])
        hold = verification["states"]["EQ-S-H01-NO-ROUTE"]
        self.assertIsNone(hold["expected_selected_route_id"])
        self.assertIn(
            "no approved open route",
            hold["expected_response_text"]["en-PH"],
        )

    def test_mission_contract_endpoint_is_available_over_asgi(self):
        async def exercise():
            transport = httpx.ASGITransport(app=server.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.get(
                    "/api/v1/missions/school-earthquake-minimal"
                )

        response = asyncio.run(exercise())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mission_revision"], "1.0.0")

    def test_simulation_page_and_assets_are_available(self):
        async def exercise():
            transport = httpx.ASGITransport(app=server.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                page = await client.get("/simulation")
                script = await client.get("/static/js/simulation.js")
                calm_client = await client.get("/static/js/calm-client.js")
                stylesheet = await client.get("/static/css/simulation.css")
                kalma = await client.get("/static/assets/kalma-neutral.png")
                return page, script, calm_client, stylesheet, kalma

        page, script, calm_client, stylesheet, kalma = asyncio.run(exercise())
        self.assertEqual(page.status_code, 200)
        self.assertIn("CALM Classroom Preview", page.text)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(calm_client.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(kalma.status_code, 200)
        self.assertEqual(kalma.headers["content-type"], "image/png")

        # The learner-question widget must exercise the same conversational
        # boundary as Unity. /respond remains the deterministic mission oracle,
        # but it is intentionally not a free-form chat endpoint.
        self.assertIn('fetch("/api/v1/chat"', calm_client.text)
        self.assertIn('fetch("/api/v1/voice-chat"', calm_client.text)
        self.assertNotIn('fetch("/api/process-voice"', calm_client.text)

        mapped_states = set(
            re.findall(r'"(EQ-S-[^"]+)":\s*"eq_sch_', calm_client.text)
        )
        contract = server.assistant.missions.get("school-earthquake-minimal")
        self.assertIsNotNone(contract)
        callable_states = set(
            contract.data["verification"]["callable_state_order"]
        )
        self.assertEqual(mapped_states, callable_states)


if __name__ == "__main__":
    unittest.main()
