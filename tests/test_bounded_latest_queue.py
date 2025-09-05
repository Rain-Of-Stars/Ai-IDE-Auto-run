# -*- coding: utf-8 -*-
"""
有界最新帧队列测试（unittest版本）

验证：
- 队列长度不超过2；
- put多次后get_latest仅返回最新一帧且清空积压；
- 线程安全基本行为。
"""
import threading
import time
import unittest

from utils.bounded_latest_queue import BoundedLatestQueue


class TestBoundedLatestQueue(unittest.TestCase):
    def test_queue_basic_behavior(self):
        q = BoundedLatestQueue(maxlen=2)

        # 初始为空
        ok, item = q.get_latest()
        self.assertFalse(ok)
        self.assertIsNone(item)

        # 放入1个
        q.put(1)
        ok, item = q.get_latest()
        self.assertTrue(ok)
        self.assertEqual(item, 1)

        # 再次取应为空
        ok, item = q.get_latest()
        self.assertFalse(ok)

    def test_queue_drop_old_and_keep_latest(self):
        q = BoundedLatestQueue(maxlen=2)
        # 放入3个，仅保留最后2个；get_latest仅返回最后一个
        q.put('a')
        q.put('b')
        q.put('c')  # 触发丢弃最旧'a'

        self.assertLessEqual(q.size(), 2)
        ok, item = q.get_latest()
        self.assertTrue(ok)
        self.assertEqual(item, 'c')
        self.assertEqual(q.size(), 0)  # 已清空

    def test_queue_thread_safety_simple(self):
        q = BoundedLatestQueue(maxlen=2)
        stop = False

        def producer():
            i = 0
            while not stop:
                q.put(i)
                i += 1
                time.sleep(0.001)

        t = threading.Thread(target=producer)
        t.start()

        # 消费若干次，确保不抛异常且能拿到最新
        last = -1
        for _ in range(100):
            ok, item = q.get_latest()
            if ok:
                self.assertGreaterEqual(item, last)
                last = item
            time.sleep(0.002)

        stop = True
        t.join(timeout=1)


if __name__ == '__main__':
    unittest.main()
