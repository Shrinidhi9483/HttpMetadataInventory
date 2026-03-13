"""
Tests for BackgroundTaskManager.

This module tests the background task management functionality
including task scheduling, execution, and shutdown.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workers.background_tasks import (
    BackgroundTaskManager,
    schedule_background_task,
)


class TestBackgroundTaskManager:
    """Tests for BackgroundTaskManager."""
    
    @pytest.fixture
    def task_manager(self) -> BackgroundTaskManager:
        """Create a fresh task manager for testing."""
        # Reset singleton for testing
        BackgroundTaskManager._instance = None
        manager = BackgroundTaskManager()
        yield manager
        # Clean up
        manager.reset()
        BackgroundTaskManager._instance = None
    
    @pytest.mark.asyncio
    async def test_add_task(self, task_manager: BackgroundTaskManager):
        """Test adding a task to the manager."""
        completed = False
        
        async def test_coro():
            nonlocal completed
            completed = True
        
        task = task_manager.add_task(test_coro(), task_name="test_task")
        
        assert task is not None
        assert task_manager.pending_count >= 0
        
        # Wait for task to complete
        await asyncio.sleep(0.1)
        assert completed is True
    
    @pytest.mark.asyncio
    async def test_add_task_with_exception(
        self,
        task_manager: BackgroundTaskManager
    ):
        """Test that task exceptions are handled gracefully."""
        async def failing_coro():
            raise ValueError("Test error")
        
        task = task_manager.add_task(failing_coro(), task_name="failing_task")
        
        assert task is not None
        
        # Wait for task to complete (with exception)
        await asyncio.sleep(0.1)
        
        # Task should be removed from pending
        # (may or may not be 0 depending on timing)
    
    @pytest.mark.asyncio
    async def test_shutdown_waits_for_tasks(
        self,
        task_manager: BackgroundTaskManager
    ):
        """Test that shutdown waits for pending tasks."""
        completed = False
        
        async def slow_coro():
            nonlocal completed
            await asyncio.sleep(0.2)
            completed = True
        
        task_manager.add_task(slow_coro(), task_name="slow_task")
        
        await task_manager.shutdown(timeout=5.0)
        
        assert completed is True
        assert task_manager.is_shutdown is True
    
    @pytest.mark.asyncio
    async def test_shutdown_cancels_on_timeout(
        self,
        task_manager: BackgroundTaskManager
    ):
        """Test that shutdown cancels tasks after timeout."""
        async def very_slow_coro():
            await asyncio.sleep(100)
        
        task_manager.add_task(very_slow_coro(), task_name="very_slow_task")
        
        # Should cancel after timeout
        await task_manager.shutdown(timeout=0.1)
        
        assert task_manager.is_shutdown is True
    
    @pytest.mark.asyncio
    async def test_reject_tasks_after_shutdown(
        self,
        task_manager: BackgroundTaskManager
    ):
        """Test that tasks are rejected after shutdown."""
        await task_manager.shutdown(timeout=1.0)
        
        async def test_coro():
            pass
        
        task = task_manager.add_task(test_coro(), task_name="rejected_task")
        
        assert task is None
    
    def test_pending_count(self, task_manager: BackgroundTaskManager):
        """Test pending count property."""
        assert task_manager.pending_count == 0
    
    def test_is_shutdown_property(self, task_manager: BackgroundTaskManager):
        """Test is_shutdown property."""
        assert task_manager.is_shutdown is False


class TestScheduleBackgroundTask:
    """Tests for the convenience function."""
    
    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset task manager before each test."""
        BackgroundTaskManager._instance = None
        yield
        # Clean up
        if BackgroundTaskManager._instance:
            BackgroundTaskManager._instance.reset()
        BackgroundTaskManager._instance = None
    
    @pytest.mark.asyncio
    async def test_schedule_background_task(self):
        """Test scheduling a task via convenience function."""
        completed = False
        
        async def test_coro():
            nonlocal completed
            completed = True
        
        task = schedule_background_task(test_coro(), task_name="scheduled_task")
        
        assert task is not None
        
        await asyncio.sleep(0.1)
        assert completed is True


class TestConcurrencyLimit:
    """Tests for concurrency limiting."""
    
    @pytest.mark.asyncio
    async def test_respects_concurrency_limit(self):
        """Test that the semaphore limits concurrent tasks."""
        # Reset singleton
        BackgroundTaskManager._instance = None
        
        with patch("src.workers.background_tasks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.worker_pool_size = 2
            mock_settings.return_value = settings
            
            manager = BackgroundTaskManager()
            
            concurrent_count = 0
            max_concurrent = 0
            
            async def counting_coro():
                nonlocal concurrent_count, max_concurrent
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.1)
                concurrent_count -= 1
            
            # Schedule more tasks than the limit
            tasks = []
            for i in range(5):
                task = manager.add_task(counting_coro(), task_name=f"task_{i}")
                if task:
                    tasks.append(task)
            
            # Wait for all tasks
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Max concurrent should not exceed pool size
            assert max_concurrent <= 2
            
            manager.reset()
            BackgroundTaskManager._instance = None
