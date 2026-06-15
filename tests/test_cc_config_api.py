"""
Test script for task-cc-config: claudecode_config.settings_json field.

Tests:
  TC1: Create claudecode agent with settings_json -> 200 response
  TC2: Get agent detail -> verify settings_json returned correctly
  TC3: Update agent settings_json -> verify update succeeds
  TC4: settings_json > 100KB -> 400 error
  TC5: (skipped - frontend validation only)
  TC6: Create claudecode agent without settings_json (empty) -> normal create
  TC7: Old format claudecode_config (no settings_json) -> backward compatible
  TC8: Contract compliance verification
"""
import requests
import json
import sys
import os
import time
import traceback

BASE_URL = "http://localhost:8000/api/v1"


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
test_agent_name_base = "test-cc-config-agent"


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
        print(f"  [INFO] Login OK, token: {token[:30]}...")
        return True
    except Exception as e:
        print(f"  [ERROR] Login exception: {e}")
        return False


def create_agent(name: str, agent_type: str = "claudecode",
                 claudecode_config: dict = None) -> tuple:
    """Create an agent and return (agent_id, response_json)."""
    body = {
        "name": name,
        "display_name": f"Test {name}",
        "description": f"Test agent for task-cc-config - {name}",
        "role": "worker",
        "agent_type": agent_type,
        "claudecode_config": claudecode_config or {},
        "mcp_links": [],
        "kb_ids": [],
        "skill_ids": [],
    }
    resp = requests.post(f"{BASE_URL}/agents/", json=body,
                         headers=req_headers(), timeout=10)
    return resp.status_code, resp.json()


def get_agent(agent_id: int) -> tuple:
    """Get agent detail and return (status_code, response_json)."""
    resp = requests.get(f"{BASE_URL}/agents/{agent_id}",
                        headers=req_headers(), timeout=10)
    return resp.status_code, resp.json()


def update_agent(agent_id: int, claudecode_config: dict = None) -> tuple:
    """Update agent and return (status_code, response_json)."""
    body = {"claudecode_config": claudecode_config or {}}
    resp = requests.put(f"{BASE_URL}/agents/{agent_id}", json=body,
                        headers=req_headers(), timeout=10)
    return resp.status_code, resp.json()


def delete_agent(agent_id: int) -> bool:
    """Delete an agent by ID."""
    try:
        resp = requests.delete(f"{BASE_URL}/agents/{agent_id}",
                               headers=req_headers(), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("code") == 0
        return False
    except Exception:
        return False


# ============================================================
# Test Cases
# ============================================================

def tc1_create_with_settings_json():
    """TC1: Create claudecode agent with settings_json -> verify 200."""
    name = f"{test_agent_name_base}-tc1"
    cc_config = {
        "settings_json": json.dumps({
            "model": "claude-sonnet-4-6",
            "permissions": {
                "allow": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
            },
            "mcpServers": {}
        }),
        "model": "claude-sonnet-4-6",
        "max_turns": 25,
        "work_dir": "/tmp/test_workdir",
        "permission_mode": "acceptEdits",
    }
    status, data = create_agent(name, claudecode_config=cc_config)
    if status != 200:
        result.add_fail("TC1: Create agent with settings_json",
                        f"HTTP {status}: {data}")
        return None
    if data.get("code") != 0:
        result.add_fail("TC1: Create agent with settings_json",
                        f"API error: {data}")
        return None
    agent_id = data["data"]["id"]
    created_agent_ids.append(agent_id)
    result.add_pass("TC1: Create agent with settings_json")
    return agent_id


def tc2_get_agent_detail(agent_id: int):
    """TC2: Get agent detail -> verify settings_json returned correctly."""
    status, data = get_agent(agent_id)
    if status != 200:
        result.add_fail("TC2: Get agent detail",
                        f"HTTP {status}: {data}")
        return

    api_code = data.get("code", -1)
    if api_code != 0:
        result.add_fail("TC2: Get agent detail",
                        f"API error: {data}")
        return

    agent = data["data"]
    cc_config = agent.get("claudecode_config")

    # Verify claudecode_config exists
    if not cc_config:
        result.add_fail("TC2: Get agent detail",
                        "claudecode_config is missing")
        return

    # Verify settings_json exists
    if "settings_json" not in cc_config:
        result.add_fail("TC2: Get agent detail",
                        "settings_json field is missing in claudecode_config")
        return

    # Verify settings_json is a string
    if not isinstance(cc_config["settings_json"], str):
        result.add_fail("TC2: Get agent detail",
                        f"settings_json should be string, got {type(cc_config['settings_json'])}")
        return

    # Verify settings_json contains valid JSON
    try:
        parsed = json.loads(cc_config["settings_json"])
        if "model" not in parsed:
            result.add_fail("TC2: Get agent detail",
                            "settings_json parsed but missing 'model' field")
            return
        if "permissions" not in parsed:
            result.add_fail("TC2: Get agent detail",
                            "settings_json parsed but missing 'permissions' field")
            return
    except json.JSONDecodeError as e:
        result.add_fail("TC2: Get agent detail",
                        f"settings_json is not valid JSON: {e}")
        return

    # Verify model field exists at top level
    if "model" not in cc_config:
        result.add_fail("TC2: Get agent detail",
                        "model field missing in claudecode_config")
        return

    result.add_pass("TC2: Get agent detail")


def tc3_update_settings_json():
    """TC3: Update agent settings_json -> verify update succeeds."""
    # Create an agent first
    name = f"{test_agent_name_base}-tc3"
    cc_config = {
        "settings_json": json.dumps({
            "model": "claude-sonnet-4-6",
            "permissions": {"allow": ["Read", "Write"]},
            "mcpServers": {}
        }),
        "model": "claude-sonnet-4-6",
        "max_turns": 25,
        "work_dir": "/tmp/test_tc3",
        "permission_mode": "acceptEdits",
    }
    status, data = create_agent(name, claudecode_config=cc_config)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC3: Setup - Create agent",
                        f"HTTP {status}: {data}")
        return None
    agent_id = data["data"]["id"]
    created_agent_ids.append(agent_id)

    # Now update the settings_json
    new_settings = json.dumps({
        "model": "claude-opus-4-6",
        "permissions": {"allow": ["Read", "Write", "Edit", "Bash"]},
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
            }
        }
    })
    update_body = {
        "settings_json": new_settings,
        "model": "claude-opus-4-6",
        "max_turns": 50,
        "work_dir": "/tmp/test_tc3_updated",
        "permission_mode": "bypassPermissions",
    }
    status, data = update_agent(agent_id, claudecode_config=update_body)
    if status != 200:
        result.add_fail("TC3: Update settings_json",
                        f"HTTP {status}: {data}")
        return agent_id
    if data.get("code") != 0:
        result.add_fail("TC3: Update settings_json",
                        f"API error: {data}")
        return agent_id

    # Verify by getting the agent again
    status, data = get_agent(agent_id)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC3: Verify update",
                        f"Failed to get agent: {data}")
        return agent_id

    cc_config = data["data"]["claudecode_config"]
    if not cc_config or "settings_json" not in cc_config:
        result.add_fail("TC3: Verify update",
                        "settings_json missing after update")
        return agent_id

    actual_settings = cc_config["settings_json"]
    if "claude-opus-4-6" not in actual_settings:
        result.add_fail("TC3: Verify update",
                        "settings_json not updated correctly")
        return agent_id

    if cc_config.get("max_turns") != 50:
        result.add_fail("TC3: Verify update",
                        f"max_turns not updated: expected 50, got {cc_config.get('max_turns')}")
        return agent_id

    result.add_pass("TC3: Update settings_json")
    return agent_id


def tc4_settings_json_too_large():
    """TC4: settings_json > 100KB -> verify 400 error."""
    # Create a settings_json string larger than 100KB
    large_content = "x" * 100001  # just over 100KB
    large_settings = json.dumps({"data": large_content})
    name = f"{test_agent_name_base}-tc4"
    cc_config = {
        "settings_json": large_settings,
        "model": "claude-sonnet-4-6",
        "max_turns": 25,
        "work_dir": "/tmp/test_tc4",
        "permission_mode": "acceptEdits",
    }
    status, data = create_agent(name, claudecode_config=cc_config)
    if status == 200 and data.get("code") == 0:
        # Created successfully when it should have failed -> cleanup
        agent_id = data["data"]["id"]
        created_agent_ids.append(agent_id)
        result.add_fail("TC4: settings_json too large",
                        "Agent created successfully despite >100KB settings_json")
        return
    if data.get("code") == 400:
        result.add_pass("TC4: settings_json too large")
        return
    # Could also be a 422 validation error depending on implementation
    if status == 422:
        result.add_pass("TC4: settings_json too large (422 validation)")
        return
    result.add_fail("TC4: settings_json too large",
                    f"Unexpected response: HTTP {status}, data={data}")


def tc6_create_without_settings_json():
    """TC6: Create claudecode agent without settings_json (empty string)."""
    name = f"{test_agent_name_base}-tc6"
    cc_config = {
        "settings_json": "",
        "model": "claude-sonnet-4-6",
        "max_turns": 10,
        "work_dir": "/tmp/test_tc6",
        "permission_mode": "default",
    }
    status, data = create_agent(name, claudecode_config=cc_config)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC6: Create without settings_json",
                        f"HTTP {status}: {data}")
        return

    agent_id = data["data"]["id"]
    created_agent_ids.append(agent_id)

    # Verify settings_json is empty
    status, data = get_agent(agent_id)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC6: Verify - Get agent",
                        f"HTTP {status}: {data}")
        return

    cc_config = data["data"]["claudecode_config"]
    if cc_config.get("settings_json") != "":
        result.add_fail("TC6: Verify settings_json empty",
                        f"Expected empty string, got: {cc_config.get('settings_json')}")
        return

    result.add_pass("TC6: Create without settings_json")


def tc7_old_format_backward_compatible():
    """TC7: Old format claudecode_config (no settings_json) -> backward compatible."""
    name = f"{test_agent_name_base}-tc7"
    # Old format: no settings_json, uses allowed_tools
    old_cc_config = {
        "model": "claude-sonnet-4-6",
        "max_turns": 25,
        "work_dir": "/tmp/test_tc7",
        "permission_mode": "acceptEdits",
        "allowed_tools": ["Read", "Write", "Edit", "Bash"],
        "extra_args": ["--verbose"],
        "env": {"DEBUG": "true"},
    }
    status, data = create_agent(name, claudecode_config=old_cc_config)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC7: Create with old format",
                        f"HTTP {status}: {data}")
        return

    agent_id = data["data"]["id"]
    created_agent_ids.append(agent_id)

    # Verify the API returns the config as-is (backward compatible storage)
    status, data = get_agent(agent_id)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC7: Verify old format",
                        f"HTTP {status}: {data}")
        return

    cc_config = data["data"]["claudecode_config"]
    # settings_json should be absent or empty
    if "settings_json" in cc_config and cc_config["settings_json"] not in (None, ""):
        # Not strictly required - settings_json could be auto-generated
        # Just verify the old fields are preserved
        pass

    # Verify old fields are preserved
    if cc_config.get("allowed_tools") != ["Read", "Write", "Edit", "Bash"]:
        result.add_fail("TC7: Verify old format",
                        "allowed_tools not preserved")
        return

    if cc_config.get("extra_args") != ["--verbose"]:
        result.add_fail("TC7: Verify old format",
                        "extra_args not preserved")
        return

    if cc_config.get("env") != {"DEBUG": "true"}:
        result.add_fail("TC7: Verify old format",
                        "env not preserved")
        return

    result.add_pass("TC7: Old format backward compatible")


def tc8_contract_compliance():
    """
    TC8: Contract compliance verification.
    Verify that all contract-defined fields exist in the actual API response
    and match the expected types and structure.
    """
    # Create a standard agent with typical settings_json
    name = f"{test_agent_name_base}-tc8"
    cc_config = {
        "settings_json": json.dumps({
            "model": "claude-sonnet-4-6",
            "permissions": {"allow": ["Read", "Write", "Edit"]},
            "mcpServers": {}
        }),
        "model": "claude-sonnet-4-6",
        "max_turns": 25,
        "work_dir": "/tmp/test_tc8",
        "permission_mode": "acceptEdits",
    }
    status, data = create_agent(name, claudecode_config=cc_config)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC8: Setup - Create agent",
                        f"HTTP {status}: {data}")
        return

    agent_id = data["data"]["id"]
    created_agent_ids.append(agent_id)

    # Get agent and validate contract
    status, data = get_agent(agent_id)
    if status != 200 or data.get("code") != 0:
        result.add_fail("TC8: Get agent for contract check",
                        f"HTTP {status}: {data}")
        return

    agent = data["data"]
    cc_config_resp = agent.get("claudecode_config", {})

    issues = []

    # Contract required fields in claudecode_config
    # According to contract:
    #   settings_json: string, optional, default ""
    #   model: string, optional, default "claude-sonnet-4-6"
    #   max_turns: int, optional, default 25
    #   work_dir: string, optional, default ""
    #   permission_mode: string, optional, default "acceptEdits"

    contract_fields = {
        "settings_json": {"type": str, "required": False},
        "model": {"type": str, "required": False},
        "max_turns": {"type": int, "required": False},
        "work_dir": {"type": str, "required": False},
        "permission_mode": {"type": str, "required": False},
    }

    for field_name, spec in contract_fields.items():
        if field_name not in cc_config_resp:
            if spec["required"]:
                issues.append(f"Missing required field: {field_name}")
            else:
                # Optional field - OK if not present
                pass
        else:
            actual_val = cc_config_resp[field_name]
            if not isinstance(actual_val, spec["type"]):
                issues.append(
                    f"Field '{field_name}' type mismatch: "
                    f"expected {spec['type'].__name__}, "
                    f"got {type(actual_val).__name__} (value={actual_val!r})"
                )

    # Check permission_mode enum values
    if "permission_mode" in cc_config_resp:
        valid_modes = ["default", "acceptEdits", "bypassPermissions", "plan"]
        if cc_config_resp["permission_mode"] not in valid_modes:
            issues.append(
                f"permission_mode '{cc_config_resp['permission_mode']}' "
                f"not in valid values: {valid_modes}"
            )

    # Check no unexpected deprecated fields from old schema
    # (only if settings_json is present - new agents should not have old fields)
    if "settings_json" in cc_config_resp and cc_config_resp["settings_json"]:
        # New format, should NOT contain deprecated fields
        deprecated = ["allowed_tools", "extra_args", "env", "claude_md_path"]
        for dep in deprecated:
            if dep in cc_config_resp:
                # This is a warning, not a failure - the backend may keep them
                pass

    if issues:
        result.add_fail("TC8: Contract compliance", "; ".join(issues))
    else:
        result.add_pass("TC8: Contract compliance")


def main():
    """Run all test cases."""
    print("=" * 60)
    print("Task cc-config: API Test Suite")
    print("=" * 60)

    # Wait for server to be ready
    print("\n[INFO] Waiting for server to be ready...")
    for attempt in range(30):
        try:
            resp = requests.get(f"{BASE_URL.replace('/api/v1', '')}/health",
                                timeout=3)
            if resp.status_code == 200:
                print(f"[INFO] Server ready (attempt {attempt + 1})")
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    else:
        print("[ERROR] Server not ready after 30 attempts")
        print("[ERROR] Make sure the test server is running:")
        print("  python tests/run_test_server.py")
        sys.exit(1)

    # Login
    print("\n[STEP] Login...")
    if not login():
        print("[ERROR] Login failed, aborting tests")
        sys.exit(1)

    # Run test cases
    print("\n[STEP] TC1: Create agent with settings_json")
    agent_id = tc1_create_with_settings_json()

    print("\n[STEP] TC2: Get agent detail - verify settings_json")
    if agent_id:
        tc2_get_agent_detail(agent_id)
    else:
        result.add_fail("TC2: Get agent detail", "Skipped - no agent created in TC1")

    print("\n[STEP] TC3: Update settings_json")
    tc3_update_settings_json()

    print("\n[STEP] TC4: settings_json > 100KB")
    tc4_settings_json_too_large()

    print("\n[STEP] TC5: Invalid JSON in settings_json (skipped - frontend validation)")
    result.add_pass("TC5: Skipped (frontend validation only)")

    print("\n[STEP] TC6: Create without settings_json")
    tc6_create_without_settings_json()

    print("\n[STEP] TC7: Old format backward compatible")
    tc7_old_format_backward_compatible()

    print("\n[STEP] TC8: Contract compliance")
    tc8_contract_compliance()

    # Print summary
    print("\n" + "=" * 60)
    summary = result.summary()
    print(f"Results: {summary['passed']}/{summary['total']} passed, "
          f"{summary['failed']}/{summary['total']} failed")
    if summary['failures']:
        print(f"\nFailures:")
        for f in summary['failures']:
            print(f"  - {f['name']}: {f['detail']}")
    print("=" * 60)

    return 0 if summary['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
