"""Unit tests for slot lease reserve / reclaim / stop release."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from ui_automation import actuator_registry as reg


class _FakeConsumer:
    def __init__(self, actuator_id: str, max_slots: int = 2):
        self.actuator_info = {
            "id": actuator_id,
            "name": actuator_id,
            "max_slots": max_slots,
            "busy_slots": 0,
            "supported_browsers": ["chromium"],
            "default_browser": "chromium",
            "supports_headed": True,
            "supports_headless": True,
            "browser_type": "chromium",
        }


class SlotLeaseTests(SimpleTestCase):
    def setUp(self):
        reg._SLOT_LEASES.clear()
        self.consumers = {
            "a1": _FakeConsumer("a1", max_slots=2),
            "a2": _FakeConsumer("a2", max_slots=1),
        }

        class SM:
            _actuator_users = self.consumers

            @classmethod
            def get_actuator_by_id(cls, actuator_id):
                return cls._actuator_users.get(actuator_id)

        self.sm = SM
        self.patcher = patch.object(reg, "SocketUserManager", self.sm, create=True)
        # actuator_registry imports SocketUserManager inside functions from .consumers
        self.patcher_cons = patch("ui_automation.consumers.SocketUserManager", self.sm)
        self.patcher_cons.start()
        # 强制内存模式：本机若有 Redis 在跑，_leases_view 会把旧 lease 从 Redis 重载回来
        self.patcher_redis = patch("ui_automation.actuator_registry._redis", return_value=None)
        self.patcher_redis.start()

    def tearDown(self):
        self.patcher_redis.stop()
        self.patcher_cons.stop()
        reg._SLOT_LEASES.clear()

    def test_reserve_and_release_adjust(self):
        ok, err = reg.reserve_slots("a1", 1, ttl_seconds=600)
        self.assertTrue(ok, err)
        self.assertEqual(self.consumers["a1"].actuator_info["busy_slots"], 1)
        reg.adjust_busy_slots("a1", -1)
        self.assertEqual(self.consumers["a1"].actuator_info["busy_slots"], 0)
        self.assertEqual(len(reg._SLOT_LEASES), 0)

    def test_expired_lease_reclaimed(self):
        ok, err = reg.reserve_slots("a1", 1, ttl_seconds=600)
        self.assertTrue(ok, err)
        # force expire
        for lease in reg._SLOT_LEASES.values():
            lease["expires_at"] = 0
        reclaimed = reg.reclaim_expired_leases()
        self.assertEqual(reclaimed, 1)
        self.assertEqual(self.consumers["a1"].actuator_info["busy_slots"], 0)

    def test_clear_on_disconnect(self):
        reg.reserve_slots("a1", 2, ttl_seconds=600)
        self.assertEqual(self.consumers["a1"].actuator_info["busy_slots"], 2)
        released = reg.clear_actuator_leases("a1")
        self.assertEqual(released, 2)
        self.assertEqual(self.consumers["a1"].actuator_info["busy_slots"], 0)

    def test_release_all(self):
        reg.reserve_slots("a1", 1, ttl_seconds=600)
        reg.reserve_slots("a2", 1, ttl_seconds=600)
        total = reg.release_all_slots()
        self.assertEqual(total, 2)
        self.assertEqual(self.consumers["a1"].actuator_info["busy_slots"], 0)
        self.assertEqual(self.consumers["a2"].actuator_info["busy_slots"], 0)

    def test_capacity_guard(self):
        ok, _ = reg.reserve_slots("a2", 1, ttl_seconds=600)
        self.assertTrue(ok)
        ok2, err = reg.reserve_slots("a2", 1, ttl_seconds=600)
        self.assertFalse(ok2)
        self.assertIn("slot", err)
