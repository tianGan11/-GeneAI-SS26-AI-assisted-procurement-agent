from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.auth import AuthUser
from api.sourcing import (
    SearchRequest,
    _SearchJobState,
    _append_event,
    _format_sse,
    _stream_search_job_events,
    _SEARCH_JOBS,
    create_search_job,
    get_search_job,
    reset_search_jobs_for_tests,
)


class FakeAgent:
    async def search_suppliers(self, query: str, progress=None):
        if progress:
            progress("parse", "已解析采购需求", 25)
            progress("retrieve", "已检索供应商资源", 70)
        return {
            "intent": {"category": "office", "country": "Germany", "keywords": [query]},
            "results": [
                {
                    "id": "supplier-1",
                    "name": "Viking Bürobedarf",
                    "category": "office",
                    "country": "Germany",
                    "matchScore": 88,
                }
            ],
        }


class SourcingJobsTest(unittest.TestCase):
    def setUp(self):
        reset_search_jobs_for_tests()

    def test_search_job_records_real_progress_and_results(self):
        async def scenario():
            request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(agent=FakeAgent())))
            user = AuthUser(
                email="user@fuyao.com",
                name="Fuyao Procurement User",
                company="Fuyao Glass",
                role="Procurement Manager",
            )

            created = await create_search_job(SearchRequest(query="A4 paper Germany"), request, user)
            self.assertEqual(created.status, "queued")
            self.assertEqual(created.progress, 0)
            self.assertEqual(created.results, [])

            # Background task should finish quickly with FakeAgent.
            for _ in range(20):
                current = await get_search_job(created.jobId, user)
                if current.status == "completed":
                    break
                await asyncio.sleep(0.01)

            current = await get_search_job(created.jobId, user)
            self.assertEqual(current.status, "completed")
            self.assertEqual(current.progress, 100)
            self.assertEqual(current.results[0]["name"], "Viking Bürobedarf")
            messages = [event.message for event in current.events]
            self.assertIn("已解析采购需求", messages)
            self.assertIn("已检索供应商资源", messages)
            self.assertIn("候选名单已准备就绪，可以开始查看结果了。", messages)

        asyncio.run(scenario())

    def test_sse_stream_emits_job_and_done_events(self):
        async def scenario():
            job = _SearchJobState(
                jobId="job-sse",
                owner="user@fuyao.com",
                status="completed",
                progress=0,
                step="Queued",
                events=[],
                intent={"category": "office"},
                results=[{"name": "Viking Bürobedarf"}],
                error=None,
            )
            _append_event(job, "completed", "候选名单已准备就绪", 100)
            _SEARCH_JOBS[job.jobId] = job

            chunks = []
            async for chunk in _stream_search_job_events(job.jobId, job.owner):
                chunks.append(chunk)

            payload = "".join(chunks)
            self.assertIn("event: job", payload)
            self.assertIn("event: done", payload)
            self.assertIn("Viking Bürobedarf", payload)
            self.assertIn("候选名单已准备就绪", payload)

        asyncio.run(scenario())

    def test_format_sse_uses_event_stream_shape(self):
        chunk = _format_sse("job", {"status": "running", "message": "正在搜索供应商"})
        self.assertTrue(chunk.startswith("event: job\n"))
        self.assertIn('"status": "running"', chunk)
        self.assertIn("正在搜索供应商", chunk)
        self.assertTrue(chunk.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
