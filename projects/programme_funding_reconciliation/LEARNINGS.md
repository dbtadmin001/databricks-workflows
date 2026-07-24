# Project 8 Delivery Learnings

## Timed benchmark

- A standalone cached runtime container must override the image's Compose-only
  `spark.driver.host=jupyter-spark` setting with `127.0.0.1`. Otherwise Spark fails
  before tests execute even though the candidate code is unaffected.
- Static fixture counts must inform profiling and reconciliation, not become brittle
  notebook assertions. The dynamic invariant is the execution contract.
- Data-quality and compatible-schema failures hold Gold publication and write a
  readable audit decision; they do not crash an otherwise executable MVP pipeline.
- Serverless Bundle resources declare one pinned `environment_version`; combining it
  with `base_environment` is invalid and should be caught before deployment.
- Reusing the immutable Bronze snapshot and one cached-runtime gate kept this change
  independent of Databricks execution until approved merge.
- Dev run `29656727202` proved Terraform and Bundle deployment, then isolated a
  dashboard-only serverless failure: `.unpersist()` is prohibited even when the
  corresponding `.cache()` was already removed. The shared Bundle contract now bans
  both sides of the persistence lifecycle.
