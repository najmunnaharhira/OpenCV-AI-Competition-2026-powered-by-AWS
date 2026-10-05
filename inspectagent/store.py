"""Trace and approval storage: local files by default, S3 + DynamoDB (+ SNS) on AWS.

Env vars (set by deploy/template.yaml):
  TRACE_BUCKET     S3 bucket for traces and evidence images
  APPROVALS_TABLE  DynamoDB table holding human-approval requests
  APPROVALS_TOPIC  optional SNS topic notified on each new request
  LOCAL_STORE      directory used when TRACE_BUCKET is unset (default ./runs)
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal

BUCKET = os.environ.get("TRACE_BUCKET")
TABLE = os.environ.get("APPROVALS_TABLE")
TOPIC = os.environ.get("APPROVALS_TOPIC")
LOCAL = os.environ.get("LOCAL_STORE", "runs")


def _aws(service):
    import boto3
    return boto3.client(service) if service != "dynamodb" else boto3.resource("dynamodb").Table(TABLE)


def save_session(s) -> dict:
    record = {"session_id": s.session_id, "part_id": s.part.part_id, "outcome": s.outcome,
              "trace": s.trace, "created_at": int(time.time())}
    body = json.dumps(record, default=str).encode()
    if BUCKET:
        s3 = _aws("s3")
        s3.put_object(Bucket=BUCKET, Key=f"traces/{s.session_id}.json", Body=body,
                      ContentType="application/json")
        for name, data in s.artifacts.items():
            s3.put_object(Bucket=BUCKET, Key=f"evidence/{s.session_id}/{name}", Body=data,
                          ContentType="image/jpeg")
    else:
        d = os.path.join(LOCAL, s.session_id)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "trace.json"), "wb") as f:
            f.write(body)
        for name, data in s.artifacts.items():
            with open(os.path.join(d, name), "wb") as f:
                f.write(data)
    if s.outcome.get("decision") == "human_review":
        _put_approval({"session_id": s.session_id, "part_id": s.part.part_id, "status": "pending",
                       "proposed_action": s.outcome.get("proposed_action"),
                       "rationale": s.outcome.get("rationale"), "created_at": int(time.time())})
    return record


def _put_approval(item: dict) -> None:
    if TABLE:
        _aws("dynamodb").put_item(Item=json.loads(json.dumps(item), parse_float=Decimal))
        if TOPIC:
            _aws("sns").publish(TopicArn=TOPIC, Subject="Inspection approval needed",
                                Message=json.dumps(item))
    else:
        path = os.path.join(LOCAL, "approvals.json")
        items = _local_approvals()
        items[item["session_id"]] = item
        os.makedirs(LOCAL, exist_ok=True)
        with open(path, "w") as f:
            json.dump(items, f, indent=2)


def _local_approvals() -> dict:
    try:
        with open(os.path.join(LOCAL, "approvals.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def list_approvals(status: str = "pending") -> list[dict]:
    if TABLE:
        items = _aws("dynamodb").scan()["Items"]
    else:
        items = list(_local_approvals().values())
    return sorted((i for i in items if i["status"] == status), key=lambda i: -int(i["created_at"]))


def resolve_approval(session_id: str, approved: bool, reviewer: str) -> dict:
    status = "approved" if approved else "declined"
    if TABLE:
        return _aws("dynamodb").update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET #s = :s, reviewer = :r, resolved_at = :t",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status, ":r": reviewer, ":t": int(time.time())},
            ReturnValues="ALL_NEW")["Attributes"]
    items = _local_approvals()
    items[session_id].update(status=status, reviewer=reviewer, resolved_at=int(time.time()))
    with open(os.path.join(LOCAL, "approvals.json"), "w") as f:
        json.dump(items, f, indent=2)
    return items[session_id]
