"""
Test script for task-a2a-agent: A2A Agent type CRUD + Contract Compliance.

Tests:
  TC1: POST /api/v1/agents/ -- Create A2A Agent with a2a_config
  TC2: GET /api/v1/agents/{id} -- Verify a2a_config in detail response
  TC3: PUT /api/v1/agents/{id} -- Update A2A Agent a2a_config
  TC4: GET /api/v1/agents/?agent_type=a2a -- Filter by agent_type=a2a
  TC5: POST /api/v1/agents/{id}/copy -- Copy A2A Agent (verify a2a_config copied)
  TC6: DELETE /api/v1/agents/{id} -- Cleanup test agents
  TC7: Contract compliance verification
"""
import requests
import json
import sys
import os
import time
import traceback

# ---------------------------------------------------------------------------
# Database setup: patch TORTOISE_ORM to use SQLite before any backend imports
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import config
config.TORTOISE_ORM = {
    "connections": {"default": "sqlite://test_a2a.db"},
    "apps": {
        "models": {
            "models": config.TORTOISE_ORM["apps"]["models"]["models"],
            "default_connection": "default",
        }
    },
    "timezone": "Asia/Shanghai",
}

# ---------------------------------------------------------------------------
# Start the backend server
# ---------------------------------------------------------------------------
import uvicorn
import multiprocessing
import signal

SERVER_PORT = 8765
BASE_URL = f"http://localhost:{SERVER_PORT}/api/v1"


class TestResult:
    """Custom test result class."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []
        self.total = 0

    def add_pass(self, name: str):
        self.passed += 1
        self.total += 1
        print(f"  [PASS] {name}")

    def add_fail(self, name: str, detail: str):
        self.failed += 1
        self.total += 1
        self.failures.append({"name": name, "detail": detail})
        print(f"  [FAIL] {name}: {detail}")

    def summary(self) -> dict:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "failures": self.failures,
        }


# Global state
result = TestResult()
token: str = ""
created_agent_ids: list = []
test_counter = 0

# Contract-defined a2a_config structure
CONTRACT_A2A_CONFIG = {
    "url": "http://test-peer-agent:8080/api/v1/chat",
    "headers": {"Authorization": "Bearer test-token-123", "X-API-Key": "test-key-456"},
    "timeout": 30,
}

CONTRACT_A2A_CONFIG_UPDATED = {
    "url": "http://updated-peer:9090/api/v1/chat",
    "headers": {"X-API-Key": "updated-key-789"},
    "timeout": 60,
}


def req_headers() -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def login() -> bool:
    """Login and get JWT token from the seed admin user."""
    global token
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": "admin",
            "password": "admin123",
        }, timeout=10)
        if resp.status_code != 200:
            print(f"  [ERROR] Login HTTP {resp.status_code}: {resp.text}")
            return False
        data = resp.json()
        if data.get("code") != 0:
            print(f"  [ERROR] Login failed: {data}")
            return False
        token = data["data"]["access_token"]
        print(f"  [INFO] Token acquired: {token[:30]}...")
        return True
    except Exception as e:
        print(f"  [ERROR] Login exception: {e}")
        return False


def test_create_a2a_agent() -> int:
    """TC1: Create A2A Agent with a2a_config. Returns agent_id."""
    global test_counter
    test_counter += 1
    agent_name = f"test-a2a-agent-{int(time.time())}"
    body = {
        "name": agent_name,
        "display_name": "Test A2A Agent",
        "description": "A2A Agent for testing",
        "role": "worker",
        "agent_type": "a2a",
        "system_prompt": "You are a test A2A agent.",
        "a2a_config": CONTRACT_A2A_CONFIG,
    }
    try:
        resp = requests.post(f"{BASE_URL}/agents/", json=body, headers=req_headers(), timeout=10)
        if resp.status_code != 200:
            result.add_fail("TC1: Create A2A Agent", f"HTTP {resp.status_code}: {resp.text}")
            return 0
        data = resp.json()
        if data.get("code") != 0:
            result.add_fail("TC1: Create A2A Agent", f"code={data.get('code')}: {data.get('message')}")
            return 0
        agent_id = data["data"]["id"]
        created_agent_ids.append(agent_id)
        result.add_pass("TC1: Create A2A Agent")
        print(f"       Created agent id={agent_id}, name={agent_name}")
        return agent_id
    except Exception as e:
        result.add_fail("TC1: Create A2A Agent", f"Exception: {e}")
        return 0


def test_get_agent_detail(agent_id: int) -> bool:
    """TC2: GET /api/v1/agents/{id} and verify a2a_config."""
    if not agent_id:
        result.add_fail("TC2: Get Agent Detail", "Skipped - no agent_id")
        return False
    try:
        resp = requests.get(f"{BASE_URL}/agents/{agent_id}", headers=req_headers(), timeout=10)
        if resp.status_code != 200:
            result.add_fail("TC2: Get Agent Detail", f"HTTP {resp.status_code}: {resp.text}")
            return False
        data = resp.json()
        if data.get("code") != 0:
            result.add_fail("TC2: Get Agent Detail", f"code={data.get('code')}: {data.get('message')}")
            return False

        agent_data = data["data"]

        # Verify a2a_config exists in response
        if "a2a_config" not in agent_data:
            result.add_fail("TC2: Get Agent Detail", "a2a_config field missing in response")
            return False

        # Verify a2a_config values
        rc = agent_data["a2a_config"]
        if rc.get("url") != CONTRACT_A2A_CONFIG["url"]:
            result.add_fail("TC2: Get Agent Detail", f"url mismatch: {rc.get('url')}")
            return False
        if rc.get("timeout") != CONTRACT_A2A_CONFIG["timeout"]:
            result.add_fail("TC2: Get Agent Detail", f"timeout mismatch: {rc.get('timeout')}")
            return False
        if rc.get("headers", {}).get("Authorization") != CONTRACT_A2A_CONFIG["headers"]["Authorization"]:
            result.add_fail("TC2: Get Agent Detail", f"headers.Authorization mismatch")
            return False

        # Verify agent_type
        if agent_data.get("agent_type") != "a2a":
            result.add_fail("TC2: Get Agent Detail", f"agent_type mismatch: {agent_data.get('agent_type')}")
            return False

        result.add_pass("TC2: Get Agent Detail (a2a_config verified)")
        return True
    except Exception as e:
        result.add_fail("TC2: Get Agent Detail", f"Exception: {e}")
        return False


def test_update_a2a_agent(agent_id: int) -> bool:
    """TC3: PUT /api/v1/agents/{id} to update a2a_config."""
    if not agent_id:
        result.add_fail("TC3: Update A2A Agent", "Skipped - no agent_id")
        return False
    try:
        body = {
            "a2a_config": CONTRACT_A2A_CONFIG_UPDATED,
            "display_name": "Updated A2A Agent",
        }
        resp = requests.put(f"{BASE_URL}/agents/{agent_id}", json=body, headers=req_headers(), timeout=10)
        if resp.status_code != 200:
            result.add_fail("TC3: Update A2A Agent", f"HTTP {resp.status_code}: {resp.text}")
            return False
        data = resp.json()
        if data.get("code") != 0:
            result.add_fail("TC3: Update A2A Agent", f"code={data.get('code')}: {data.get('message')}")
            return False

        # Verify by getting detail
        resp2 = requests.get(f"{BASE_URL}/agents/{agent_id}", headers=req_headers(), timeout=10)
        agent_data = resp2.json()["data"]
        rc = agent_data["a2a_config"]
        if rc.get("url") != CONTRACT_A2A_CONFIG_UPDATED["url"]:
            result.add_fail("TC3: Update A2A Agent", f"Updated url mismatch: {rc.get('url')}")
            return False
        if rc.get("timeout") != CONTRACT_A2A_CONFIG_UPDATED["timeout"]:
            result.add_fail("TC3: Update A2A Agent", f"Updated timeout mismatch: {rc.get('timeout')}")
            return False
        if agent_data.get("display_name") != "Updated A2A Agent":
            result.add_fail("TC3: Update A2A Agent", f"display_name not updated")
            return False

        result.add_pass("TC3: Update A2A Agent (a2a_config updated)")
        return True
    except Exception as e:
        result.add_fail("TC3: Update A2A Agent", f"Exception: {e}")
        return False


def test_list_by_agent_type(agent_id: int) -> bool:
    """TC4: GET /api/v1/agents/?agent_type=a2a and verify."""
    if not agent_id:
        result.add_fail("TC4: List by agent_type=a2a", "Skipped - no agent_id")
        return False
    try:
        resp = requests.get(f"{BASE_URL}/agents/?agent_type=a2a", headers=req_headers(), timeout=10)
        if resp.status_code != 200:
            result.add_fail("TC4: List by agent_type=a2a", f"HTTP {resp.status_code}: {resp.text}")
            return False
        data = resp.json()
        if data.get("code") != 0:
            result.add_fail("TC4: List by agent_type=a2a", f"code={data.get('code')}: {data.get('message')}")
            return False

        agents = data["data"]
        if not agents:
            result.add_fail("TC4: List by agent_type=a2a", "No agents returned in list")
            return False

        # Verify all returned agents are type a2a
        all_a2a = all(a.get("agent_type") == "a2a" for a in agents)
        if not all_a2a:
            result.add_fail("TC4: List by agent_type=a2a", "Not all returned agents have agent_type=a2a")
            return False

        # Verify our test agent is in the list
        ids_in_list = [a["id"] for a in agents]
        if agent_id not in ids_in_list:
            result.add_fail("TC4: List by agent_type=a2a", f"Agent {agent_id} not found in list")
            return False

        # Verify a2a_config is NOT returned in list (per contract: LIST hides sensitive config)
        if "a2a_config" in agents[0]:
            result.add_fail("TC4: List by agent_type=a2a", "a2a_config should NOT be returned in LIST response")
            return False

        result.add_pass("TC4: List by agent_type=a2a (filter works, a2a_config hidden)")
        return True
    except Exception as e:
        result.add_fail("TC4: List by agent_type=a2a", f"Exception: {e}")
        return False


def test_copy_a2a_agent(agent_id: int) -> int:
    """TC5: POST /api/v1/agents/{id}/copy and verify a2a_config copied."""
    if not agent_id:
        result.add_fail("TC5: Copy A2A Agent", "Skipped - no agent_id")
        return 0
    try:
        resp = requests.post(f"{BASE_URL}/agents/{agent_id}/copy", headers=req_headers(), timeout=10)
        if resp.status_code != 200:
            result.add_fail("TC5: Copy A2A Agent", f"HTTP {resp.status_code}: {resp.text}")
            return 0
        data = resp.json()
        if data.get("code") != 0:
            result.add_fail("TC5: Copy A2A Agent", f"code={data.get('code')}: {data.get('message')}")
            return 0

        copied_id = data["data"]["id"]
        copied_name = data["data"]["name"]
        created_agent_ids.append(copied_id)

        # Verify detail of copied agent
        resp2 = requests.get(f"{BASE_URL}/agents/{copied_id}", headers=req_headers(), timeout=10)
        copied_data = resp2.json()["data"]
        copied_config = copied_data.get("a2a_config")

        if not copied_config:
            result.add_fail("TC5: Copy A2A Agent", "Copied agent has no a2a_config")
            return 0

        # Compare with the updated config (since we updated in TC3)
        if copied_config.get("url") != CONTRACT_A2A_CONFIG_UPDATED["url"]:
            result.add_fail("TC5: Copy A2A Agent", f"Copied url mismatch: {copied_config.get('url')}")
            return 0
        if copied_config.get("timeout") != CONTRACT_A2A_CONFIG_UPDATED["timeout"]:
            result.add_fail("TC5: Copy A2A Agent", f"Copied timeout mismatch: {copied_config.get('timeout')}")
            return 0

        if copied_data.get("agent_type") != "a2a":
            result.add_fail("TC5: Copy A2A Agent", f"Copied agent_type mismatch: {copied_data.get('agent_type')}")
            return 0

        result.add_pass(f"TC5: Copy A2A Agent (copied id={copied_id}, a2a_config preserved)")
        return copied_id
    except Exception as e:
        result.add_fail("TC5: Copy A2A Agent", f"Exception: {e}")
        return 0


def test_delete_agent(agent_id: int, expect_exists: bool = True) -> bool:
    """TC6: DELETE /api/v1/agents/{id} to clean up."""
    if not agent_id:
        result.add_fail("TC6: Delete Agent", "Skipped - no agent_id")
        return False
    try:
        # First check if agent exists
        check = requests.get(f"{BASE_URL}/agents/{agent_id}", headers=req_headers(), timeout=10)
        agent_exists = (check.status_code == 200 and check.json().get("code") == 0)

        if not agent_exists and not expect_exists:
            result.add_pass("TC6: Delete Agent (already cleaned up)")
            return True

        if not agent_exists:
            result.add_fail("TC6: Delete Agent", "Agent does not exist (already deleted?)")
            return False

        resp = requests.delete(f"{BASE_URL}/agents/{agent_id}", headers=req_headers(), timeout=10)
        if resp.status_code != 200:
            result.add_fail("TC6: Delete Agent", f"HTTP {resp.status_code}: {resp.text}")
            return False
        data = resp.json()
        if data.get("code") != 0:
            result.add_fail("TC6: Delete Agent", f"code={data.get('code')}: {data.get('message')}")
            return False

        # Verify deletion
        resp2 = requests.get(f"{BASE_URL}/agents/{agent_id}", headers=req_headers(), timeout=10)
        if resp2.status_code == 200 and resp2.json().get("code") == 0:
            result.add_fail("TC6: Delete Agent", "Agent still exists after deletion")
            return False

        result.add_pass("TC6: Delete Agent (cleanup)")
        return True
    except Exception as e:
        result.add_fail("TC6: Delete Agent", f"Exception: {e}")
        return False


def test_contract_compliance(agent_id: int) -> bool:
    """TC7: Contract compliance verification.

    Checks:
    1. Response field names match contract (snake_case)
    2. Field types match contract
    3. No extra/missing required fields
    4. Enum values match contract (agent_type="a2a")
    5. a2a_config structure matches contract
    """
    if not agent_id:
        result.add_fail("TC7: Contract Compliance", "Skipped - no agent_id")
        return False

    all_passed = True
    try:
        resp = requests.get(f"{BASE_URL}/agents/{agent_id}", headers=req_headers(), timeout=10)
        if resp.status_code != 200:
            result.add_fail("TC7: Contract Compliance", f"Cannot fetch agent detail: HTTP {resp.status_code}")
            return False
        actual = resp.json()["data"]

        # ----- Detail Response contract fields -----
        detail_fields_contract = [
            ("id", int, True),
            ("name", str, True),
            ("display_name", str, True),
            ("description", str, True),
            ("role", str, True),
            ("agent_type", str, True),
            ("llm_config", (dict, type(None)), True),
            ("llm_config_id", (int, type(None)), True),
            ("http_config", (dict, type(None)), True),
            ("claudecode_config", (dict, type(None)), True),
            ("a2a_config", (dict, type(None)), True),
            ("system_prompt", str, True),
            ("status", str, True),
            ("knowledge_base_ids", list, True),
            ("mcp_links", list, True),
            ("kb_links", list, True),
            ("skill_links", list, True),
            ("created_at", str, True),
            ("updated_at", (str, type(None)), True),
        ]

        for field_name, expected_type, is_required in detail_fields_contract:
            # Check field presence
            if field_name not in actual:
                result.add_fail(f"TC7: Contract Detail - Field '{field_name}'",
                              f"MISSING in response (required={is_required})")
                all_passed = False
                continue

            # Check field type
            val = actual[field_name]
            if isinstance(expected_type, tuple):
                if not isinstance(val, expected_type):
                    result.add_fail(f"TC7: Contract Detail - Field '{field_name}' type",
                                  f"Expected {expected_type}, got {type(val).__name__} = {val}")
                    all_passed = False
            else:
                if not isinstance(val, expected_type):
                    result.add_fail(f"TC7: Contract Detail - Field '{field_name}' type",
                                  f"Expected {expected_type.__name__}, got {type(val).__name__} = {val}")
                    all_passed = False

        # ----- Check a2a_config internal structure matches contract -----
        a2a = actual.get("a2a_config")
        if a2a is not None:
            contract_a2a_fields = [
                ("url", str, True),
                ("headers", dict, False),
                ("timeout", (int, float), False),
            ]
            for field_name, expected_type, is_required in contract_a2a_fields:
                if field_name not in a2a:
                    if is_required:
                        result.add_fail(f"TC7: Contract a2a_config - Field '{field_name}'",
                                      f"MISSING but contract says required")
                        all_passed = False
                    continue
                val = a2a[field_name]
                if isinstance(expected_type, tuple):
                    if not isinstance(val, expected_type):
                        result.add_fail(f"TC7: Contract a2a_config - Field '{field_name}' type",
                                      f"Expected {expected_type}, got {type(val).__name__} = {val}")
                        all_passed = False
                else:
                    if not isinstance(val, expected_type):
                        result.add_fail(f"TC7: Contract a2a_config - Field '{field_name}' type",
                                      f"Expected {expected_type.__name__}, got {type(val).__name__} = {val}")
                        all_passed = False

        # ----- Check agent_type enum value -----
        agent_type_val = actual.get("agent_type")
        if agent_type_val != "a2a":
            # If the agent was updated to another type, just note it
            valid_types = ["local", "http", "claudecode", "a2a"]
            if agent_type_val not in valid_types:
                result.add_fail(f"TC7: Contract - agent_type enum",
                              f"Value '{agent_type_val}' not in valid types {valid_types}")
                all_passed = False

        # ----- Check no unexpected extra fields in a2a_config -----
        if a2a is not None:
            allowed_a2a_fields = {"url", "headers", "timeout"}
            actual_a2a_fields = set(a2a.keys())
            extra = actual_a2a_fields - allowed_a2a_fields
            if extra:
                result.add_fail(f"TC7: Contract a2a_config - Extra fields",
                              f"Unexpected fields in a2a_config: {extra}")
                all_passed = False

        if all_passed:
            result.add_pass("TC7: Contract Compliance (all fields match)")
        return all_passed

    except Exception as e:
        result.add_fail("TC7: Contract Compliance", f"Exception: {e}")
        traceback.print_exc()
        return False


def cleanup_all():
    """Clean up all created agents in reverse order."""
    global created_agent_ids
    # Remove duplicates while preserving order
    seen = set()
    ids_to_delete = []
    for aid in reversed(created_agent_ids):
        if aid not in seen:
            ids_to_delete.append(aid)
            seen.add(aid)

    for aid in ids_to_delete:
        try:
            requests.delete(f"{BASE_URL}/agents/{aid}", headers=req_headers(), timeout=10)
            print(f"  [CLEANUP] Deleted agent {aid}")
        except Exception as e:
            print(f"  [CLEANUP] Error deleting agent {aid}: {e}")


# ===========================================================================
#  Main
# ===========================================================================
def run_tests():
    """Execute all test cases sequentially."""
    print("")
    print("=" * 60)
    print("  A2A Agent API Integration Tests")
    print("=" * 60)
    print(f"  Base URL: {BASE_URL}")
    print("")

    # Login
    print("[STEP] Login as admin...")
    if not login():
        print("[FATAL] Cannot login. Aborting tests.")
        return
    print("")

    # TC1: Create
    print("[STEP] TC1: Create A2A Agent...")
    agent_id = test_create_a2a_agent()
    print("")

    # TC2: Get detail
    print("[STEP] TC2: Get Agent Detail (verify a2a_config)...")
    test_get_agent_detail(agent_id)
    print("")

    # TC3: Update
    print("[STEP] TC3: Update A2A Agent...")
    test_update_a2a_agent(agent_id)
    print("")

    # TC4: List with filter
    print("[STEP] TC4: List agents by agent_type=a2a...")
    test_list_by_agent_type(agent_id)
    print("")

    # TC5: Copy
    print("[STEP] TC5: Copy A2A Agent...")
    copied_id = test_copy_a2a_agent(agent_id)
    print("")

    # TC7: Contract compliance
    print("[STEP] TC7: Contract Compliance Verification...")
    test_contract_compliance(agent_id)
    print("")

    # Cleanup all test agents
    print("[STEP] Cleanup...")
    cleanup_all()
    # Verify deletion of original and copied agents
    if agent_id:
        test_delete_agent(agent_id, expect_exists=False)
    if copied_id:
        test_delete_agent(copied_id, expect_exists=False)
    print("")

    # Summary
    s = result.summary()
    print("=" * 60)
    print(f"  RESULTS: {s['passed']}/{s['total']} passed, {s['failed']}/{s['total']} failed")
    if s["failures"]:
        print("  FAILURES:")
        for f in s["failures"]:
            print(f"    - {f['name']}: {f['detail']}")
    print("=" * 60)

    # Return exit code
    return 0 if s["failed"] == 0 else 1


if __name__ == "__main__":
    # Import and start the server in a subprocess
    from main import app
    import uvicorn
    import threading
    import time

    server_running = threading.Event()
    server_error = [None]

    def start_server():
        try:
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=SERVER_PORT,
                log_level="warning",
            )
        except Exception as e:
            server_error[0] = e
        finally:
            server_running.set()

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    max_wait = 30
    for i in range(max_wait):
        try:
            r = requests.get(f"http://127.0.0.1:{SERVER_PORT}/health", timeout=2)
            if r.status_code == 200:
                print(f"  [INFO] Server ready after {i+1}s")
                break
        except:
            pass
        if i == 0:
            print("  [INFO] Waiting for server to start...")
        if server_error[0]:
            print(f"  [FATAL] Server failed: {server_error[0]}")
            sys.exit(1)
        time.sleep(1)
    else:
        print("  [FATAL] Server did not start within 30s")
        sys.exit(1)

    time.sleep(1)  # Extra wait for Tortoise migrations

    try:
        exit_code = run_tests()
    finally:
        # Shutdown server by sending a stop request
        try:
            requests.get(f"http://127.0.0.1:{SERVER_PORT}/shutdown", timeout=2)
        except:
            pass
        time.sleep(1)

        # Cleanup SQLite DB
        db_dir = os.path.join(os.path.dirname(__file__), "..")
        db_path = os.path.join(db_dir, "test_a2a.db")
        # Try to remove DB file (may need multiple attempts due to locks)
        for attempt in range(5):
            try:
                if os.path.exists(db_path):
                    os.remove(db_path)
                    print("  [CLEANUP] Removed test SQLite database")
                # Also remove journal/WAL files
                for ext in [".db-journal", ".db-wal", ".db-shm"]:
                    j_path = db_path + ext
                    if os.path.exists(j_path):
                        os.remove(j_path)
                break
            except PermissionError as e:
                if attempt < 4:
                    time.sleep(1)
                else:
                    print(f"  [CLEANUP] Could not remove SQLite DB (will be cleaned on next run): {e}")

    sys.exit(exit_code)
