from typing import Dict, List, Callable
from datetime import datetime, timedelta
import asyncio


class TaskScheduler:
    def __init__(self):
        self.tasks = {}
        self.running = False
        self.task_history = []

    def add_task(self, name: str, func: Callable, interval_hours: int, **kwargs) -> None:
        """Add a scheduled task"""
        self.tasks[name] = {
            "function": func,
            "interval_hours": interval_hours,
            "kwargs": kwargs,
            "last_run": None,
            "next_run": datetime.now(),
            "run_count": 0
        }
        print(f"[Scheduler] Added task: {name} (every {interval_hours}h)")

    async def run_task(self, task_name: str) -> Dict:
        """Run a specific task"""
        if task_name not in self.tasks:
            return {"error": f"Task {task_name} not found"}
        
        task = self.tasks[task_name]
        try:
            if asyncio.iscoroutinefunction(task["function"]):
                result = await task["function"](**task["kwargs"])
            else:
                result = task["function"](**task["kwargs"])
            
            task["last_run"] = datetime.now()
            task["next_run"] = datetime.now() + timedelta(hours=task["interval_hours"])
            task["run_count"] += 1
            
            self.task_history.append({
                "task": task_name,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "result": str(result)[:200]
            })
            
            print(f"[Scheduler] Task {task_name} completed successfully")
            return {"status": "success", "result": result}
            
        except Exception as e:
            self.task_history.append({
                "task": task_name,
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            print(f"[Scheduler] Task {task_name} failed: {e}")
            return {"status": "error", "error": str(e)}

    async def run_pending_tasks(self) -> List[Dict]:
        """Run all tasks that are due"""
        results = []
        now = datetime.now()
        
        for name, task in self.tasks.items():
            if task["next_run"] <= now:
                result = await self.run_task(name)
                results.append({"task": name, **result})
        
        return results

    async def start(self) -> None:
        """Start the scheduler loop"""
        self.running = True
        print("[Scheduler] Started")
        
        while self.running:
            await self.run_pending_tasks()
            await asyncio.sleep(60)  # Check every minute

    def stop(self) -> None:
        """Stop the scheduler"""
        self.running = False
        print("[Scheduler] Stopped")

    def get_status(self) -> Dict:
        """Get scheduler status"""
        return {
            "running": self.running,
            "total_tasks": len(self.tasks),
            "tasks": {
                name: {
                    "interval_hours": task["interval_hours"],
                    "last_run": task["last_run"].isoformat() if task["last_run"] else None,
                    "next_run": task["next_run"].isoformat(),
                    "run_count": task["run_count"]
                }
                for name, task in self.tasks.items()
            },
            "history_count": len(self.task_history)
        }
