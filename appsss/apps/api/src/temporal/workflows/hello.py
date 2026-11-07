from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.hello import hello_activity


@workflow.defn
class HelloWorkflow:
    # job_id is optional: the internal smoke-test route starts this with
    # no arguments. It used to be required, so that route's workflow
    # task failed on every attempt and the HTTP request hung forever.
    @workflow.run
    async def run(self, job_id: str | None = None) -> dict[str, str]:
        return await workflow.execute_activity(
            hello_activity,
            job_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
