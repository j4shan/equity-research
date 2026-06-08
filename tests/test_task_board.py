"""Unit tests for the durable task board + lifecycle FSM."""

from research_hub.task_board import MAX_ATTEMPTS, TaskBoard


def fresh() -> tuple[TaskBoard, str]:
    b = TaskBoard(":memory:")
    return b, b.create_run("test")


def test_happy_path_lifecycle():
    b, run = fresh()
    t = b.enqueue_task(run, "NVDA", "fundamentals")
    tid = t["task_id"]
    assert b.claim_task(tid, "w1")["status"] == "claimed"
    assert b.start_task(tid)["status"] == "running"
    done = b.complete_task(tid, "data/fundamentals.json")
    assert done["status"] == "done"
    assert done["result_ref"] == "data/fundamentals.json"
    run_status = b.get_run(run)
    assert run_status["complete"] is True
    assert run_status["counts"]["done"] == 1


def test_illegal_transition_blocked():
    b, run = fresh()
    t = b.enqueue_task(run, "AMD", "technical")
    # cannot complete a task that was never started/claimed
    res = b.complete_task(t["task_id"])
    assert "error" in res


def test_fail_retry_requeues_then_fails():
    b, run = fresh()
    t = b.enqueue_task(run, "AMD", "technical")
    tid = t["task_id"]
    # First failure with retries remaining requeues the task.
    b.claim_task(tid, "w")
    b.start_task(tid)
    requeued = b.fail_task(tid, "AV timeout", retry=True)
    assert requeued["status"] == "queued"
    assert requeued["attempts"] == 1

    # Exhaust the remaining attempts until it lands terminally failed.
    last = requeued
    while last["status"] != "failed":
        b.claim_task(tid, "w")
        b.start_task(tid)
        last = b.fail_task(tid, "AV timeout", retry=True)
    assert last["status"] == "failed"
    assert last["attempts"] >= MAX_ATTEMPTS


def test_next_task_priority_order():
    b, run = fresh()
    b.enqueue_task(run, "A", "fundamentals", priority=9)
    high = b.enqueue_task(run, "B", "fundamentals", priority=1)
    assert b.next_task(run)["task_id"] == high["task_id"]


def test_run_board_counts_and_log():
    b, run = fresh()
    for role in ("fundamentals", "technical", "sentiment", "relationship"):
        b.enqueue_task(run, "NVDA", role)
    board = b.get_run(run)
    assert board["total"] == 4
    assert board["counts"]["queued"] == 4
    assert board["complete"] is False
    log = b.render_run_log(run, "markdown")
    assert "fundamentals" in log and "| task_id |" in log
    html = b.render_run_log(run, "html")
    assert "<table" in html


def test_durability_across_instances(tmp_path):
    db = str(tmp_path / "board.db")
    b1 = TaskBoard(db)
    run = b1.create_run("persist")
    t = b1.enqueue_task(run, "NVDA", "fundamentals")
    b1.close()
    # reopen: queued task should still be there (resumable)
    b2 = TaskBoard(db)
    again = b2.get_task(t["task_id"])
    assert again["status"] == "queued"
    assert again["ticker"] == "NVDA"
