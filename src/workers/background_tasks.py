"""
Background task manager for asynchronous metadata collection.

This module provides a task queue system for processing URL
metadata collection in the background without blocking API responses.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any, Optional

from ..core.config import get_settings
from ..core.logging import logger


class BackgroundTaskManager:
    """
    Manager for background tasks.
    
    Provides a simple, efficient way to run tasks in the background
    without blocking the API response cycle. Uses asyncio for
    cooperative multitasking.
    """
    
    _instance: Optional["BackgroundTaskManager"] = None
    
    def __new__(cls) -> "BackgroundTaskManager":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the task manager."""
        if self._initialized:
            return
        
        settings = get_settings()
        self._max_concurrent_tasks = settings.worker_pool_size
        self._pending_tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(self._max_concurrent_tasks)
        self._shutdown = False
        self._initialized = True
        
        logger.info(
            f"BackgroundTaskManager initialized with "
            f"{self._max_concurrent_tasks} concurrent task limit"
        )
    
    def add_task(
        self,
        coro: Coroutine[Any, Any, Any],
        task_name: Optional[str] = None
    ) -> Optional[asyncio.Task]:
        """
        Add a background task to be executed.
        
        The task will run independently of the calling context
        and will be automatically cleaned up when complete.
        
        Args:
            coro: Coroutine to execute
            task_name: Optional name for the task (for logging)
            
        Returns:
            Created asyncio.Task or None if shutdown
        """
        if self._shutdown:
            logger.warning("Task manager is shutting down, rejecting new task")
            # Close the coroutine to prevent warnings
            coro.close()
            return None
        
        # Create wrapper that handles semaphore and cleanup
        async def task_wrapper() -> None:
            async with self._semaphore:
                try:
                    await coro
                except asyncio.CancelledError:
                    logger.info(f"Task {task_name or 'unnamed'} was cancelled")
                    raise
                except Exception as e:
                    logger.error(
                        f"Background task {task_name or 'unnamed'} failed: {str(e)}"
                    )
        
        # Create and track the task
        task = asyncio.create_task(task_wrapper(), name=task_name)
        self._pending_tasks.add(task)
        
        # Add callback to remove task from tracking set when done
        task.add_done_callback(self._task_done_callback)
        
        logger.debug(
            f"Added background task: {task_name or task.get_name()} "
            f"(pending: {len(self._pending_tasks)})"
        )
        
        return task
    
    def _task_done_callback(self, task: asyncio.Task) -> None:
        """Callback to clean up completed tasks."""
        self._pending_tasks.discard(task)
        
        # Log if task had an exception (that wasn't CancelledError)
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                logger.error(
                    f"Task {task.get_name()} completed with exception: {exc}"
                )
            else:
                logger.debug(f"Task {task.get_name()} completed successfully")
    
    @property
    def pending_count(self) -> int:
        """Get the number of pending tasks."""
        return len(self._pending_tasks)
    
    @property
    def is_shutdown(self) -> bool:
        """Check if the manager is shut down."""
        return self._shutdown
    
    async def shutdown(self, timeout: float = 30.0) -> None:
        """
        Gracefully shut down the task manager.
        
        Waits for pending tasks to complete or cancels them
        after the timeout.
        
        Args:
            timeout: Maximum time to wait for tasks to complete
        """
        self._shutdown = True
        
        if not self._pending_tasks:
            logger.info("No pending tasks to clean up")
            return
        
        logger.info(
            f"Shutting down BackgroundTaskManager "
            f"({len(self._pending_tasks)} pending tasks)"
        )
        
        # Wait for pending tasks with timeout
        pending = list(self._pending_tasks)
        
        try:
            done, pending_remaining = await asyncio.wait(
                pending,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )
            
            # Cancel any remaining tasks
            for task in pending_remaining:
                logger.warning(f"Cancelling task: {task.get_name()}")
                task.cancel()
            
            # Wait for cancellation to complete
            if pending_remaining:
                await asyncio.gather(
                    *pending_remaining,
                    return_exceptions=True
                )
            
            logger.info(
                f"Task manager shutdown complete "
                f"(completed: {len(done)}, cancelled: {len(pending_remaining)})"
            )
            
        except Exception as e:
            logger.error(f"Error during task manager shutdown: {str(e)}")
    
    def reset(self) -> None:
        """
        Reset the task manager (for testing purposes).
        
        Clears all pending tasks and resets shutdown state.
        """
        self._pending_tasks.clear()
        self._shutdown = False
        logger.debug("BackgroundTaskManager reset")


# Global instance
task_manager = BackgroundTaskManager()


def schedule_background_task(
    coro: Coroutine[Any, Any, Any],
    task_name: Optional[str] = None
) -> Optional[asyncio.Task]:
    """
    Convenience function to schedule a background task.
    
    Args:
        coro: Coroutine to execute
        task_name: Optional name for the task
        
    Returns:
        Created asyncio.Task or None
    """
    return task_manager.add_task(coro, task_name)
