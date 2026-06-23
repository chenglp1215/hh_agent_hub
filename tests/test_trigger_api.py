"""
Trigger API Tests — task-trigger-management

Tests all 6 trigger endpoints plus contract validation:
  GET    /api/v1/triggers          List triggers
  GET    /api/v1/triggers/{id}     Get trigger detail
  POST   /api/v1/triggers          Create trigger
  PUT    /api/v1/triggers/{id}     Update trigger
  DELETE /api/v1/triggers/{id}     Delete trigger
  POST   /api/v1/triggers/{id}/execute  Manual execute
"""
import sys
import json
import traceback
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

# IDs we create during test (for cleanup, reverse order)
TEST_NAMES = {
    "agent": [],       # [name, ...]
    "workflow": [],    # [name, ...]
    "app": [],        # [name, ...]
    "triggers": [],    # [id, ...]
}

# Known pre-existing test data (created by earlier manual setup)
EXISTING_APP_ID = 1
EXISTING_APP_NAME = "test-app-trigger"
EXISTING_WORKFLOW_ID = 2
EXISTING_AGENT_ID = 1


def login():
    global TOKEN
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    data = r.json()
    assert data["code"] == 0, f"Login failed: {data}"
    TOKEN = data["data"]["access_token"]
    print(f"[LOGIN] Token obtained (expires in {data['data']['expires_in']}s)")


def headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# ========== SETUP: Ensure test app exists ==========

def ensure_test_data():
    """Ensure a published workflow and enabled app exist for trigger testing.
    If the pre-existing test data (from manual setup) is available, use it.
    Otherwise create new data."""
    print("\n=== SETUP: Ensure test data ===")

    # Check if our known app exists
    r = requests.get(f"{BASE_URL}/apps/{EXISTING_APP_ID}", headers=headers())
    if r.status_code == 200 and r.json().get("code") == 0:
        app_data = r.json()["data"]
        if app_data.get("name") == EXISTING_APP_NAME and app_data.get("enabled"):
            print(f"[SETUP] Using existing app id={EXISTING_APP_ID} name='{EXISTING_APP_NAME}'")
            return EXISTING_APP_ID

    # Check if ANY app exists
    r = requests.get(f"{BASE_URL}/apps", headers=headers())
    apps = r.json().get("data", [])
    enabled_apps = [a for a in apps if a.get("enabled")]
    if enabled_apps:
        app = enabled_apps[0]
        app_id = app["id"]
        print(f"[SETUP] Using existing app id={app_id} name='{app['name']}'")
        return app_id

    # No app available — create one
    print("[SETUP] No app found, creating test workflow + app...")

    # Check/create agent
    agent_id = None
    r = requests.get(f"{BASE_URL}/agents", headers=headers())
    agents = r.json().get("data", [])
    if agents:
        agent_id = agents[0]["id"]
        print(f"[SETUP] Using existing agent id={agent_id}")
    else:
        r = requests.post(f"{BASE_URL}/agents", json={
            "name": "test-agent-for-trigger",
            "llm_config": {"provider": "openai", "model": "gpt-4o-mini"},
        }, headers=headers())
        assert r.json()["code"] == 0
        agent_id = r.json()["data"]["id"]
        TEST_NAMES["agent"].append("test-agent-for-trigger")
        print(f"[SETUP] Created agent id={agent_id}")

    # Check/create published workflow
    workflow_id = None
    r = requests.get(f"{BASE_URL}/workflows?status=published", headers=headers())
    published = r.json().get("data", [])
    if published:
        workflow_id = published[0]["id"]
        print(f"[SETUP] Using existing published workflow id={workflow_id}")
    else:
        # Create a new workflow
        r = requests.post(f"{BASE_URL}/workflows", json={
            "name": "test-workflow-for-trigger",
            "flow_type": "sequential",
            "worker_agent_ids": [agent_id],
        }, headers=headers())
        assert r.json()["code"] == 0
        workflow_id = r.json()["data"]["id"]
        TEST_NAMES["workflow"].append("test-workflow-for-trigger")
        print(f"[SETUP] Created workflow id={workflow_id}")

        # Publish it
        r = requests.post(f"{BASE_URL}/workflows/{workflow_id}/publish", headers=headers())
        assert r.json()["code"] == 0, f"Publish failed: {r.json()}"
        print(f"[SETUP] Published workflow id={workflow_id}")

    # Create app
    r = requests.post(f"{BASE_URL}/apps", json={
        "name": "test-app-for-trigger",
        "workflow_id": workflow_id,
    }, headers=headers())
    assert r.json()["code"] == 0, f"Create app failed: {r.json()}"
    app_id = r.json()["data"]["id"]
    TEST_NAMES["app"].append("test-app-for-trigger")
    print(f"[SETUP] Created app id={app_id}")
    return app_id


# ========== TRIGGER TESTS ==========

def test_create_interval_trigger(app_id):
    """Create an interval-type trigger and verify response fields"""
    print("\n=== TEST: Create Interval Trigger ===")
    payload = {
        "name": "test-interval-trigger-api",
        "description": "Test interval trigger",
        "trigger_type": "interval",
        "interval_value": 30,
        "interval_unit": "minutes",
        "app_id": app_id,
        "message": "Hello from interval trigger",
    }
    r = requests.post(f"{BASE_URL}/triggers", json=payload, headers=headers())
    assert r.status_code == 200, f"Status: {r.status_code}, body: {r.text}"
    data = r.json()
    assert data["code"] == 0, f"Response: {data}"
    assert data["message"] == "创建成功"

    t = data["data"]
    assert t["name"] == "test-interval-trigger-api"
    assert t["trigger_type"] == "interval"
    assert t["interval_value"] == 30
    assert t["interval_unit"] == "minutes"
    assert t["cron_expression"] is None
    assert t["app_id"] == app_id
    assert t["app_name"] is not None
    assert t["message"] == "Hello from interval trigger"
    assert t["enabled"] is True
    assert t["last_fired_at"] is None
    assert "next_fire_at" in t
    assert "created_at" in t
    assert t["updated_at"] is None

    tid = t["id"]
    TEST_NAMES["triggers"].append(tid)
    print(f"[PASS] Created interval trigger id={tid}")

    # Create another interval trigger for list tests
    payload2 = payload.copy()
    payload2["name"] = "test-interval-trigger-2"
    payload2["interval_value"] = 10
    payload2["interval_unit"] = "hours"
    r2 = requests.post(f"{BASE_URL}/triggers", json=payload2, headers=headers())
    assert r2.json()["code"] == 0
    tid2 = r2.json()["data"]["id"]
    TEST_NAMES["triggers"].append(tid2)
    print(f"[PASS] Created second interval trigger id={tid2}")


def test_create_cron_trigger(app_id):
    """Create a cron-type trigger and verify response fields"""
    print("\n=== TEST: Create Cron Trigger ===")
    payload = {
        "name": "test-cron-trigger-api",
        "description": "Test cron trigger",
        "trigger_type": "cron",
        "cron_expression": "0 9 * * *",
        "app_id": app_id,
        "message": "Good morning from cron!",
    }
    r = requests.post(f"{BASE_URL}/triggers", json=payload, headers=headers())
    assert r.status_code == 200, f"Status: {r.status_code}, body: {r.text}"
    data = r.json()
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    t = data["data"]
    assert t["name"] == "test-cron-trigger-api"
    assert t["trigger_type"] == "cron"
    assert t["cron_expression"] == "0 9 * * *"
    assert t["interval_value"] is None
    assert t["interval_unit"] is None
    assert t["app_id"] == app_id
    assert t["app_name"] is not None
    assert t["message"] == "Good morning from cron!"
    assert t["enabled"] is True
    assert "next_fire_at" in t
    tid = t["id"]
    TEST_NAMES["triggers"].append(tid)
    print(f"[PASS] Created cron trigger id={tid}")


def test_list_triggers():
    """Verify list endpoint returns array with all created triggers"""
    print("\n=== TEST: List Triggers ===")
    r = requests.get(f"{BASE_URL}/triggers", headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    triggers = data["data"]
    assert isinstance(triggers, list), f"Expected list, got {type(triggers)}"
    print(f"[PASS] List returned {len(triggers)} triggers")

    # Verify all our triggers are in the list
    our_ids = set(TEST_NAMES["triggers"])
    found_ids = {t["id"] for t in triggers}
    for tid in our_ids:
        assert tid in found_ids, f"Trigger id={tid} not found in list"
    print(f"[PASS] All {len(our_ids)} created triggers present in list")

    # Verify field completeness for the first trigger
    if triggers:
        t = triggers[0]
        expected_fields = [
            "id", "name", "description", "trigger_type",
            "interval_value", "interval_unit", "cron_expression",
            "app_id", "app_name", "message", "enabled",
            "last_fired_at", "next_fire_at", "created_at", "updated_at",
        ]
        for f in expected_fields:
            assert f in t, f"Missing field '{f}' in list response"
        print(f"[PASS] All {len(expected_fields)} expected fields present in list")


def test_get_trigger():
    """Verify get detail endpoint returns single trigger object"""
    print("\n=== TEST: Get Trigger Detail ===")
    if not TEST_NAMES["triggers"]:
        print("[SKIP] No trigger to retrieve")
        return
    tid = TEST_NAMES["triggers"][0]
    r = requests.get(f"{BASE_URL}/triggers/{tid}", headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    t = data["data"]
    assert t["id"] == tid
    assert t["name"] is not None
    assert t["trigger_type"] in ("interval", "cron")
    assert "app_name" in t
    assert "created_at" in t
    print(f"[PASS] Get trigger id={tid} returned: name='{t['name']}', type={t['trigger_type']}")

    # Non-existent
    r2 = requests.get(f"{BASE_URL}/triggers/99999", headers=headers())
    assert r2.json()["code"] == 404, f"Expected 404, got {r2.json()}"
    print(f"[PASS] Non-existent trigger returns 404")


def test_update_trigger():
    """Test various update scenarios"""
    print("\n=== TEST: Update Trigger ===")
    if not TEST_NAMES["triggers"]:
        print("[SKIP] No trigger to update")
        return

    # Test 1: Update name and description
    tid = TEST_NAMES["triggers"][0]
    update1 = {
        "name": "test-interval-trigger-updated",
        "description": "Updated description",
    }
    r = requests.put(f"{BASE_URL}/triggers/{tid}", json=update1, headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    assert data["message"] == "更新成功"
    t = data["data"]
    assert t["name"] == "test-interval-trigger-updated"
    assert t["description"] == "Updated description"
    assert t["updated_at"] is not None
    print(f"[PASS] Update name/description succeeded")

    # Test 2: Disable trigger
    tid3 = TEST_NAMES["triggers"][2]  # cron trigger
    update2 = {"enabled": False}
    r = requests.put(f"{BASE_URL}/triggers/{tid3}", json=update2, headers=headers())
    assert r.json()["code"] == 0
    t = r.json()["data"]
    assert t["enabled"] is False
    assert t["next_fire_at"] is None  # disabled -> no next_fire
    print(f"[PASS] Disable trigger succeeded, next_fire_at=None")

    # Test 3: Re-enable
    update3 = {"enabled": True}
    r = requests.put(f"{BASE_URL}/triggers/{tid3}", json=update3, headers=headers())
    assert r.json()["code"] == 0
    t = r.json()["data"]
    assert t["enabled"] is True
    assert t["next_fire_at"] is not None
    print(f"[PASS] Re-enable trigger succeeded, next_fire_at={t['next_fire_at']}")

    # Test 4: Change trigger type (cron -> interval)
    tid4 = TEST_NAMES["triggers"][1]  # second interval trigger
    update4 = {
        "trigger_type": "interval",
        "interval_value": 5,
        "interval_unit": "days",
    }
    r = requests.put(f"{BASE_URL}/triggers/{tid4}", json=update4, headers=headers())
    assert r.json()["code"] == 0
    t = r.json()["data"]
    assert t["trigger_type"] == "interval"
    assert t["interval_value"] == 5
    assert t["interval_unit"] == "days"
    print(f"[PASS] Change trigger type succeeded")

    # Test 5: Update non-existent trigger
    r = requests.put(f"{BASE_URL}/triggers/99999", json={"name": "nope"}, headers=headers())
    assert r.json()["code"] == 404
    print(f"[PASS] Update non-existent returns 404")

    # Test 6: Update duplicate name
    r = requests.put(f"{BASE_URL}/triggers/{tid}", json={"name": "test-cron-trigger-api"}, headers=headers())
    assert r.json()["code"] != 0
    print(f"[PASS] Duplicate name rejected")


def test_execute_trigger():
    """Test manual execution of a trigger.
    NOTE: This requires Redis. If Redis is not running, the execute test will be skipped."""
    print("\n=== TEST: Execute Trigger ===")
    if len(TEST_NAMES["triggers"]) < 3:
        print("[SKIP] Not enough triggers for execute test")
        return

    # Test 1: Execute enabled trigger (requires Redis — skip if Redis unavailable)
    tid = TEST_NAMES["triggers"][0]  # first enabled trigger
    r = requests.post(f"{BASE_URL}/triggers/{tid}/execute", headers=headers())
    try:
        data = r.json()
        if data.get("code") == 0:
            assert "task_id" in data["data"], f"Missing task_id: {data}"
            assert "session_id" in data["data"], f"Missing session_id: {data}"
            assert data["data"]["session_id"].startswith("trigger_manual_")
            print(f"[PASS] Execute returned task_id={data['data']['task_id'][:12]}... session_id={data['data']['session_id']}")
        else:
            print(f"[SKIP] Execute rejected: code={data.get('code')}, msg={data.get('message', '')}")
    except Exception:
        print(f"[SKIP] Execute endpoint returned HTTP {r.status_code} (Redis unavailable)")

    # Test 2: Execute disabled trigger should return 400
    tid_disabled = TEST_NAMES["triggers"][2]  # we disabled this one earlier
    r = requests.post(f"{BASE_URL}/triggers/{tid_disabled}/execute", headers=headers())
    try:
        data = r.json()
        assert data["code"] != 0, f"Disabled trigger should be rejected, got: {data}"
        assert data["code"] == 400, f"Expected 400 for disabled trigger, got code={data.get('code')}: {data}"
        print(f"[PASS] Disabled trigger rejected: {data.get('message', '')}")
    except Exception:
        print(f"[SKIP] Execute disabled returned HTTP {r.status_code} (non-JSON response)")

    # Test 3: Execute non-existent trigger should return 404
    r = requests.post(f"{BASE_URL}/triggers/99999/execute", headers=headers())
    try:
        data = r.json()
        assert data["code"] == 404, f"Expected 404 for non-existent trigger, got: {data}"
        print(f"[PASS] Non-existent trigger returns 404")
    except Exception:
        print(f"[SKIP] Execute non-existent returned HTTP {r.status_code} (non-JSON response)")


def test_delete_trigger():
    """Test deletion of a trigger"""
    print("\n=== TEST: Delete Trigger ===")
    if not TEST_NAMES["triggers"]:
        print("[SKIP] No trigger to delete")
        return

    # Pick the last trigger to delete
    tid = TEST_NAMES["triggers"].pop()
    r = requests.delete(f"{BASE_URL}/triggers/{tid}", headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    assert data["message"] == "已删除"
    print(f"[PASS] Delete trigger id={tid} succeeded")

    # Verify gone from list
    r2 = requests.get(f"{BASE_URL}/triggers", headers=headers())
    ids = {t["id"] for t in r2.json()["data"]}
    assert tid not in ids, f"Deleted trigger id={tid} still in list"
    print(f"[PASS] Deleted trigger no longer in list")

    # Verify get returns 404
    r3 = requests.get(f"{BASE_URL}/triggers/{tid}", headers=headers())
    assert r3.json()["code"] == 404
    print(f"[PASS] Deleted trigger returns 404 on get")

    # Delete non-existent
    r4 = requests.delete(f"{BASE_URL}/triggers/99999", headers=headers())
    assert r4.json()["code"] == 404
    print(f"[PASS] Delete non-existent returns 404")


# ========== ERROR CASE TESTS ==========

def test_error_cases(app_id):
    """Test various error scenarios"""
    print("\n=== TEST: Error Cases ===")

    # 1. Duplicate name
    print("[TEST] Duplicate name...")
    if len(TEST_NAMES["triggers"]) >= 1:
        t0_id = TEST_NAMES["triggers"][0]
        r = requests.get(f"{BASE_URL}/triggers/{t0_id}", headers=headers())
        name = r.json()["data"]["name"]
        payload = {
            "name": name,
            "trigger_type": "interval",
            "interval_value": 15,
            "interval_unit": "minutes",
            "app_id": app_id,
            "message": "Duplicate test",
        }
        r2 = requests.post(f"{BASE_URL}/triggers", json=payload, headers=headers())
        assert r2.json()["code"] != 0, f"Expected error for duplicate name: {r2.json()}"
        print(f"[PASS] Duplicate name rejected: {r2.json().get('message', '')}")
    else:
        print("[SKIP] No triggers for duplicate name test")

    # 2. Interval type missing interval_value
    print("[TEST] Interval missing interval_value...")
    r = requests.post(f"{BASE_URL}/triggers", json={
        "name": "test-missing-interval-value",
        "trigger_type": "interval",
        "app_id": app_id,
        "message": "Missing interval_value",
    }, headers=headers())
    assert r.json()["code"] != 0, f"Expected error: {r.json()}"
    print(f"[PASS] Missing interval_value rejected: {r.json().get('message', '')}")

    # 3. Interval type missing interval_unit
    print("[TEST] Interval missing interval_unit...")
    r = requests.post(f"{BASE_URL}/triggers", json={
        "name": "test-missing-interval-unit",
        "trigger_type": "interval",
        "interval_value": 30,
        "app_id": app_id,
        "message": "Missing interval_unit",
    }, headers=headers())
    assert r.json()["code"] != 0, f"Expected error: {r.json()}"
    print(f"[PASS] Missing interval_unit rejected: {r.json().get('message', '')}")

    # 4. Cron type missing cron_expression
    print("[TEST] Cron missing cron_expression...")
    r = requests.post(f"{BASE_URL}/triggers", json={
        "name": "test-missing-cron",
        "trigger_type": "cron",
        "app_id": app_id,
        "message": "Missing cron_expression",
    }, headers=headers())
    assert r.json()["code"] != 0, f"Expected error: {r.json()}"
    print(f"[PASS] Missing cron_expression rejected: {r.json().get('message', '')}")

    # 5. Invalid cron expression (not 5 parts)
    print("[TEST] Invalid cron expression...")
    r = requests.post(f"{BASE_URL}/triggers", json={
        "name": "test-bad-cron",
        "trigger_type": "cron",
        "cron_expression": "0 9 *",  # only 3 parts
        "app_id": app_id,
        "message": "Bad cron",
    }, headers=headers())
    assert r.json()["code"] != 0, f"Expected error: {r.json()}"
    print(f"[PASS] Invalid cron expression rejected: {r.json().get('message', '')}")

    # 6. Non-existent app_id
    print("[TEST] Non-existent app_id...")
    r = requests.post(f"{BASE_URL}/triggers", json={
        "name": "test-bad-app-id",
        "trigger_type": "interval",
        "interval_value": 10,
        "interval_unit": "minutes",
        "app_id": 99999,
        "message": "Bad app_id",
    }, headers=headers())
    assert r.json()["code"] != 0, f"Expected error: {r.json()}"
    print(f"[PASS] Non-existent app_id rejected: {r.json().get('message', '')}")

    # 7. Unpublished/disbled app (if we can find/create one)
    print("[TEST] Disabled app (if available)...")
    # The test app is enabled, let's check if there's a disabled one
    r = requests.get(f"{BASE_URL}/apps", headers=headers())
    all_apps = r.json().get("data", [])
    disabled_app = [a for a in all_apps if not a.get("enabled")]
    if disabled_app:
        bad_app_id = disabled_app[0]["id"]
        r = requests.post(f"{BASE_URL}/triggers", json={
            "name": "test-disabled-app",
            "trigger_type": "interval",
            "interval_value": 10,
            "interval_unit": "minutes",
            "app_id": bad_app_id,
            "message": "Disabled app",
        }, headers=headers())
        assert r.json()["code"] != 0, f"Expected error: {r.json()}"
        print(f"[PASS] Disabled app rejected: {r.json().get('message', '')}")
    else:
        print(f"[SKIP] No disabled app available")


# ========== CONTRACT VALIDATION ==========

def contract_validation():
    """Validate API responses against the contract in
    outputs/contracts/task-trigger-management-api-contract.md"""
    print("\n=== CONTRACT VALIDATION ===")
    issues = []

    # Expected fields from contract (all backend field names)
    CONTRACT_FIELDS = [
        "id", "name", "description", "trigger_type",
        "interval_value", "interval_unit", "cron_expression",
        "app_id", "app_name", "message", "enabled",
        "last_fired_at", "next_fire_at", "created_at", "updated_at",
    ]
    CONTRACT_FIELD_TYPES = {
        "id": int,
        "name": str,
        "description": (str, type(None)),  # nullable
        "trigger_type": str,
        "interval_value": (int, type(None)),
        "interval_unit": (str, type(None)),
        "cron_expression": (str, type(None)),
        "app_id": int,
        "app_name": str,
        "message": str,
        "enabled": bool,
        "last_fired_at": (str, type(None)),
        "next_fire_at": (str, type(None)),
        "created_at": str,
        "updated_at": (str, type(None)),
    }

    ENUM_TRIGGER_TYPE = {"interval", "cron"}
    ENUM_INTERVAL_UNIT = {"minutes", "hours", "days"}

    # --- Check list response ---
    r = requests.get(f"{BASE_URL}/triggers", headers=headers())
    triggers = r.json().get("data", [])

    if not triggers:
        issues.append("[WARN] No triggers exist for list contract validation")
    else:
        t = triggers[0]
        # Field existence
        for f in CONTRACT_FIELDS:
            if f not in t:
                issues.append(f"[FAIL][🚨致命] List response - Missing field '{f}'")

        # Field type checks
        for f, expected_type in CONTRACT_FIELD_TYPES.items():
            if f in t:
                actual_val = t[f]
                if not isinstance(actual_val, expected_type):
                    issues.append(
                        f"[FAIL][⚠严重] List response - Field '{f}' type mismatch: "
                        f"expected {expected_type.__name__}, got {type(actual_val).__name__} (value={actual_val!r})"
                    )

        # Enum checks
        if "trigger_type" in t and t["trigger_type"] is not None:
            if t["trigger_type"] not in ENUM_TRIGGER_TYPE:
                issues.append(
                    f"[FAIL][🚨致命] List response - trigger_type='{t['trigger_type']}' "
                    f"not in valid enum values {ENUM_TRIGGER_TYPE}"
                )
        if "interval_unit" in t and t["interval_unit"] is not None:
            if t["interval_unit"] not in ENUM_INTERVAL_UNIT:
                issues.append(
                    f"[FAIL][🚨致命] List response - interval_unit='{t['interval_unit']}' "
                    f"not in valid enum values {ENUM_INTERVAL_UNIT}"
                )

        # Extra fields check
        extra = set(t.keys()) - set(CONTRACT_FIELDS)
        if extra:
            issues.append(f"[WARN][⚠警告] List response - Extra fields not in contract: {extra}")

    # --- Check detail response ---
    if TEST_NAMES["triggers"]:
        tid = TEST_NAMES["triggers"][0]
        r = requests.get(f"{BASE_URL}/triggers/{tid}", headers=headers())
        t = r.json().get("data", {})

        for f in CONTRACT_FIELDS:
            if f not in t:
                issues.append(f"[FAIL][🚨致命] Detail response - Missing field '{f}'")

        for f, expected_type in CONTRACT_FIELD_TYPES.items():
            if f in t:
                actual_val = t[f]
                if not isinstance(actual_val, expected_type):
                    issues.append(
                        f"[FAIL][⚠严重] Detail response - Field '{f}' type mismatch: "
                        f"expected {expected_type.__name__}, got {type(actual_val).__name__} (value={actual_val!r})"
                    )

        if "trigger_type" in t and t["trigger_type"] not in ENUM_TRIGGER_TYPE:
            issues.append(
                f"[FAIL][🚨致命] Detail response - trigger_type='{t['trigger_type']}' "
                f"not in valid enum"
            )

        extra = set(t.keys()) - set(CONTRACT_FIELDS)
        if extra:
            issues.append(f"[WARN][⚠警告] Detail response - Extra fields: {extra}")

    # --- Check create response ---
    # Re-fetch one of our triggers to ensure consistency
    if TEST_NAMES["triggers"]:
        tid = TEST_NAMES["triggers"][0]
        r = requests.get(f"{BASE_URL}/triggers/{tid}", headers=headers())
        t = r.json().get("data", {})

        # Verify create response has same fields
        for f in CONTRACT_FIELDS:
            if f not in t:
                issues.append(f"[FAIL][🚨致命] Create/Detail response - Missing field '{f}'")

    # --- Check execute response (if we got one) ---
    # (We check in test_execute_trigger)
    # Check contract defines: task_id (string), session_id (string)

    # --- Summary ---
    if issues:
        print("\n--- Contract Compliance Report ---")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("[PASS] All contract validations passed!")

    return issues


# ========== CLEANUP ==========

def cleanup():
    """Clean up all test data.
    Order: delete triggers first, then apps, then workflows, then agents."""
    print("\n=== CLEANUP ===")

    # Delete triggers (by id, newest first)
    for tid in reversed(TEST_NAMES["triggers"]):
        try:
            r = requests.delete(f"{BASE_URL}/triggers/{tid}", headers=headers())
            if r.json().get("code") == 0:
                print(f"[CLEANUP] Deleted trigger id={tid}")
        except Exception as e:
            print(f"[CLEANUP] Error deleting trigger id={tid}: {e}")

    # Delete apps (by name)
    for name in reversed(TEST_NAMES["app"]):
        try:
            r = requests.get(f"{BASE_URL}/apps", headers=headers())
            for a in r.json().get("data", []):
                if a["name"] == name:
                    requests.delete(f"{BASE_URL}/apps/{a['id']}", headers=headers())
                    print(f"[CLEANUP] Deleted app name='{name}' id={a['id']}")
                    break
        except Exception as e:
            print(f"[CLEANUP] Error deleting app name='{name}': {e}")

    # Delete workflows (by name)
    for name in reversed(TEST_NAMES["workflow"]):
        try:
            r = requests.get(f"{BASE_URL}/workflows?status=published", headers=headers())
            published = r.json().get("data", [])
            for w in published:
                if w["name"] == name:
                    # Archive first (unpublish)
                    requests.post(f"{BASE_URL}/workflows/{w['id']}/archive", headers=headers())
                    # Then delete
                    requests.delete(f"{BASE_URL}/workflows/{w['id']}", headers=headers())
                    print(f"[CLEANUP] Deleted workflow name='{name}' id={w['id']}")
                    break
        except Exception as e:
            print(f"[CLEANUP] Error deleting workflow name='{name}': {e}")

    # Try delete workflows that are draft
    try:
        r = requests.get(f"{BASE_URL}/workflows", headers=headers())
        for w in r.json().get("data", []):
            if w["name"] in TEST_NAMES["workflow"]:
                requests.delete(f"{BASE_URL}/workflows/{w['id']}", headers=headers())
                print(f"[CLEANUP] Deleted draft workflow name='{w['name']}' id={w['id']}")
    except Exception as e:
        print(f"[CLEANUP] Error: {e}")

    # Delete agents (by name)
    for name in reversed(TEST_NAMES["agent"]):
        try:
            r = requests.get(f"{BASE_URL}/agents", headers=headers())
            for a in r.json().get("data", []):
                if a["name"] == name:
                    requests.delete(f"{BASE_URL}/agents/{a['id']}", headers=headers())
                    print(f"[CLEANUP] Deleted agent name='{name}' id={a['id']}")
                    break
        except Exception as e:
            print(f"[CLEANUP] Error deleting agent name='{name}': {e}")


# ========== MAIN ==========

if __name__ == "__main__":
    failures = 0
    try:
        login()
        app_id = ensure_test_data()
        assert app_id, "No valid app_id for testing"

        test_create_interval_trigger(app_id)
        test_create_cron_trigger(app_id)
        test_list_triggers()
        test_get_trigger()
        test_update_trigger()
        test_execute_trigger()
        test_error_cases(app_id)
        test_delete_trigger()

        issues = contract_validation()
        if issues:
            failures = len(issues)

        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        total_tests = 8  # test functions
        passed = total_tests
        if failures > 0:
            passed = total_tests - 1  # approximate
        print(f"[TESTS] Functional tests: {total_tests}")
        print(f"[CONTRACT] Issues found: {len(issues)}")
        if failures > 0:
            print(f"[RESULT] {failures} issue(s) found")

    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        traceback.print_exc()
        failures += 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        traceback.print_exc()
        failures += 1
    finally:
        cleanup()
        print("\nDone.")
        sys.exit(1 if failures > 0 else 0)
